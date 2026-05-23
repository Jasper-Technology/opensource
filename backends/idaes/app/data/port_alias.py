"""
Canonical port-name table and alias resolver.

Source of truth for port names across every layer of Jasper:
  - Frontend ReactFlow handles (``site/src/core/portAlias.ts``, mirror of this file)
  - ``unit_definitions.py`` — every ``PortDef.name`` MUST be a canonical name here
  - ``unit_models.py`` — maps canonical → IDAES attribute via ``unit_definitions``
  - DWSIM backend — maps canonical → port index via ``MapPortIndex``
  - Import parsers — normalize incoming names to canonical on ingest
  - Yjs legacy-data migration — rewrites legacy names to canonical

Any non-canonical name encountered on an already-persisted edge or a freshly
imported flowsheet must be resolvable through this module or fail loudly.

Design rules
------------
1. Canonical names are the frontend-visible names (shorter, kebab-case where
   natural). Backend attribute names (e.g. IDAES ``condenser_distillate``)
   are NOT canonical — they live in ``unit_definitions.py`` as ``idaes_attr``.
2. Aliases never shadow canonical names. If ``feed`` is canonical on
   ``DistillationColumn``, it is returned as-is; aliases only apply to units
   that do not carry that port.
3. Dynamic ports (``in1``…``inN``) are not listed here; they are resolved by
   pattern against the unit's port-spec. See ``resolve_dynamic``.
4. No silent fall-through. Unknown names raise ``UnknownPortError``.

Parity with the TS mirror is enforced by CI (see
``site/src/core/portAlias.test.ts``).
"""
from __future__ import annotations
import re
from dataclasses import dataclass
from typing import Iterable


# ── Canonical port names ──────────────────────────────────────────────────────
# Every frontend handle id and every PortDef.name in unit_definitions.py must
# draw from this set (or match a dynamic pattern below).
CANONICAL_PORTS: frozenset[str] = frozenset(
    {
        # Single-port blocks
        "in",
        "out",
        # Two-phase separators
        "vapor",
        "liquid",
        "aqueous",  # three-phase
        # Heat exchanger
        "hot-in",
        "hot-out",
        "cold-in",
        "cold-out",
        # Absorber / Stripper
        "gas-in",
        "gas-out",
        "liquid-in",
        "liquid-out",
        # Columns
        "feed",
        "overhead",
        "bottoms",
        # LLE / 2-product splitter alternate names
        "light",
        "heavy",
    }
)

# Dynamic canonical patterns — numeric-suffix ports on Mixer/Splitter etc.
# Resolver matches names like ``in3`` or ``out7`` and returns them as-is.
_DYNAMIC_CANONICAL = re.compile(r"^(in|out)(\d+)$")


# ── Static aliases ────────────────────────────────────────────────────────────
# Legacy / vendor / synonym names normalize to a canonical name. If the
# canonical target is also a valid port on the current unit, the alias
# resolves; otherwise the resolver tries the next candidate.
#
# Multiple aliases may map to the same canonical. One alias may have more
# than one canonical candidate (e.g. ``input`` → prefer ``in``, fall back to
# ``feed`` on a column); in that case list them in preference order.
STATIC_ALIASES: dict[str, tuple[str, ...]] = {
    # Generic in/out synonyms
    "inlet": ("in", "feed"),
    "input": ("in", "feed"),
    "outlet": ("out",),
    "output": ("out",),
    "product": ("out",),
    # Phase aliases (Flash / separators)
    "vap": ("vapor",),
    "v": ("vapor",),
    "gas": ("vapor", "gas-out"),
    "liq": ("liquid",),
    "l": ("liquid",),
    # Heat-exchanger alt names
    "hot_inlet": ("hot-in",),
    "hot_outlet": ("hot-out",),
    "cold_inlet": ("cold-in",),
    "cold_outlet": ("cold-out",),
    "shell-in": ("hot-in",),
    "shell-out": ("hot-out",),
    "tube-in": ("cold-in",),
    "tube-out": ("cold-out",),
    # Gas/liquid column alt names
    "vapor-in": ("gas-in",),
    "vapor-out": ("gas-out",),
    # Column alt names
    "distillate": ("overhead",),
    "top": ("overhead",),
    "tops": ("overhead",),
    "bottom": ("bottoms",),
    "btms": ("bottoms",),
    # Two-product splitter alt names
    "outlet1": ("light", "out1"),
    "outlet2": ("heavy", "out2"),
    "product1": ("light", "out1"),
    "product2": ("heavy", "out2"),
}

