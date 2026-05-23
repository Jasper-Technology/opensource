"""
Pydantic models matching Jasper's TypeScript schema.

These models define the structure of data exchanged between
the Jasper frontend and the IDAES backend.
"""
from typing import Optional, Any
from pydantic import BaseModel, Field, field_validator


# ============ Basic Types ============

class Quantity(BaseModel):
    """A value with units."""
    kind: str = "quantity"
    value: float
    unit: str


class PortReference(BaseModel):
    """Reference to a port on a node."""
    nodeId: str
    portName: str


# ============ Components ============

class Component(BaseModel):
    """Chemical component in the simulation."""
    id: str
    name: str
    formula: Optional[str] = None
    cas: Optional[str] = Field(None, alias="casNumber")

    class Config:
        populate_by_name = True


# ============ Thermodynamics ============

class ThermodynamicsConfig(BaseModel):
    """Thermodynamics configuration for the simulation."""
    propertyMethod: str = "Ideal"
    eos: Optional[str] = None  # SRK, PR
    activityModel: Optional[str] = None  # NRTL, UNIQUAC


# ============ Stream Spec ============

class StreamSpec(BaseModel):
    """Specification for a process stream."""
    T: Optional[Quantity] = None
    P: Optional[Quantity] = None
    flow: Optional[Quantity] = None
    composition: Optional[dict[str, float]] = None  # component_id -> mole fraction
    vaporFraction: Optional[float] = None
    phase: Optional[str] = None


# ============ Flowsheet Elements ============

class NodeParams(BaseModel):
    """Parameters for a unit operation node.

    Uses a dict[str, Any] field instead of extra="allow" so that
    arbitrary keys are still accepted but confined to a single field.
    """
    values: dict[str, Any] = Field(default_factory=dict)


class FlowsheetNode(BaseModel):
    """A unit operation node in the flowsheet."""
    id: str
    type: str  # Feed, Sink, Mixer, Flash, Heater, etc.
    name: str
    x: Optional[float] = None
    y: Optional[float] = None
    params: dict[str, Any] = Field(default_factory=dict)


class FlowsheetEdge(BaseModel):
    """A stream connection between nodes."""
    id: str
    from_: PortReference = Field(alias="from")
    to: PortReference
    spec: Optional[StreamSpec] = None
    label: Optional[str] = None

    class Config:
        populate_by_name = True


class Flowsheet(BaseModel):
    """The process flowsheet structure."""
    nodes: list[FlowsheetNode]
    edges: list[FlowsheetEdge]


# ============ Reactions ============

class ArrheniusKinetics(BaseModel):
    """Arrhenius rate law parameters: k = A * exp(-Ea / (R * T))."""
    A: float  # Pre-exponential factor
    Ea: float  # Activation energy (J/mol)
    T_ref: Optional[float] = None  # Reference temperature (K), optional


class Reaction(BaseModel):
    """A chemical reaction specification.

    stoichiometry maps component formula (e.g. 'H2O') to signed coefficient
    (negative for reactants, positive for products).
    """
    id: str
    stoichiometry: dict[str, float]
    type: str = "rate"  # 'rate' | 'equilibrium'
    rate_constant: Optional[float] = None
    equilibrium_constant: Optional[float] = None
    arrhenius: Optional[ArrheniusKinetics] = None
    concentration_orders: Optional[dict[str, float]] = None


# ============ Project ============

class JasperProject(BaseModel):
    """Complete Jasper project for simulation."""
    projectId: Optional[str] = None
    name: str
    thermodynamics: ThermodynamicsConfig = Field(default_factory=ThermodynamicsConfig)
    components: list[Component]
    flowsheet: Flowsheet
    reactions: Optional[list[Reaction]] = None


# ============ Simulation Options ============

ALLOWED_SOLVERS = frozenset({"ipopt"})


class SimulationOptions(BaseModel):
    """Options for simulation solver."""
    solver: str = "ipopt"
    # Capped at 1000 — anything higher implies a non-converging model and
    # would just lock up the solver without producing useful output.
    max_iterations: int = Field(default=100, ge=1, le=1000)
    tolerance: float = Field(default=1e-6, gt=0, le=1)
    tee: bool = False  # Print solver output

    @field_validator("solver")
    @classmethod
    def solver_must_be_allowed(cls, v: str) -> str:
        if v not in ALLOWED_SOLVERS:
            raise ValueError(f"Solver must be one of {sorted(ALLOWED_SOLVERS)}")
        return v


class OptimizationOptions(BaseModel):
    """Options for optimization solver."""
    solver: str = "ipopt"
    # Capped at 1000 — see note on SimulationOptions.max_iterations.
    max_iterations: int = Field(default=200, ge=1, le=1000)
    tolerance: float = Field(default=1e-6, gt=0, le=1)
    tee: bool = False

    @field_validator("solver")
    @classmethod
    def solver_must_be_allowed(cls, v: str) -> str:
        if v not in ALLOWED_SOLVERS:
            raise ValueError(f"Solver must be one of {sorted(ALLOWED_SOLVERS)}")
        return v
