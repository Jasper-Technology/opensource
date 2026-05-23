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

        # Unfix decision variables
        for dv in request.decision_variables:
            var = builder.get_variable(dv.unit_id, dv.parameter)
            if var:
                var.unfix()
                if dv.lower_bound is not None:
                    var.setlb(dv.lower_bound)
                if dv.upper_bound is not None:
                    var.setub(dv.upper_bound)
                if dv.initial_value is not None:
                    var.set_value(dv.initial_value)

        # Add objective function
        obj_metric = request.objective.get('metric', 'total_cost')
        obj_sense = request.objective.get('sense', 'minimize')

        obj_expr = builder.build_objective_expression(obj_metric)
        sense = minimize if obj_sense == 'minimize' else maximize
        model.optimization_objective = Objective(expr=obj_expr, sense=sense)
        messages.append(f"Objective: {obj_sense} {obj_metric}")

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

        # Initialize and solve
        builder.initialize()
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
            if var:
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
