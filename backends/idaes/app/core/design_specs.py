"""Design Spec Solver (Rigorous mode)

Implements AspenPlus-style "design specifications" by:
  1. Mapping each user-defined spec to a target expression on the IDAES model
  2. Picking a "handle" variable (e.g. reflux ratio, duty) to vary
  3. Unfixing the handle, adding `spec_expr == spec_target` as a Pyomo
     constraint, and letting IPOPT solve simultaneously (DOF stays 0).

Each spec is self-contained; multiple active specs are applied sequentially.

Frontend spec shape (from site/src/core/schema.ts):
    { id, type: 'purity',    streamId, component, target }
    { id, type: 'recovery',  component, feedStreamId, productStreamId, target }
    { id, type: 'capture',   component, ventStreamId, targetRemoval }

A spec may include an optional `vary: { unitId, param }` override.
"""
from __future__ import annotations

import logging
from typing import Any, Optional

from pyomo.environ import Constraint, value

logger = logging.getLogger(__name__)


# ─── Spec → handle default mapping ─────────────────────────────────────
#
# For each spec type, we look up the target unit and pick a sensible
# handle variable. Users may override via spec.vary.

# Default handle choices, in preference order.
_DEFAULT_HANDLES: dict[str, list[tuple[str, str]]] = {
    # (unit_type, attribute path relative to the unit)
    "DistillationColumn": [("reflux_ratio", ""), ("condenser", "heat_duty")],
    "Heater":             [("outlet", "temperature"), ("heat_duty", "")],
    "Cooler":             [("outlet", "temperature"), ("heat_duty", "")],
    "Pump":               [("deltaP", "")],
    "Compressor":         [("outlet", "pressure")],
    "Splitter":           [("split_fraction", "")],
    "Flash":              [("heat_duty", ""), ("outlet", "temperature")],
}


class DesignSpecError(Exception):
    """Raised when a design spec cannot be attached to the model."""


def _resolve_handle(unit: Any, attr_chain: tuple[str, str]):
    """Resolve a handle attribute chain to a Pyomo Var.

    attr_chain is a 2-tuple (parent_attr, child_attr). child_attr may be
    empty to indicate the parent is the target itself.

    Returns the indexed variable element (at index 0 or 0.0 where applicable)
    or None if it cannot be resolved.
    """
    parent_name, child_name = attr_chain
    obj = getattr(unit, parent_name, None)
    if obj is None:
        return None
    if child_name:
        obj = getattr(obj, child_name, None)
        if obj is None:
            return None

    # If the object is indexed (time or phase), try to grab [0] / [0.0]
    for idx in (0.0, 0):
        try:
            return obj[idx]
        except (KeyError, TypeError, IndexError):
            continue
    return obj


def _get_stream_composition_expr(arc, component: str):
    """Return a Pyomo expression for the mole fraction of `component` on arc.source.

    Returns None if the port does not expose mole_frac_comp.
    """
    port = arc.source
    vars_ = getattr(port, "vars", None)
    if vars_ is None:
        return None
    mf = vars_.get("mole_frac_comp")
    if mf is None:
        return None
    key = (0.0, component)
    if key in mf:
        return mf[key]
    # Try non-time-indexed form
    if component in mf:
        return mf[component]
    return None


def _get_stream_flow_expr(arc):
    """Return a Pyomo expression for total molar flow on arc.source, or None."""
    port = arc.source
    vars_ = getattr(port, "vars", None)
    if vars_ is None:
        return None
    flow = vars_.get("flow_mol")
    if flow is None:
        return None
    try:
        return flow[0.0]
    except (KeyError, TypeError):
        return flow


def _find_unit_owning_stream(builder, stream_id: str) -> Optional[str]:
    """Return the unit id whose outlet produces `stream_id` (the arc source).

    Uses the project's edges, since arc_map keys to edge IDs.
    """
    for edge in builder.project.flowsheet.edges:
        if edge.id == stream_id:
            return edge.from_.nodeId
    return None


def _select_handle(builder, spec: dict) -> Optional[tuple[str, Any]]:
    """Pick a handle variable for this spec.

    Returns (unit_id, pyomo_var) or None if no handle can be found.

    Honors an explicit `vary: { unitId, param }` on the spec first;
    otherwise falls back to _DEFAULT_HANDLES keyed on the owning unit
    type. `param` is interpreted as a dotted attr path (e.g.
    "outlet.temperature" or "heat_duty").
    """
    # 1) Explicit override from frontend
    vary = spec.get("vary") if isinstance(spec, dict) else None
    if isinstance(vary, dict) and vary.get("unitId"):
        unit_id = vary["unitId"]
        param = vary.get("param", "")
        unit = builder.unit_map.get(unit_id)
        if unit is None or not param:
            return None
        parts = param.split(".")
        if len(parts) > 2:
            logger.warning(
                "Design spec vary.param '%s' has >2 segments; only 2 supported. "
                "Truncating to '%s.%s'.", param, parts[0], parts[1],
            )
        attr_chain = (parts[0], parts[1] if len(parts) > 1 else "")
        var = _resolve_handle(unit, attr_chain)
        return (unit_id, var) if var is not None else None

    # 2) Default: find the unit that produces the target stream
    stream_id = (
        spec.get("streamId")
        or spec.get("productStreamId")
        or spec.get("ventStreamId")
    )
    if not stream_id:
        return None

    unit_id = _find_unit_owning_stream(builder, stream_id)
    if unit_id is None:
        return None

    # Look up unit type via the project
    node_type = None
    for n in builder.project.flowsheet.nodes:
        if n.id == unit_id:
            node_type = n.type
            break
    if node_type is None:
        return None

    unit = builder.unit_map.get(unit_id)
    if unit is None:
        return None

    for attr_chain in _DEFAULT_HANDLES.get(node_type, []):
        var = _resolve_handle(unit, attr_chain)
        if var is not None:
            return (unit_id, var)

    return None


