"""Optimization endpoint for running IDAES process optimization."""
import logging
import time
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.core.auth import require_api_key
from app.models.jasper_schema import JasperProject, OptimizationOptions
from app.models.results import OptimizationResult

logger = logging.getLogger(__name__)
router = APIRouter()


class DecisionVariable(BaseModel):
    """A decision variable for optimization."""
    unit_id: str
    parameter: str
    lower_bound: Optional[float] = None
    upper_bound: Optional[float] = None
    initial_value: Optional[float] = None


class Constraint(BaseModel):
    """An optimization constraint."""
    type: str  # 'max', 'min', or 'equality'
    unit_id: str
    parameter: str
    bound: float


class OptimizeRequest(BaseModel):
    """Request body for optimization endpoint."""
    project: JasperProject
    objective: dict  # {metric: "COM", sense: "minimize"}
    decision_variables: list[DecisionVariable]
    constraints: Optional[list[Constraint]] = None
    options: Optional[OptimizationOptions] = None


class OptimizeResponse(BaseModel):
    """Response body for optimization endpoint."""
    status: str
    converged: bool
    solver_status: str
    iterations: int
    solve_time: float
    objective_value: float
    optimal_variables: dict
    streams: list
    units: list
    messages: list[str]


@router.post("/optimize", response_model=OptimizeResponse)
async def run_optimization(request: OptimizeRequest, _key: str = Depends(require_api_key)):
    """
    Run process optimization using IDAES.

    Builds model, adds objective function and constraints,
    solves optimization problem, and returns results.
    """
    start_time = time.time()
    messages = []

    try:
        from app.core.model_builder import IdaesModelBuilder
        from app.core.result_extractor import ResultExtractor
        from pyomo.environ import Objective, minimize, maximize

        # Build IDAES model
        builder = IdaesModelBuilder(request.project)
        model = builder.build()
        messages.append("Model built successfully")

        # Initialize the model FIRST while decision variables are still
        # fixed at their default spec values. This gives IDAES a feasible
        # starting point — initialization on a model with unfixed variables
        # is fragile and tends to land outside reasonable bounds.
        builder.initialize()
        messages.append("Model initialized")

        # Now unfix decision variables and apply bounds + initial guess.
        # Note: a Pyomo Var is truthy in expression contexts, so we MUST
        # use `is not None` here, not `if var:`.
        for dv in request.decision_variables:
            var = builder.get_variable(dv.unit_id, dv.parameter)
            if var is None:
                messages.append(
                    f"Warning: decision variable {dv.unit_id}.{dv.parameter} "
                    f"not found on the model"
                )
                continue
            var.unfix()
            if dv.lower_bound is not None:
                var.setlb(dv.lower_bound)
            if dv.upper_bound is not None:
                var.setub(dv.upper_bound)
            if dv.initial_value is not None:
                var.set_value(dv.initial_value)
            elif var.value is not None:
                # If caller didn't supply an initial guess, clamp the
                # initialize-derived value into the bounds so IPOPT
                # starts feasible.
                lb = var.lb if dv.lower_bound is None else dv.lower_bound
                ub = var.ub if dv.upper_bound is None else dv.upper_bound
                v = var.value
                if lb is not None and v < lb:
                    var.set_value(lb)
                elif ub is not None and v > ub:
                    var.set_value(ub)

        # Add objective function.
        #
        # Two accepted shapes:
        #   1. {"metric": "total_cost"|"COM"|"total_duty"|"total_work",
        #       "sense": "minimize"|"maximize"}                  (legacy)
        #   2. {"unit_id": "H1", "parameter": "duty",
        #       "sense": "minimize"|"maximize"}                  (per-variable)
        obj_sense = request.objective.get('sense', 'minimize')
        if 'unit_id' in request.objective and 'parameter' in request.objective:
            obj_arg = {
                "unit_id": request.objective['unit_id'],
                "parameter": request.objective['parameter'],
            }
            obj_label = f"{obj_arg['unit_id']}.{obj_arg['parameter']}"
        else:
            obj_arg = request.objective.get('metric', 'total_cost')
            obj_label = obj_arg

        obj_expr = builder.build_objective_expression(obj_arg)
        sense = minimize if obj_sense == 'minimize' else maximize
        model.optimization_objective = Objective(expr=obj_expr, sense=sense)
        messages.append(f"Objective: {obj_sense} {obj_label}")

        # Apply constraints
        from pyomo.environ import Constraint as PyomoConstraint

        if request.constraints:
            for i, con in enumerate(request.constraints):
                var = builder.get_variable(con.unit_id, con.parameter)
                if var is None:
                    messages.append(f"Warning: constraint variable {con.unit_id}.{con.parameter} not found")
                    continue
                if con.type == 'max':
                    setattr(model, f"opt_con_{i}", PyomoConstraint(expr=var <= con.bound))
                elif con.type == 'min':
                    setattr(model, f"opt_con_{i}", PyomoConstraint(expr=var >= con.bound))
                elif con.type == 'equality':
                    setattr(model, f"opt_con_{i}", PyomoConstraint(expr=var == con.bound))

        # Solve (initialization happened above, before unfixing).
        options = request.options or OptimizationOptions()
        result = builder.solve(
            solver=options.solver,
            max_iterations=options.max_iterations,
            tolerance=options.tolerance
        )

        solve_time = time.time() - start_time

        # Extract results
        extractor = ResultExtractor(model, builder.unit_map, builder.arc_map)

        optimal_vars = {}
        for dv in request.decision_variables:
            var = builder.get_variable(dv.unit_id, dv.parameter)
            if var is not None and var.value is not None:
                optimal_vars[f"{dv.unit_id}.{dv.parameter}"] = float(var.value)

        converged = str(result.solver.termination_condition) == "optimal"

        return OptimizeResponse(
            status="success" if converged else "warning",
            converged=converged,
            solver_status=str(result.solver.termination_condition),
            iterations=result.solver.iterations if hasattr(result.solver, 'iterations') else 0,
            solve_time=solve_time,
            objective_value=float(model.optimization_objective()),
            optimal_variables=optimal_vars,
            streams=extractor.extract_streams(),
            units=extractor.extract_units(),
            messages=messages
        )

    except Exception as e:
        logger.error("Optimization failed: %s", e, exc_info=True)
        raise HTTPException(
            status_code=500,
            detail={"error": "Optimization failed. Please check your model and try again."},
        )
