"""Dimension enum — one entry per physical quantity Jasper tracks."""
from __future__ import annotations
from enum import Enum


class Dimension(str, Enum):
    """Physical dimensions. Stored internally in canonical SI (see below)."""

    TEMPERATURE = "temperature"        # K
    PRESSURE = "pressure"              # Pa (absolute)
    MOLAR_FLOW = "molar_flow"          # mol/s
    MASS_FLOW = "mass_flow"            # kg/s
    VOLUMETRIC_FLOW = "volumetric_flow"  # m3/s
    ENERGY = "energy"                  # J
    POWER = "power"                    # W
    MOLAR_ENTHALPY = "molar_enthalpy"  # J/mol
    MOLAR_ENTROPY = "molar_entropy"    # J/(mol·K)
    DENSITY = "density"                # kg/m3
    LENGTH = "length"                  # m
    AREA = "area"                      # m2
    VOLUME = "volume"                  # m3
    TIME = "time"                      # s
    MASS = "mass"                      # kg
    DIMENSIONLESS = "dimensionless"

    @property
    def canonical_si(self) -> str:
        return _CANONICAL[self]


_CANONICAL: dict[Dimension, str] = {
    Dimension.TEMPERATURE: "K",
    Dimension.PRESSURE: "Pa",
    Dimension.MOLAR_FLOW: "mol/s",
    Dimension.MASS_FLOW: "kg/s",
    Dimension.VOLUMETRIC_FLOW: "m3/s",
    Dimension.ENERGY: "J",
    Dimension.POWER: "W",
    Dimension.MOLAR_ENTHALPY: "J/mol",
    Dimension.MOLAR_ENTROPY: "J/(mol*K)",
    Dimension.DENSITY: "kg/m3",
    Dimension.LENGTH: "m",
    Dimension.AREA: "m2",
    Dimension.VOLUME: "m3",
    Dimension.TIME: "s",
    Dimension.MASS: "kg",
    Dimension.DIMENSIONLESS: "",
}