def _build_spec_expr(builder, spec: dict):
    """Build the Pyomo expression whose value equals the spec's achieved value.

    Returns (expr, target) or None if the spec cannot be constructed.
    """
    spec_type = spec.get("type")

    if spec_type == "purity":
        stream_id = spec.get("streamId")
        component = spec.get("component")
        target = spec.get("target")
        if not stream_id or not component or target is None:
            return None
        arc = builder.arc_map.get(stream_id)
        if arc is None:
            return None
        expr = _get_stream_composition_expr(arc, component)
        if expr is None:
            return None
        return expr, float(target)

    if spec_type == "recovery":
        feed_id = spec.get("feedStreamId")
        prod_id = spec.get("productStreamId")
        comp = spec.get("component")
        if not feed_id or not prod_id or not comp:
            return None
        feed_arc = builder.arc_map.get(feed_id)
        prod_arc = builder.arc_map.get(prod_id)
        if feed_arc is None or prod_arc is None:
            return None
        feed_frac = _get_stream_composition_expr(feed_arc, comp)
        prod_frac = _get_stream_composition_expr(prod_arc, comp)
        feed_flow = _get_stream_flow_expr(feed_arc)
        prod_flow = _get_stream_flow_expr(prod_arc)
        if None in (feed_frac, prod_frac, feed_flow, prod_flow):
            return None
        # recovery = (prod_frac * prod_flow) / (feed_frac * feed_flow + eps)
        # Epsilon prevents division-by-zero during initialization
        expr = (prod_frac * prod_flow) / (feed_frac * feed_flow + 1e-10)
        return expr, float(spec["target"])

    if spec_type == "capture":
        vent_id = spec.get("ventStreamId")
        comp = spec.get("component")
        if not vent_id or not comp:
            return None
        vent_arc = builder.arc_map.get(vent_id)
        if vent_arc is None:
            return None
        # capture = 1 - vent_frac (normalized removal)
        vent_frac = _get_stream_composition_expr(vent_arc, comp)
        if vent_frac is None:
            return None
        expr = 1 - vent_frac
        return expr, float(spec["targetRemoval"])

    return None


def attach_design_specs(builder, specs: list[dict]) -> list[dict]:
    """Attach design specs to the model.

    For each spec, unfix a handle variable and add an equality constraint
    `expr == target`. Returns a list of attachment records:
        { specId, handleUnit, handleVar, target, status, reason? }

    A spec that cannot be attached (missing stream, no available handle,
    etc.) is recorded with status='skipped' and a reason.
    """
    records: list[dict] = []
    if not specs:
        return records

    model = builder.model

    for i, spec in enumerate(specs):
        spec_id = spec.get("id", f"spec_{i}")
        record: dict[str, Any] = {
            "specId": spec_id,
            "status": "skipped",
            "target": None,
        }

        # Build target expression
        built = _build_spec_expr(builder, spec)
        if built is None:
            record["reason"] = "could not build target expression (missing stream/port?)"
            records.append(record)
            continue
        expr, target = built
        record["target"] = target

        # Select handle
        handle = _select_handle(builder, spec)
        if handle is None:
            record["reason"] = "no handle variable available"
            records.append(record)
            continue
        handle_unit_id, handle_var = handle
        record["handleUnit"] = handle_unit_id
        record["handleVar"] = str(handle_var.name) if hasattr(handle_var, "name") else "unknown"

        # Unfix handle, add equality constraint
        try:
            if hasattr(handle_var, "fixed") and handle_var.fixed:
                handle_var.unfix()
        except Exception as exc:
            record["reason"] = f"could not unfix handle: {exc}"
            records.append(record)
            continue

        cons_name = f"design_spec_{spec_id.replace('-', '_')}"
        try:
            setattr(
                model.fs,
                cons_name,
                Constraint(expr=(expr == target)),
            )
        except Exception as exc:
            record["reason"] = f"could not add constraint: {exc}"
            records.append(record)
            continue

        record["status"] = "attached"
        record["constraint"] = cons_name
        records.append(record)

    return records


def evaluate_design_specs(records: list[dict], builder, specs: list[dict]) -> list[dict]:
    """Evaluate each attached spec post-solve and append achieved value + ok flag."""
    by_id = {s.get("id", ""): s for s in specs}
    out: list[dict] = []
    for r in records:
        r = dict(r)  # copy
        spec = by_id.get(r["specId"])
        if spec and r["status"] == "attached":
            try:
                built = _build_spec_expr(builder, spec)
                if built is not None:
                    expr, target = built
                    achieved = float(value(expr))
                    r["achieved"] = achieved
                    tol = 1e-3 * max(1.0, abs(target))
                    r["ok"] = abs(achieved - target) <= tol
                    r["target"] = target
            except Exception as exc:
                r["reason"] = f"evaluation failed: {exc}"
                r["ok"] = False
        out.append(r)
    return out
