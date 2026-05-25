"""
IDAES Model Builder

Converts Jasper project schema to IDAES Pyomo models.
"""
import logging
from collections import deque
from typing import Optional, Any

from pyomo.environ import ConcreteModel, TransformationFactory, SolverFactory

from app.models.jasper_schema import JasperProject, FlowsheetNode

logger = logging.getLogger(__name__)


# ─── ParamValue unwrapper ──────────────────────────────────────────────

def _unwrap_param(param: Any) -> Any:
    """Unwrap a frontend ParamValue discriminated union into a plain value.

    Frontend sends params in formats like:
        { kind: 'quantity', q: { value: 350, unit: 'K' } }
        { kind: 'number',  x: 42 }
        { kind: 'int',     n: 5 }
        { kind: 'string',  s: 'foo' }
        { kind: 'boolean', b: true }
        { kind: 'enum',    e: 'isentropic' }
        { kind: 'composition', comp: { ... } }
    """
    if not isinstance(param, dict) or "kind" not in param:
        return param
    kind = param["kind"]
    if kind == "quantity":
        return param.get("q", param)
    elif kind == "number":
        return param.get("x", 0)
    elif kind == "int":
        return param.get("n", 0)
    elif kind == "string":
        return param.get("s", "")
    elif kind == "boolean":
        return param.get("b", False)
    elif kind == "enum":
        return param.get("e", "")
    elif kind == "composition":
        return param.get("comp", {})
    return param


# ─── Flow conversion helpers ──────────────────────────────────────────

_FLOW_TO_MOL_PER_S: dict[str, float] = {
    "mol/s": 1.0,
    "kmol/h": 1000.0 / 3600.0,
    "kmol/s": 1000.0,
    "kg/h": 1.0,  # needs MW — handled separately
    "lb/h": 1.0,  # needs MW — handled separately
}


def _convert_flow_to_mol_per_s(value: float, unit: str) -> float:
    """Convert a molar flow to mol/s.  Mass-based units are not supported here."""
    factor = _FLOW_TO_MOL_PER_S.get(unit)
    if factor is None:
        # Default: treat as kmol/h (most common in process engineering)
        return value * 1000.0 / 3600.0
    return value * factor


# ─── Main builder ─────────────────────────────────────────────────────