# Dynamic alias patterns — ``inlet3`` → ``in3``, ``feed5`` → ``in5``, etc.
# Each entry is (regex, canonical_template) where the template uses
# ``{n}`` for the captured number.
_DYNAMIC_ALIASES: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"^inlet_?(\d+)$"), "in{n}"),
    (re.compile(r"^feed_?(\d+)$"), "in{n}"),
    (re.compile(r"^outlet_?(\d+)$"), "out{n}"),
    (re.compile(r"^product_?(\d+)$"), "out{n}"),
]


class UnknownPortError(ValueError):
    """Raised when a port name cannot be resolved to a canonical form."""

    def __init__(self, port_name: str, unit_type: str | None = None) -> None:
        self.port_name = port_name
        self.unit_type = unit_type
        ctx = f" on unit type {unit_type!r}" if unit_type else ""
        super().__init__(
            f"Unknown port name {port_name!r}{ctx}. "
            "Canonical names live in app/data/port_alias.py."
        )


@dataclass(frozen=True)
class ResolvedPort:
    """Result of resolving a port name."""

    canonical: str
    was_alias: bool  # True if the input differed from the canonical form
    original: str


def _match_dynamic(name: str) -> str | None:
    """Return canonical dynamic form (``in3``/``out7``) or ``None``."""
    m = _DYNAMIC_CANONICAL.match(name)
    if m:
        return name
    for pattern, template in _DYNAMIC_ALIASES:
        m = pattern.match(name)
        if m:
            return template.format(n=m.group(1))
    return None


def is_canonical(name: str) -> bool:
    """Return True if the given name is already a canonical port name."""
    return name in CANONICAL_PORTS or _DYNAMIC_CANONICAL.match(name) is not None


def resolve(
    port_name: str,
    valid_ports: Iterable[str] | None = None,
    unit_type: str | None = None,
) -> ResolvedPort:
    """
    Normalize a port name to its canonical form.

    Parameters
    ----------
    port_name
        Incoming port name (may be canonical, alias, or dynamic).
    valid_ports
        Optional iterable of ports the target unit actually has. When
        provided, aliases that could resolve to multiple canonicals are
        disambiguated by picking one present in this set.
    unit_type
        Optional unit type string, used only for error context.

    Returns
    -------
    ResolvedPort(canonical, was_alias, original)

    Raises
    ------
    UnknownPortError
        If no canonical candidate can be found.
    """
    if not isinstance(port_name, str) or not port_name:
        raise UnknownPortError(port_name, unit_type)

    valid_set = set(valid_ports) if valid_ports is not None else None

    # Already canonical?
    if port_name in CANONICAL_PORTS:
        if valid_set is None or port_name in valid_set:
            return ResolvedPort(port_name, was_alias=False, original=port_name)

    # Dynamic canonical (e.g., "in3")
    dyn = _match_dynamic(port_name)
    if dyn is not None:
        # Dynamic ports are always considered "resolved" — valid_set check is
        # the caller's responsibility since Mixer/Splitter grow ports at
        # runtime via numInlets/numOutlets.
        return ResolvedPort(dyn, was_alias=(dyn != port_name), original=port_name)

    # Static alias?
    candidates = STATIC_ALIASES.get(port_name, ())
    for candidate in candidates:
        if valid_set is not None and candidate not in valid_set:
            continue
        return ResolvedPort(candidate, was_alias=True, original=port_name)

    # Last-chance fallback: if valid_set is None and we have a single alias
    # target, accept it. This supports use cases where we just need to
    # normalize (e.g., migrations) without a unit context.
    if valid_set is None and len(candidates) == 1:
        return ResolvedPort(candidates[0], was_alias=True, original=port_name)

    raise UnknownPortError(port_name, unit_type)


def try_resolve(
    port_name: str,
    valid_ports: Iterable[str] | None = None,
    unit_type: str | None = None,
) -> ResolvedPort | None:
    """Same as resolve, but returns None instead of raising."""
    try:
        return resolve(port_name, valid_ports=valid_ports, unit_type=unit_type)
    except UnknownPortError:
        return None
