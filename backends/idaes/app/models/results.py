"""Result models for simulation and optimization outputs."""
from typing import Optional, Any
from pydantic import BaseModel, Field


class StreamResult(BaseModel):
    """Results for a process stream."""
    id: str
    from_node: str
    to_node: str
    temperature: float  # K
    pressure: float  # Pa
    flow_mol: float  # mol/s
    flow_mass: float  # kg/s
    phase: str  # V, L, VL
    vapor_fraction: float
    composition: dict[str, float]  # component -> mole fraction
    enthalpy: Optional[float] = None  # J/mol
    entropy: Optional[float] = None  # J/mol/K
    density: Optional[float] = None  # kg/m3
    molecular_weight: float  # g/mol


class UnitResult(BaseModel):
    """Results for a unit operation."""
    id: str
    name: str
    type: str
    duty: Optional[float] = None  # W
    work: Optional[float] = None  # W
    pressure_drop: Optional[float] = None  # Pa
    efficiency: Optional[float] = None
    custom_results: dict[str, Any] = Field(default_factory=dict)


class SimulationResult(BaseModel):
    """Complete simulation results."""
    status: str
    converged: bool
    solver_status: str
    iterations: int
    solve_time: float
    streams: list[StreamResult]
    units: list[UnitResult]
    degrees_of_freedom: int
    messages: list[str]


class OptimizationResult(BaseModel):
    """Complete optimization results."""
    status: str
    converged: bool
    solver_status: str
    iterations: int
    solve_time: float
    objective_value: float
    optimal_variables: dict[str, float]
    streams: list[StreamResult]
    units: list[UnitResult]
    messages: list[str]


class DiagnosticsResult(BaseModel):
    """Model diagnostics information."""
    degrees_of_freedom: int
    n_variables: int
    n_constraints: int
    n_objectives: int
    warnings: list[str]
    structural_issues: list[str]
    numerical_issues: list[str]