class IdaesModelBuilder:
    """Builds IDAES models from Jasper project schema."""

    def __init__(self, project: JasperProject):
        self.project = project
        self.model: Optional[ConcreteModel] = None
        self.unit_map: dict[str, Any] = {}  # Jasper ID -> IDAES unit
        self.arc_map: dict[str, Any] = {}   # Jasper edge ID -> IDAES Arc
        self.arc_phase_map: dict[str, str | None] = {}  # edge ID -> source port phase (V/L/None)
        self.arc_warnings: list[str] = []   # port-lookup failures surfaced to messages
        self.rxn_pkg: Optional[Any] = None  # IDAES reaction parameter block
        self.node_type_map: dict[str, str] = {
            n.id: n.type for n in project.flowsheet.nodes
        }

    def build(self) -> ConcreteModel:
        """Build complete IDAES model from Jasper project."""
        from idaes.core import FlowsheetBlock

        self.model = ConcreteModel()
        self.model.fs = FlowsheetBlock(dynamic=False)

        # Step 1: Create property package
        self._build_property_package()

        # Step 1b: Create reaction package (optional, only if project has reactions)
        self._build_reaction_package()

        # Step 2: Create unit models
        self._build_unit_models()

        # Step 3: Create arcs (connections)
        self._build_arcs()

        # Step 4: Apply feed specifications
        self._apply_feed_specs()

        # Step 5: Apply unit parameters
        self._apply_unit_params()

        return self.model

    def _build_property_package(self):
        """Create property package based on Jasper thermodynamics config."""
        from app.idaes_wrapper.property_packages import create_property_package

        thermo_config = self.project.thermodynamics
        components = self.project.components

        self.model.fs.properties = create_property_package(
            property_method=thermo_config.propertyMethod,
            components=[c.formula or c.name for c in components],
            eos=thermo_config.eos,
            activity_model=thermo_config.activityModel
        )

    def _build_reaction_package(self):
        """Create IDAES reaction package if project defines reactions.

        Only builds the package if the project has a non-empty list of
        reactions. Stores the resulting block on self.model.fs.reactions
        and self.rxn_pkg for downstream use by reactor unit models.
        """
        reactions = getattr(self.project, "reactions", None) or []
        if not reactions:
            return

        from app.idaes_wrapper.reaction_packages import build_reaction_package

        # Convert pydantic Reaction models to plain dicts for the builder
        rxn_dicts = [r.model_dump() if hasattr(r, "model_dump") else dict(r) for r in reactions]

        try:
            rxn_block = build_reaction_package(self.model.fs.properties, rxn_dicts)
        except Exception as e:
            msg = f"Failed to build reaction package: {e}"
            logger.warning(msg)
            self.arc_warnings.append(msg)
            return

        if rxn_block is None:
            return

        self.model.fs.reactions = rxn_block
        self.rxn_pkg = rxn_block

    _REACTOR_TYPES = frozenset({"RCSTR", "RPfr", "REquil", "RGibbs"})

    def _build_unit_models(self):
        """Create IDAES unit models for each Jasper node."""
        from app.idaes_wrapper.unit_models import create_unit_model

        for node in self.project.flowsheet.nodes:
            if node.type == 'TextBox':
                continue

            rxn_pkg = self.rxn_pkg if node.type in self._REACTOR_TYPES else None

            unit = create_unit_model(
                flowsheet=self.model.fs,
                unit_type=node.type,
                unit_id=node.id,
                unit_name=node.name,
                property_package=self.model.fs.properties,
                params=node.params,
                reaction_package=rxn_pkg,
            )

            if unit is not None:
                self.unit_map[node.id] = unit
                setattr(self.model.fs, f"unit_{node.id}", unit)

    def _build_arcs(self):
        """Create IDAES Arcs for each Jasper stream edge."""
        from pyomo.network import Arc
        from app.data.unit_definitions import UNIT_DEFINITIONS

        # Build a node_id → unit_type lookup so _get_port can do per-type mapping
        node_type_map = {n.id: n.type for n in self.project.flowsheet.nodes}

        for edge in self.project.flowsheet.edges:
            source_unit = self.unit_map.get(edge.from_.nodeId)
            dest_unit = self.unit_map.get(edge.to.nodeId)

            if not source_unit or not dest_unit:
                continue

            source_type = node_type_map.get(edge.from_.nodeId)
            dest_type = node_type_map.get(edge.to.nodeId)

            source_port = self._get_port(source_unit, edge.from_.portName, 'out', unit_type=source_type)
            dest_port = self._get_port(dest_unit, edge.to.portName, 'in', unit_type=dest_type)

            if source_port and dest_port:
                arc = Arc(source=source_port, destination=dest_port)
                self.arc_map[edge.id] = arc
                setattr(self.model.fs, f"arc_{edge.id}", arc)

                # Store source port phase from unit_definitions for result extraction
                phase = None
                if source_type and source_type in UNIT_DEFINITIONS:
                    for port_def in UNIT_DEFINITIONS[source_type].get("ports", []):
                        if port_def.get("name") == edge.from_.portName:
                            phase = port_def.get("phase")
                            break
                self.arc_phase_map[edge.id] = phase
            else:
                # Surface the failure in arc_warnings so simulate.py can add it to messages
                src_attrs = sorted([a for a in dir(source_unit) if not a.startswith('_')]) if source_unit else []
                dst_attrs = sorted([a for a in dir(dest_unit) if not a.startswith('_')]) if dest_unit else []
                self.arc_warnings.append(
                    f"Arc {edge.id} skipped: "
                    f"src_port='{edge.from_.portName}'(found={source_port is not None}, "
                    f"unit_type={source_type}, available={[a for a in src_attrs if 'outlet' in a.lower() or 'inlet' in a.lower() or 'port' in a.lower()]}), "
                    f"dst_port='{edge.to.portName}'(found={dest_port is not None}, "
                    f"unit_type={dest_type}, available={[a for a in dst_attrs if 'outlet' in a.lower() or 'inlet' in a.lower() or 'port' in a.lower()]})"
                )

        # Expand arcs to create equality constraints
        TransformationFactory('network.expand_arcs').apply_to(self.model)

    def _get_port(self, unit, port_name: str, direction: str, unit_type: str = None):
        """Get IDAES port from unit model.

        Looks up the IDAES attribute name from UNIT_DEFINITIONS using the
        per-unit-type port definition. This avoids collisions where different
        unit types share the same frontend port name (e.g. Flash and
        DistillationColumn both have a 'vapor' port but different IDAES attrs).
        """
        from app.data.unit_definitions import UNIT_DEFINITIONS

        idaes_attr = port_name  # default: try the name as-is

        # Per-unit-type lookup (preferred)
        if unit_type and unit_type in UNIT_DEFINITIONS:
            for port_def in UNIT_DEFINITIONS[unit_type].get("ports", []):
                if port_def.get("name") == port_name:
                    idaes_attr = port_def.get("idaes_attr", port_name)
                    break

        port = getattr(unit, idaes_attr, None)

        # Generic fallbacks for HeatExchanger when user draws 'in'/'out'
        if port is None and port_name == 'in':
            port = getattr(unit, 'hot_side_inlet', None)
        if port is None and port_name == 'out':
            port = getattr(unit, 'hot_side_outlet', None)

        if port is None:
            logger.warning(
                "Port '%s' not found on %s unit (tried IDAES attr '%s'). "
                "Check app/data/unit_definitions.py for correct idaes_attr.",
                port_name, unit_type or type(unit).__name__, idaes_attr,
            )

        return port

    # ─── Feed specifications ──────────────────────────────────────────

    def _apply_feed_specs(self):
        """Apply feed stream specifications.

        Feed data can come from two places:
        1. Edge spec (StreamSpec with plain Quantity objects) — used by seed data
        2. Node params (ParamValue format from NodePanel UI) — used by user edits

        We try edge spec first, then fall back to node params.
        """
        for edge in self.project.flowsheet.edges:
            source_node = next(
                (n for n in self.project.flowsheet.nodes if n.id == edge.from_.nodeId),
                None
            )

            if not source_node or source_node.type != 'Feed':
                continue

            unit = self.unit_map.get(source_node.id)
            if not unit or not hasattr(unit, 'outlet'):
                continue

            # Try edge spec first
            if edge.spec:
                self._fix_stream_state(unit.outlet, edge.spec)
            else:
                # Fall back to node params (ParamValue format)
                self._fix_stream_from_node_params(unit.outlet, source_node.params)

    def _fix_stream_state(self, port, spec):
        """Fix state variables on a port based on Jasper StreamSpec.

        Port vars are time-indexed (e.g. flow_mol[0.0], mole_frac_comp[0.0, 'H2O']).
        We fix at time=0.0 for steady-state models.
        """
        state = port.vars

        if spec.T:
            T_kelvin = self._convert_temperature(spec.T.value, spec.T.unit)
            if 'temperature' in state:
                state['temperature'][0.0].fix(T_kelvin)

        if spec.P:
            P_pascal = self._convert_pressure(spec.P.value, spec.P.unit)
            if 'pressure' in state:
                state['pressure'][0.0].fix(P_pascal)

        if spec.flow:
            flow_mol_s = _convert_flow_to_mol_per_s(spec.flow.value, spec.flow.unit)
            if 'flow_mol' in state:
                state['flow_mol'][0.0].fix(flow_mol_s)

        if spec.composition:
            mf_var = state.get('mole_frac_comp')
            if mf_var is not None:
                for comp_id, mole_frac in spec.composition.items():
                    comp_name = self._resolve_component_name(comp_id)
                    key = (0.0, comp_name)
                    if key in mf_var:
                        mf_var[key].fix(mole_frac)

    def _fix_stream_from_node_params(self, port, params: dict):
        """Fix state variables from node params in ParamValue format."""
        state = port.vars

        if 'T' in params:
            raw = _unwrap_param(params['T'])
            if isinstance(raw, dict) and 'value' in raw:
                T_kelvin = self._convert_temperature(raw['value'], raw.get('unit', 'K'))
                if 'temperature' in state:
                    state['temperature'][0.0].fix(T_kelvin)

        if 'P' in params:
            raw = _unwrap_param(params['P'])
            if isinstance(raw, dict) and 'value' in raw:
                P_pascal = self._convert_pressure(raw['value'], raw.get('unit', 'bar'))
                if 'pressure' in state:
                    state['pressure'][0.0].fix(P_pascal)

        if 'flow' in params:
            raw = _unwrap_param(params['flow'])
            if isinstance(raw, dict) and 'value' in raw:
                flow_mol_s = _convert_flow_to_mol_per_s(
                    raw['value'], raw.get('unit', 'kmol/h')
                )
                if 'flow_mol' in state:
                    state['flow_mol'][0.0].fix(flow_mol_s)

        if 'composition' in params:
            comp_data = _unwrap_param(params['composition'])
            if isinstance(comp_data, dict):
                mf_var = state.get('mole_frac_comp')
                if mf_var is not None:
                    for comp_id, mole_frac in comp_data.items():
                        comp_name = self._resolve_component_name(comp_id)
                        if isinstance(mole_frac, dict):
                            mole_frac = mole_frac.get('value', mole_frac)
                        # mole_frac_comp is time-indexed: key is (0.0, comp_name)
                        key = (0.0, comp_name)
                        if key in mf_var:
                            mf_var[key].fix(float(mole_frac))

    # ─── Unit parameters ──────────────────────────────────────────────

    def _apply_unit_params(self):
        """Apply unit operation parameters."""
        for node in self.project.flowsheet.nodes:
            unit = self.unit_map.get(node.id)
            if not unit:
                continue

            params = node.params
            self._apply_params_for_type(unit, node.type, params)

    def _apply_params_for_type(self, unit, unit_type: str, params: dict):
        """Apply parameters based on unit type."""
        if unit_type in ('Heater', 'Cooler'):
            if 'outletT' in params:
                raw = _unwrap_param(params['outletT'])
                if isinstance(raw, dict) and 'value' in raw:
                    T_kelvin = self._convert_temperature(
                        raw['value'], raw.get('unit', 'C')
                    )
                else:
                    T_kelvin = self._convert_temperature(
                        self._get_param_value(params['outletT']), 'C'
                    )
                if hasattr(unit, 'outlet') and hasattr(unit.outlet, 'temperature'):
                    unit.outlet.temperature.fix(T_kelvin)

        elif unit_type == 'Pump':
            if 'dP' in params:
                raw = _unwrap_param(params['dP'])
                if isinstance(raw, dict) and 'value' in raw:
                    dP_Pa = self._convert_pressure(raw['value'], raw.get('unit', 'bar'))
                else:
                    dP_Pa = self._get_param_value(params['dP']) * 1e5
                if hasattr(unit, 'deltaP'):
                    unit.deltaP[0].fix(dP_Pa)

        elif unit_type == 'Flash':
            # Flash needs exactly 2 DOF specs.
            # Default: adiabatic (heat_duty=0) + isobaric (deltaP=0).
            # If user specifies outlet T, swap heat_duty for outlet T.
            has_T = 'T' in params

            if has_T and hasattr(unit, 'control_volume'):
                raw = _unwrap_param(params['T'])
                if isinstance(raw, dict) and 'value' in raw:
                    T_kelvin = self._convert_temperature(
                        raw['value'], raw.get('unit', 'K')
                    )
                else:
                    T_kelvin = self._get_param_value(params['T'])
                unit.control_volume.properties_out[0.0].temperature.fix(T_kelvin)
            else:
                # Adiabatic flash
                if hasattr(unit, 'heat_duty'):
                    unit.heat_duty[0].fix(0)

            # Fix pressure drop to zero (isobaric).
            # IDAES Flash.deltaP is an IndexedVar that causes IPOPT
            # evaluation errors when fixed directly. Instead, fix through
            # the control volume's pressure balance.
            try:
                if hasattr(unit, 'deltaP'):
                    unit.deltaP[0].fix(0)
            except Exception as exc:
                # Fallback: fix outlet pressure = inlet pressure via heat_duty only
                logger.debug("Could not fix Flash.deltaP[0]: %s — using heat_duty only", exc)

        elif unit_type == 'Splitter':
            if 'splitRatio' in params:
                raw = _unwrap_param(params['splitRatio'])
                if isinstance(raw, dict) and 'value' in raw:
                    ratio = float(raw['value'])
                else:
                    ratio = self._get_param_value(params['splitRatio'])
                if hasattr(unit, 'split_fraction'):
                    unit.split_fraction[0, 'outlet_1'].fix(ratio)
                    unit.split_fraction[0, 'outlet_2'].fix(1 - ratio)

        elif unit_type == 'Compressor':
            if 'outletP' in params:
                raw = _unwrap_param(params['outletP'])
                if isinstance(raw, dict) and 'value' in raw:
                    P_pascal = self._convert_pressure(
                        raw['value'], raw.get('unit', 'bar')
                    )
                else:
                    P_pascal = self._get_param_value(params['outletP']) * 1e5
                if hasattr(unit, 'outlet') and hasattr(unit.outlet, 'pressure'):
                    unit.outlet.pressure.fix(P_pascal)

        elif unit_type in ('DistillationColumn', 'Absorber', 'Stripper'):
            if 'refluxRatio' in params:
                raw = _unwrap_param(params['refluxRatio'])
                val = float(raw['value']) if isinstance(raw, dict) and 'value' in raw else self._get_param_value(params['refluxRatio'])
                if hasattr(unit, 'reflux_ratio'):
                    unit.reflux_ratio.fix(val)

    # ─── Converters ───────────────────────────────────────────────────

    def _convert_temperature(self, value: float, unit: str) -> float:
        """Convert temperature to Kelvin."""
        if unit == 'K':
            return value
        elif unit == 'C':
            return value + 273.15
        elif unit == 'F':
            return (value - 32) * 5 / 9 + 273.15
        return value + 273.15  # Default assume Celsius

    def _convert_pressure(self, value: float, unit: str) -> float:
        """Convert pressure to Pascal."""
        conversions = {
            'Pa': 1,
            'kPa': 1e3,
            'MPa': 1e6,
            'bar': 1e5,
            'atm': 101325,
            'psi': 6894.76,
        }
        return value * conversions.get(unit, 1e5)

    def _get_param_value(self, param) -> float:
        """Extract numeric value from parameter (handles Quantity objects)."""
        unwrapped = _unwrap_param(param)
        if isinstance(unwrapped, dict):
            return float(unwrapped.get('value', 0))
        return float(unwrapped)

    def _resolve_component_name(self, comp_id: str) -> str:
        """Resolve component ID to IDAES-compatible name (formula)."""
        for comp in self.project.components:
            if comp.id == comp_id:
                return comp.formula or comp.name
        return comp_id

    # ─── Recycle / tear-stream helpers ──────────────────────────────────

    def _identify_tear_streams(self) -> list[str]:
        """Identify tear streams in recycle loops.

        Returns edge IDs that form backward edges (i.e. edges whose
        destination appears before its source in topological order).
        These are the "tear streams" where Wegstein acceleration is applied.
        """
        topo = self._topological_order()
        rank = {uid: i for i, uid in enumerate(topo)}

        tears: list[str] = []
        for edge in self.project.flowsheet.edges:
            src = edge.from_.nodeId
            dst = edge.to.nodeId
            if src in rank and dst in rank and rank[dst] <= rank[src]:
                tears.append(edge.id)
        return tears

    def _solve_with_wegstein(
        self,
        solver_obj,
        tear_ids: list[str],
        max_outer: int = 20,
        tol: float = 1e-4,
    ):
        """Iterative Wegstein acceleration for recycle loops.

        For each tear stream, stores the molar flow and temperature as
        the "guess" variable, solves the full model, reads back the new
        values, and applies the Wegstein update:
            q = (x_new - x_old) / (x_old - x_prev)
            x_next = x_new + q / (1 - q) * (x_new - x_old)

        Falls back to direct solve if Wegstein diverges.
        """
        from pyomo.environ import value as pyo_value, TerminationCondition

        # Collect tear ports (source side of tear arcs)
        tear_ports = []
        for eid in tear_ids:
            arc = self.arc_map.get(eid)
            if arc is not None:
                tear_ports.append(arc.source)

        if not tear_ports:
            # No tear streams — just solve directly
            return solver_obj.solve(self.model, tee=False, load_solutions=False)

        def _read_tear_values() -> list[float]:
            vals = []
            for port in tear_ports:
                pvars = port.vars
                t_var = pvars.get('temperature')
                f_var = pvars.get('flow_mol')
                if t_var:
                    try:
                        vals.append(float(pyo_value(t_var[0.0])))
                    except Exception:
                        vals.append(300.0)
                if f_var:
                    try:
                        vals.append(float(pyo_value(f_var[0.0])))
                    except Exception:
                        vals.append(1.0)
            return vals

        x_prev = _read_tear_values()
        result = solver_obj.solve(self.model, tee=False, load_solutions=False)

        # Check if it converged on the first try
        if result.solver.termination_condition in (
            TerminationCondition.optimal,
            TerminationCondition.locallyOptimal,
            TerminationCondition.feasible,
        ):
            self.model.solutions.load_from(result)
            return result

        # Wegstein outer loop
        self.model.solutions.load_from(result)
        x_old = x_prev
        x_new = _read_tear_values()

        for iteration in range(max_outer):
            # Wegstein update (skip acceleration on iter 0 — use direct substitution)
            if iteration == 0:
                x_next = list(x_new)
            else:
                x_next = []
                for j in range(len(x_new)):
                    dx = x_new[j] - x_old[j]
                    dx_prev = x_old[j] - (x_prev[j] if len(x_prev) > j else x_old[j])
                    if abs(dx - dx_prev) > 1e-12:
                        q = dx / (dx - dx_prev)
                        # Bound q to prevent wild extrapolation
                        q = max(-5.0, min(q, 0.0))
                        x_next.append(x_new[j] + q / (1.0 - q) * dx)
                    else:
                        x_next.append(x_new[j])

            # Write updated guesses back to tear ports
            idx = 0
            for port in tear_ports:
                pvars = port.vars
                t_var = pvars.get('temperature')
                f_var = pvars.get('flow_mol')
                if t_var and idx < len(x_next):
                    try:
                        t_var[0.0].set_value(x_next[idx])
                    except Exception:
                        pass
                    idx += 1
                if f_var and idx < len(x_next):
                    try:
                        f_var[0.0].set_value(x_next[idx])
                    except Exception:
                        pass
                    idx += 1

            x_prev = x_old
            x_old = x_new

            result = solver_obj.solve(self.model, tee=False, load_solutions=False)
            if result.solver.termination_condition in (
                TerminationCondition.optimal,
                TerminationCondition.locallyOptimal,
                TerminationCondition.feasible,
            ):
                self.model.solutions.load_from(result)
                logger.info(
                    "Wegstein converged after %d outer iterations", iteration + 1
                )
                return result

            self.model.solutions.load_from(result)
            x_new = _read_tear_values()

            # Convergence check
            max_change = max(
                abs(a - b) / max(abs(a), 1.0)
                for a, b in zip(x_new, x_old)
            )
            if max_change < tol:
                logger.info(
                    "Wegstein tear values converged (max_change=%.2e) after %d iters",
                    max_change, iteration + 1,
                )
                return result

        logger.warning("Wegstein did not converge after %d outer iterations", max_outer)
        return result

    # ─── Initialization (topological sort) ────────────────────────────

    def _topological_order(self) -> list[str]:
        """Return unit IDs in topological order using Kahn's algorithm.

        Edges define the DAG.  If the graph has cycles (recycle loops),
        the remaining units are appended in definition order — IPOPT will
        handle the recycle equations.
        """
        # Build adjacency from edges
        in_degree: dict[str, int] = {uid: 0 for uid in self.unit_map}
        successors: dict[str, list[str]] = {uid: [] for uid in self.unit_map}

        for edge in self.project.flowsheet.edges:
            src = edge.from_.nodeId
            dst = edge.to.nodeId
            if src in self.unit_map and dst in self.unit_map:
                in_degree[dst] = in_degree.get(dst, 0) + 1
                successors.setdefault(src, []).append(dst)

        queue: deque[str] = deque(uid for uid, deg in in_degree.items() if deg == 0)
        order: list[str] = []

        while queue:
            uid = queue.popleft()
            order.append(uid)
            for succ in successors.get(uid, []):
                in_degree[succ] -= 1
                if in_degree[succ] == 0:
                    queue.append(succ)

        # Append any remaining (cycle members) in original order
        remaining = [uid for uid in self.unit_map if uid not in set(order)]
        order.extend(remaining)

        return order

    def initialize(self):
        """Initialize the IDAES model in topological order."""
        from idaes.core.util.model_statistics import degrees_of_freedom

        dof = degrees_of_freedom(self.model)
        if dof != 0:
            logger.warning("Model has %d degrees of freedom", dof)

        order = self._topological_order()

        for unit_id in order:
            unit = self.unit_map[unit_id]
            if hasattr(unit, 'initialize'):
                try:
                    unit.initialize()
                except Exception as e:
                    logger.warning("Failed to initialize unit %s: %s", unit_id, e)

            # Propagate state to downstream arcs
            self._propagate_from(unit_id)

    def _propagate_from(self, unit_id: str):
        """Propagate state from unit's outlet ports to connected inlets."""
        try:
            from idaes.core.util.initialization import propagate_state
        except ImportError:
            return

        for edge in self.project.flowsheet.edges:
            if edge.from_.nodeId == unit_id:
                arc = self.arc_map.get(edge.id)
                if arc is not None:
                    try:
                        propagate_state(arc)
                    except Exception:
                        pass

    def solve(self, solver: str = 'ipopt', max_iterations: int = 100, tolerance: float = 1e-6):
        """Solve the model.

        If the flowsheet contains recycle loops (tear streams), uses
        Wegstein acceleration with an outer iteration. Otherwise does a
        single IPOPT solve.
        """
        solver_obj = SolverFactory(solver)

        if solver == 'ipopt':
            solver_obj.options['max_iter'] = max_iterations
            solver_obj.options['tol'] = tolerance

        # Check for recycle loops and use Wegstein if present
        tear_ids = self._identify_tear_streams()
        if tear_ids:
            logger.info("Detected %d tear stream(s): %s", len(tear_ids), tear_ids)
            return self._solve_with_wegstein(solver_obj, tear_ids)

        # No recycles — standard single solve.
        # load_solutions=False prevents Pyomo from crashing with ValueError
        # when IPOPT returns a non-optimal status. We load solutions manually
        # only if the solve succeeded.
        result = solver_obj.solve(self.model, tee=False, load_solutions=False)

        from pyomo.environ import TerminationCondition
        if result.solver.termination_condition == TerminationCondition.optimal:
            self.model.solutions.load_from(result)
        elif result.solver.termination_condition in (
            TerminationCondition.locallyOptimal,
            TerminationCondition.feasible,
        ):
            self.model.solutions.load_from(result)

        return result

    # ─── Optimization helpers ─────────────────────────────────────────

    # Allowed attribute segments for decision variable lookup.
    ALLOWED_VARIABLE_PARTS = frozenset({
        "inlet", "outlet", "vapor_outlet", "liquid_outlet",
        "hot_side_inlet", "hot_side_outlet", "cold_side_inlet", "cold_side_outlet",
        "control_volume", "properties_in", "properties_out",
        "temperature", "pressure", "flow_mol", "mole_frac_comp",
        "heat_duty", "deltaP", "split_fraction", "enth_mol",
        "work_mechanical", "efficiency_isentropic",
    })

    # Frontend-facing param name → internal IDAES attribute path, per unit type.
    # Lets the caller speak the same vocabulary as /api/units (T, P, duty, …)
    # without knowing the underlying Pyomo attribute names.
    PARAM_ALIASES: dict[str, dict[str, str]] = {
        "Feed":        {"T": "outlet.temperature", "P": "outlet.pressure",
                        "flow": "outlet.flow_mol"},
        "Heater":      {"T": "outlet.temperature", "outletT": "outlet.temperature",
                        "P": "outlet.pressure",
                        "duty": "heat_duty", "Q": "heat_duty"},
        "Cooler":      {"T": "outlet.temperature", "outletT": "outlet.temperature",
                        "P": "outlet.pressure",
                        "duty": "heat_duty", "Q": "heat_duty"},
        "Flash":       {"T": "control_volume.properties_out.temperature",
                        "P": "control_volume.properties_out.pressure",
                        "duty": "heat_duty", "Q": "heat_duty"},
        "Pump":        {"dP": "deltaP", "deltaP": "deltaP",
                        "outletP": "outlet.pressure",
                        "work": "work_mechanical", "W": "work_mechanical",
                        "efficiency": "efficiency_isentropic"},
        "Compressor":  {"dP": "deltaP", "deltaP": "deltaP",
                        "outletP": "outlet.pressure",
                        "T": "outlet.temperature",
                        "work": "work_mechanical", "W": "work_mechanical",
                        "efficiency": "efficiency_isentropic"},
        "Valve":       {"dP": "deltaP", "deltaP": "deltaP",
                        "outletP": "outlet.pressure"},
    }

    def _resolve_param_path(self, unit_id: str, parameter: str) -> Optional[str]:
        """Map a frontend param name to a dotted attribute path, or return
        the parameter as-is if it's already a valid path."""
        unit_type = self.node_type_map.get(unit_id)
        alias_table = self.PARAM_ALIASES.get(unit_type or "", {})
        return alias_table.get(parameter, parameter)

    def get_variable(self, unit_id: str, parameter: str):
        """Get a Pyomo scalar variable from a unit for optimization.

        Accepts either:
          - a frontend param name (T, P, duty, dP, work, flow, outletT, outletP)
            which is mapped via PARAM_ALIASES per unit type, or
          - a raw dotted attribute path (e.g. "outlet.temperature",
            "heat_duty"), traversed against the IDAES unit.

        Resulting attribute may be an IndexedVar (e.g. unit.heat_duty), in
        which case the time-0 element is returned so the caller always gets
        a scalar suitable for unfix(), setlb(), setub(), set_value(), and
        use in objective/constraint expressions.

        Only attribute names in ALLOWED_VARIABLE_PARTS may be traversed
        to prevent arbitrary attribute access on internal model objects.
        """
        unit = self.unit_map.get(unit_id)
        if not unit:
            return None

        path = self._resolve_param_path(unit_id, parameter)
        if path is None:
            return None

        parts = path.split('.')
        if not all(p in self.ALLOWED_VARIABLE_PARTS for p in parts):
            return None

        obj = unit
        for part in parts:
            obj = getattr(obj, part, None)
            if obj is None:
                return None

        # If we landed on an IndexedVar (e.g. unit.heat_duty indexed by time),
        # return the time-0 scalar so callers can call .unfix()/.setlb()/etc.
        try:
            from pyomo.core.base.var import IndexedVar
            if isinstance(obj, IndexedVar):
                try:
                    return obj[0]
                except KeyError:
                    # Some IndexedVars use different index sets; grab the first.
                    first_key = next(iter(obj), None)
                    if first_key is not None:
                        return obj[first_key]
                    return None
        except ImportError:
            pass

        return obj

    def build_objective_expression(self, metric):
        """Build objective expression for optimization.

        Accepts either:
          - a named metric string ("total_duty", "total_work", "COM",
            "total_cost") — legacy behavior, sums across the flowsheet, or
          - a dict {"unit_id": str, "parameter": str} — the value of the
            referenced decision variable (resolved via get_variable).

        Returns a Pyomo expression suitable for use as Objective(expr=...).
        Raises ValueError if the variable can't be resolved.
        """
        if isinstance(metric, dict):
            unit_id = metric.get("unit_id")
            parameter = metric.get("parameter")
            if not unit_id or not parameter:
                raise ValueError(
                    "objective dict must include 'unit_id' and 'parameter'"
                )
            var = self.get_variable(unit_id, parameter)
            if var is None:
                raise ValueError(
                    f"objective variable {unit_id}.{parameter} could not be "
                    f"resolved on the model"
                )
            return var

        if metric == 'total_duty':
            duties = []
            for unit in self.unit_map.values():
                if hasattr(unit, 'heat_duty'):
                    duties.append(unit.heat_duty[0])
            return sum(duties) if duties else 0

        elif metric == 'total_work':
            works = []
            for unit in self.unit_map.values():
                if hasattr(unit, 'work_mechanical'):
                    works.append(unit.work_mechanical[0])
            return sum(works) if works else 0

        elif metric == 'COM':
            # Cost of Manufacture: steam_price * duty + elec_price * work
            steam_price = 14.0   # $/GJ  (typical utility cost)
            elec_price = 0.07    # $/kWh (typical utility cost)

            expr = 0
            for unit in self.unit_map.values():
                if hasattr(unit, 'heat_duty'):
                    # heat_duty is in W; convert to GJ/h → $/h
                    expr += steam_price * unit.heat_duty[0] * 3600 / 1e9
                if hasattr(unit, 'work_mechanical'):
                    # work_mechanical is in W; convert to kW → $/h
                    expr += elec_price * unit.work_mechanical[0] / 1e3
            return expr

        elif metric == 'total_cost':
            return self.build_objective_expression('COM')

        return 0
