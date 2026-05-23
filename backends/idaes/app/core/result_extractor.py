"""
Result Extractor

Extracts simulation results from solved IDAES models
and converts them to Jasper-compatible format.
"""
import logging
from typing import Any, Optional
from pyomo.environ import value

from app.models.results import StreamResult, UnitResult

logger = logging.getLogger(__name__)


# ─── Property extraction helpers ──────────────────────────────────────

# Phase labels IDAES uses for phase-indexed properties (e.g. enth_mol_phase['Liq']).
_PHASE_KEYS = ('Liq', 'Vap', 'Sol', 'Mix')


def _safe_prop(block, attr: str, default: Any = None) -> Optional[float]:
    """Safely read a thermodynamic property from a state block.

    Tries the scalar form (e.g. `enth_mol`) first, then the phase-indexed
    form (e.g. `enth_mol_phase['Liq']`) summing across phases weighted by
    phase fraction. Returns `default` if the property isn't available or
    evaluation fails (e.g. IDAES didn't construct the property).
    """
    if block is None:
        return default

    # 1. Try scalar form
    var = getattr(block, attr, None)
    if var is not None:
        try:
            val = value(var, exception=False)
            if val is not None:
                return float(val)
        except Exception:
            pass

    # 2. Try phase-indexed form (e.g. enth_mol_phase)
    phase_attr = f"{attr}_phase"
    phase_var = getattr(block, phase_attr, None)
    if phase_var is not None:
        try:
            # Try to weight by phase mole fraction if available
            phase_frac = getattr(block, 'phase_frac', None)
            total = 0.0
            total_weight = 0.0
            for key in phase_var.keys():
                # key may be 'Liq' or ('Liq',) or similar
                phase_name = key if isinstance(key, str) else (
                    key[-1] if isinstance(key, tuple) else str(key)
                )
                if phase_name not in _PHASE_KEYS:
                    continue
                v = value(phase_var[key], exception=False)
                if v is None:
                    continue
                if phase_frac is not None and key in phase_frac:
                    w = value(phase_frac[key], exception=False) or 0.0
                else:
                    w = 1.0
                total += float(v) * float(w)
                total_weight += float(w)
            if total_weight > 0:
                return total / total_weight
        except Exception:
            pass

    return default


