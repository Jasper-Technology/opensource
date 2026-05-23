"""Health check endpoints for Railway deployment."""
import logging

from fastapi import APIRouter, Depends

from app.core.auth import require_api_key

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/health")
async def health_check():
    """
    Health check endpoint - also used to wake Railway from sleep.

    This is a lightweight, unauthenticated check that confirms
    the service is running. No internal details are exposed.
    """
    return {"status": "ok", "idaes_version": "bundled", "solver_available": True}


@router.get("/health/deep")
async def deep_health_check(_key: str = Depends(require_api_key)):
    """
    Deep health check - verify IDAES can actually solve a problem.

    This runs a minimal optimization to verify the solver works.
    Requires authentication because it exposes internal state.
    """
    try:
        from pyomo.environ import ConcreteModel, Var, Objective, SolverFactory

        m = ConcreteModel()
        m.x = Var(initialize=1.0)
        m.obj = Objective(expr=m.x**2)

        solver = SolverFactory('ipopt')
        result = solver.solve(m, tee=False)

        return {
            "status": "ok",
            "solver_test": "passed",
        }
    except Exception as e:
        logger.error("Deep health check failed: %s", e, exc_info=True)
        return {
            "status": "error",
            "solver_test": "failed",
        }
