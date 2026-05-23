"""API routes for Jasper IDAES Backend.

Intentionally does NOT eagerly import every route module — the full set
pulls in pyomo/idaes, which is heavy and unavailable in some dev/test
environments. ``app.main`` imports the specific routes it needs.
"""
__all__ = [
    "health",
    "simulate",
    "optimize",
    "properties",
    "components",
    "units",
    "jobs",
    "tea",
]