class ResultExtractor:
    """Extracts results from solved IDAES models."""

    def __init__(self, model, unit_map: dict, arc_map: dict,
                 arc_phase_map: dict[str, str | None] | None = None):
        self.model = model
        self.unit_map = unit_map
        self.arc_map = arc_map
        self.arc_phase_map = arc_phase_map or {}

    def extract_streams(self) -> list[StreamResult]:
        """Extract stream results from all arcs."""
        streams = []

        for arc_id, arc in self.arc_map.items():
            try:
                stream = self._extract_stream_from_arc(arc_id, arc,
                                                        self.arc_phase_map.get(arc_id))
                if stream:
                    streams.append(stream)
            except Exception as e:
                logger.warning("Failed to extract stream %s: %s", arc_id, e)

        return streams

    def _extract_stream_from_arc(self, arc_id: str, arc,
                                  defined_phase: str | None = None) -> StreamResult:
        """Extract stream data from an IDAES Arc.

        Port variables are time-indexed (e.g. flow_mol[0.0]).
        We read values at time=0.0 for steady-state models.
        """
        port = arc.source
        port_vars = port.vars

        # Extract state variables from port vars (time-indexed)
        T = self._port_var_value(port_vars, 'temperature', 0.0, 298.15)
        P = self._port_var_value(port_vars, 'pressure', 0.0, 101325)
        flow_mol = self._port_var_value(port_vars, 'flow_mol', 0.0, 0)

        # Get composition — mole_frac_comp is indexed by (time, component)
        composition = {}
        mf = port_vars.get('mole_frac_comp')
        if mf is not None:
            for key in mf.keys():
                try:
                    # key is (0.0, 'H2O') — extract component name
                    comp_name = key[1] if isinstance(key, tuple) else str(key)
                    composition[comp_name] = value(mf[key])
                except Exception:
                    pass

        # MW is on the property block, not the port
        MW = 28.0
        try:
            props = port.parent_block()
            if hasattr(props, 'mw'):
                mw_var = props.mw
                # mw may be time-indexed — try [0.0] first, then direct
                try:
                    MW = value(mw_var[0.0]) * 1000  # kg/mol → g/mol
                except (KeyError, TypeError):
                    MW = value(mw_var) * 1000
        except Exception:
            pass

        flow_mass = flow_mol * MW / 1000  # mol/s * g/mol / 1000 = kg/s

        # Vapor fraction — try parent property block first, fall back to
        # port phase from unit_definitions.py
        vapor_frac = None
        try:
            props = port.parent_block()
            if hasattr(props, 'flow_mol_phase'):
                vap_flow = 0
                total_flow = 0
                for phase_key in props.flow_mol_phase.keys():
                    fval = value(props.flow_mol_phase[phase_key])
                    total_flow += fval
                    # Keys may be time-indexed tuples like (0.0, 'Vap') or plain 'Vap'
                    key_str = str(phase_key[-1]) if isinstance(phase_key, tuple) else str(phase_key)
                    if 'Vap' in key_str:
                        vap_flow += fval
                if total_flow > 1e-10:
                    vapor_frac = vap_flow / total_flow
        except Exception:
            pass

        # Fall back to phase declared in unit_definitions.py
        if vapor_frac is None and defined_phase == 'V':
            vapor_frac = 1.0
        elif vapor_frac is None and defined_phase == 'L':
            vapor_frac = 0.0
        elif vapor_frac is None:
            vapor_frac = 0.0

        phase = self._determine_phase(vapor_frac)

        # Extract real thermodynamic properties from the port's parent
        # property block. Fall back gracefully if IDAES didn't build them.
        props = None
        try:
            props = port.parent_block()
        except Exception:
            props = None

        enthalpy = _safe_prop(props, 'enth_mol', default=None)
        entropy = _safe_prop(props, 'entr_mol', default=None)

        density_mol = _safe_prop(props, 'dens_mol', default=None)  # mol/m³
        if density_mol is not None and density_mol > 0:
            # Convert molar density → mass density: mol/m³ * g/mol / 1000 = kg/m³
            density = density_mol * MW / 1000.0
        else:
            density = None

        from_node = str(arc.source.parent_block().name) if hasattr(arc.source, 'parent_block') else "unknown"
        to_node = str(arc.destination.parent_block().name) if hasattr(arc.destination, 'parent_block') else "unknown"

        return StreamResult(
            id=arc_id,
            from_node=from_node,
            to_node=to_node,
            temperature=T,
            pressure=P,
            flow_mol=flow_mol,
            flow_mass=flow_mass,
            phase=phase,
            vapor_fraction=vapor_frac,
            composition=composition,
            enthalpy=enthalpy,
            entropy=entropy,
            density=density,
            molecular_weight=MW
        )

    def _port_var_value(self, port_vars: dict, var_name: str, time_idx: float, default):
        """Get the value of a time-indexed port variable."""
        var = port_vars.get(var_name)
        if var is None:
            return default
        try:
            return value(var[time_idx])
        except Exception:
            return default

    def extract_units(self) -> list[UnitResult]:
        """Extract unit operation results."""
        units = []

        for unit_id, unit in self.unit_map.items():
            try:
                result = self._extract_unit_result(unit_id, unit)
                if result:
                    units.append(result)
            except Exception as e:
                logger.warning("Failed to extract unit %s: %s", unit_id, e)

        return units

    def _extract_unit_result(self, unit_id: str, unit) -> UnitResult:
        """Extract results from a single unit operation."""
        unit_type = type(unit).__name__
        unit_name = getattr(unit, 'name', unit_id)

        # Extract common results
        duty = None
        work = None
        pressure_drop = None
        efficiency = None
        custom_results = {}

        # Heat duty (heaters, coolers, heat exchangers)
        if hasattr(unit, 'heat_duty'):
            duty = self._safe_value(unit.heat_duty, 0, 0)

        # Work (pumps, compressors)
        if hasattr(unit, 'work_mechanical'):
            work = self._safe_value(unit.work_mechanical, 0, 0)
        elif hasattr(unit, 'work'):
            work = self._safe_value(unit, 'work', 0)

        # Pressure drop (valves, pressure changers)
        if hasattr(unit, 'deltaP'):
            pressure_drop = self._safe_value(unit, 'deltaP', 0)

        # Efficiency
        if hasattr(unit, 'efficiency_isentropic'):
            efficiency = self._safe_value(unit.efficiency_isentropic, 0, 0)
        elif hasattr(unit, 'efficiency'):
            efficiency = self._safe_value(unit, 'efficiency', 0)

        # Unit-specific results
        if hasattr(unit, 'vapor_reboil_ratio'):
            custom_results['vapor_reboil_ratio'] = self._safe_value(unit, 'vapor_reboil_ratio', 0)

        if hasattr(unit, 'reflux_ratio'):
            custom_results['reflux_ratio'] = self._safe_value(unit, 'reflux_ratio', 0)

        if hasattr(unit, 'split_fraction'):
            fractions = {}
            for idx in unit.split_fraction:
                fractions[str(idx)] = value(unit.split_fraction[idx])
            custom_results['split_fractions'] = fractions

        return UnitResult(
            id=unit_id,
            name=str(unit_name),
            type=unit_type,
            duty=duty,
            work=work,
            pressure_drop=pressure_drop,
            efficiency=efficiency,
            custom_results=custom_results
        )

    def _safe_value(self, obj, attr, default=0):
        """Safely extract value from Pyomo variable.

        When attr is a string, reads getattr(obj, attr). Otherwise treats
        obj as an indexed var and reads obj[attr].
        """
        try:
            if isinstance(attr, str):
                var = getattr(obj, attr, None)
                # If the result is an IndexedVar, try the time index
                if var is not None and hasattr(var, '__getitem__'):
                    try:
                        var = var[0.0]
                    except (KeyError, TypeError, IndexError):
                        try:
                            var = var[0]
                        except (KeyError, TypeError, IndexError):
                            pass
            else:
                var = obj[attr] if hasattr(obj, '__getitem__') else None

            if var is None:
                return default

            val = value(var)
            return val if val is not None else default
        except Exception:
            return default

    def _determine_phase(self, vapor_fraction: float) -> str:
        """Determine phase string from vapor fraction."""
        if vapor_fraction > 0.999:
            return 'V'
        elif vapor_fraction < 0.001:
            return 'L'
        else:
            return 'VL'
