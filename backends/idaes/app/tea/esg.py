"""
ESG emissions accounting — scope 1/2/3 tons CO2e per year + per unit product.

Scope 1: direct emissions from on-site fuel combustion (fired heaters,
         boilers, gas turbines). Computed from fuel consumption + EF.
Scope 2: indirect emissions from purchased electricity. Grid emission
         factor (kg CO2e/kWh) varies 20x by location; defaults below
         from IEA 2023 country/region averages.
Scope 3: upstream emissions from feedstock production. Computed from
         feedstock mass × carbon intensity.

References:
- GHG Protocol Corporate Standard (scope classification)
- IEA Electricity Information 2023 (scope 2 factors)
- RED II / CA LCFS methodology (carbon intensity conventions)
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Optional


# ── Scope 2 grid emission factors (kg CO2e/kWh) ─────────────────────────────
# IEA 2023 published data; round to two significant figures.
GRID_EF_KGCO2_PER_KWH: dict[str, float] = {
    "US-GC": 0.40,
    "US-MW": 0.45,    # higher coal share
    "US-CA": 0.23,
    "EU": 0.24,
    "JP": 0.46,
    "CN": 0.55,
    "IN": 0.70,
    "BR": 0.12,       # hydro-heavy
    "NO": 0.03,       # hydro
    "FR": 0.05,       # nuclear-heavy
    "CUSTOM": 0.45,   # fallback — reasonable "mixed" number
}


# ── Scope 1 fuel emission factors (kg CO2e / kg fuel) ───────────────────────
# Stoichiometric combustion with the standard 44/12 C ratio, adjusted for
# typical fuel carbon fractions and full oxidation.
FUEL_EF_KGCO2_PER_KG: dict[str, float] = {
    "natural_gas": 2.75,      # ~75% C → 0.75 × 44/12 = 2.75 kg CO2/kg
    "fuel_oil": 3.15,
    "coal": 2.55,              # bituminous average
    "biomass": 0.0,            # biogenic — scope 1 accounting typically zero
    "hydrogen": 0.0,           # no CO2 at combustion; upstream may have CI
    "diesel": 3.17,
    "lpg": 3.00,
}


# ── Scope 3 feedstock carbon intensities (kg CO2e / kg product) ─────────────
# Cradle-to-gate; excludes end-use combustion. Sources: NREL H2A, EU JRC.
FEEDSTOCK_CI_KGCO2_PER_KG: dict[str, float] = {
    "natural_gas": 0.30,      # methane leakage + production
    "syngas_smr": 10.0,       # SMR-produced syngas
    "syngas_ats": 1.5,        # autothermal + CCS
    "electrolysis_h2_green": 0.0,
    "electrolysis_h2_grid": 10.0,  # varies massively by grid
    "biomass": 0.1,
    "corn": 0.6,
    "sugar": 0.9,
    "bauxite": 0.8,
    "iron_ore": 0.8,
    "air": 0.0,                # on-site, scope 1 only
    "water": 0.0,
}


@dataclass(frozen=True)
class FuelConsumption:
    fuel: str                  # key into FUEL_EF_KGCO2_PER_KG
    mass_kg_per_year: float


@dataclass(frozen=True)
class FeedstockInput:
    name: str                  # key into FEEDSTOCK_CI_KGCO2_PER_KG or 'custom'
    mass_kg_per_year: float
    ci_kgco2_per_kg: Optional[float] = None   # overrides table


@dataclass(frozen=True)
class EsgConfig:
    """Inputs to the scope 1/2/3 calculation."""

    fuels: tuple[FuelConsumption, ...] = ()
    grid_region: str = "US-GC"
    grid_ef_override: Optional[float] = None   # kg CO2e/kWh
    electricity_kwh_per_year: float = 0.0
    feedstocks: tuple[FeedstockInput, ...] = ()
    annual_production_kg: float = 0.0
    # Water footprint: process withdrawal minus return (evaporation +
    # entrainment + blowdown). Cooling towers typically consume 1–2% of
    # circulation rate. Users enter the net annual consumption directly;
    # default m3/year.
    water_withdrawal_m3_per_year: float = 0.0
    water_consumption_m3_per_year: float = 0.0


@dataclass(frozen=True)
class EsgResult:
    scope_1_tco2_per_year: float
    scope_2_tco2_per_year: float
    scope_3_tco2_per_year: float
    total_tco2_per_year: float
    ci_kgco2_per_kg_product: float    # only meaningful if annual_production_kg > 0
    water_withdrawal_m3_per_kg: float = 0.0
    water_consumption_m3_per_kg: float = 0.0
    # Names the caller asked for that weren't in the CI table and had no
    # explicit override — those contributions silently zero'd out, so the
    # UI can warn the user.
    unknown_feedstocks: tuple[str, ...] = ()
    unknown_fuels: tuple[str, ...] = ()

    def to_dict(self) -> dict:
        return {
            "scope_1_tco2_per_year": self.scope_1_tco2_per_year,
            "scope_2_tco2_per_year": self.scope_2_tco2_per_year,
            "scope_3_tco2_per_year": self.scope_3_tco2_per_year,
            "total_tco2_per_year": self.total_tco2_per_year,
            "ci_kgco2_per_kg_product": self.ci_kgco2_per_kg_product,
            "water_withdrawal_m3_per_kg": self.water_withdrawal_m3_per_kg,
            "water_consumption_m3_per_kg": self.water_consumption_m3_per_kg,
            "unknown_feedstocks": list(self.unknown_feedstocks),
            "unknown_fuels": list(self.unknown_fuels),
        }


def _kg_to_tons(kg: float) -> float:
    return kg / 1000.0


def compute_esg(config: EsgConfig) -> EsgResult:
    """Aggregate scope 1/2/3 emissions + per-unit product CI."""
    unknown_fuels: list[str] = []
    unknown_feedstocks: list[str] = []

    # Scope 1
    scope_1_kg = 0.0
    for f in config.fuels:
        ef = FUEL_EF_KGCO2_PER_KG.get(f.fuel)
        if ef is None:
            unknown_fuels.append(f.fuel)
            ef = 0.0
        scope_1_kg += f.mass_kg_per_year * ef

    # Scope 2
    grid_ef = (
        config.grid_ef_override
        if config.grid_ef_override is not None
        else GRID_EF_KGCO2_PER_KWH.get(config.grid_region, GRID_EF_KGCO2_PER_KWH["CUSTOM"])
    )
    scope_2_kg = config.electricity_kwh_per_year * grid_ef

    # Scope 3
    scope_3_kg = 0.0
    for fs in config.feedstocks:
        if fs.ci_kgco2_per_kg is not None:
            ci = fs.ci_kgco2_per_kg
        else:
            looked_up = FEEDSTOCK_CI_KGCO2_PER_KG.get(fs.name)
            if looked_up is None:
                unknown_feedstocks.append(fs.name)
                ci = 0.0
            else:
                ci = looked_up
        scope_3_kg += fs.mass_kg_per_year * ci

    total_kg = scope_1_kg + scope_2_kg + scope_3_kg
    ci_product = (
        total_kg / config.annual_production_kg
        if config.annual_production_kg > 0
        else 0.0
    )

    water_w = (
        config.water_withdrawal_m3_per_year / config.annual_production_kg
        if config.annual_production_kg > 0
        else 0.0
    )
    water_c = (
        config.water_consumption_m3_per_year / config.annual_production_kg
        if config.annual_production_kg > 0
        else 0.0
    )

    return EsgResult(
        scope_1_tco2_per_year=_kg_to_tons(scope_1_kg),
        scope_2_tco2_per_year=_kg_to_tons(scope_2_kg),
        scope_3_tco2_per_year=_kg_to_tons(scope_3_kg),
        total_tco2_per_year=_kg_to_tons(total_kg),
        ci_kgco2_per_kg_product=ci_product,
        water_withdrawal_m3_per_kg=water_w,
        water_consumption_m3_per_kg=water_c,
        unknown_feedstocks=tuple(unknown_feedstocks),
        unknown_fuels=tuple(unknown_fuels),
    )
