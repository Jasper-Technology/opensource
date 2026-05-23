"""
Component registry — curated seed of ~50 common chemicals for Jasper.

Used by:
- Import parsers to validate component names (CAS lookup / fuzzy match).
- Sizing to fill fallback MW and density when streams lack them.
- TEA comprehension to identify products + feedstocks.

Deliberately not a full DIPPR/NIST database — just enough to get R1
projects off the ground. Larger property data (Tc/Pc/Hf/Cp) and BIPs
live in a future ``components/bips.py`` backed by a postgres table and
subscription imports.
"""
from .registry import (
    Component,
    ComponentRegistry,
    get_default_registry,
    DEFAULT_COMPONENTS,
)

__all__ = [
    "Component",
    "ComponentRegistry",
    "get_default_registry",
    "DEFAULT_COMPONENTS",
]
