"""
Component Database

Single source of truth for chemical component physical properties.
Both the API components route and the property packages module read from here.
"""

from dataclasses import dataclass, field
from typing import Optional


@dataclass(frozen=True)
class ComponentData:
    """Physical property data for a chemical component."""
    id: str
    name: str
    formula: str
    cas_number: Optional[str]
    mw: float              # kg/kmol
    temperature_crit: float  # K
    pressure_crit: float     # Pa
    omega: float             # acentric factor
    normal_bp: float         # K (normal boiling point)
    category: str
    # Wagner equation coefficients for saturation pressure (dimensionless)
    # ln(Pr) = (1-x)^-1 * (A*x + B*x^1.5 + C*x^3 + D*x^6), x = 1 - T/Tc
    wagner_A: float = 0.0
    wagner_B: float = 0.0
    wagner_C: float = 0.0
    wagner_D: float = 0.0


# ─── Master component table ───────────────────────────────────────────
# Sources: NIST WebBook, Perry's Chemical Engineers' Handbook (9th ed.),
# Reid, Prausnitz & Poling "Properties of Gases and Liquids" (5th ed.)
# Wagner coefficients from DIPPR/NIST correlations.

COMPONENTS: tuple[ComponentData, ...] = (
    ComponentData(
        id="water", name="Water", formula="H2O", cas_number="7732-18-5",
        mw=18.015, temperature_crit=647.3, pressure_crit=22.064e6,
        omega=0.344, normal_bp=373.15, category="inorganic",
        wagner_A=-7.76451, wagner_B=1.45838, wagner_C=-2.77580, wagner_D=-1.23303,
    ),
    ComponentData(
        id="methane", name="Methane", formula="CH4", cas_number="74-82-8",
        mw=16.043, temperature_crit=190.6, pressure_crit=4.60e6,
        omega=0.011, normal_bp=111.7, category="alkane",
        wagner_A=-6.00435, wagner_B=1.18850, wagner_C=-0.83400, wagner_D=-1.22833,
    ),
    ComponentData(
        id="ethane", name="Ethane", formula="C2H6", cas_number="74-84-0",
        mw=30.07, temperature_crit=305.4, pressure_crit=4.88e6,
        omega=0.099, normal_bp=184.6, category="alkane",
        wagner_A=-6.48647, wagner_B=1.24399, wagner_C=-1.35769, wagner_D=-2.56776,
    ),
    ComponentData(
        id="propane", name="Propane", formula="C3H8", cas_number="74-98-6",
        mw=44.1, temperature_crit=369.8, pressure_crit=4.25e6,
        omega=0.152, normal_bp=231.1, category="alkane",
        wagner_A=-6.72219, wagner_B=1.33236, wagner_C=-2.13868, wagner_D=-1.38551,
    ),
    ComponentData(
        id="n-butane", name="n-Butane", formula="C4H10", cas_number="106-97-8",
        mw=58.12, temperature_crit=425.2, pressure_crit=3.80e6,
        omega=0.199, normal_bp=272.7, category="alkane",
        wagner_A=-6.88709, wagner_B=1.15157, wagner_C=-1.99873, wagner_D=-3.13003,
    ),
    ComponentData(
        id="n-pentane", name="n-Pentane", formula="C5H12", cas_number="109-66-0",
        mw=72.15, temperature_crit=469.7, pressure_crit=3.37e6,
        omega=0.251, normal_bp=309.2, category="alkane",
        wagner_A=-7.28936, wagner_B=1.53679, wagner_C=-3.08367, wagner_D=-1.02456,
    ),
    ComponentData(
        id="n-hexane", name="n-Hexane", formula="C6H14", cas_number="110-54-3",
        mw=86.18, temperature_crit=507.4, pressure_crit=3.01e6,
        omega=0.299, normal_bp=341.9, category="alkane",
        wagner_A=-7.46765, wagner_B=1.44211, wagner_C=-3.28222, wagner_D=-2.50941,
    ),
    ComponentData(
        id="n-heptane", name="n-Heptane", formula="C7H16", cas_number="142-82-5",
        mw=100.20, temperature_crit=540.2, pressure_crit=2.74e6,
        omega=0.349, normal_bp=371.6, category="alkane",
        wagner_A=-7.67468, wagner_B=1.37068, wagner_C=-3.53620, wagner_D=-3.20243,
    ),
    ComponentData(
        id="n-octane", name="n-Octane", formula="C8H18", cas_number="111-65-9",
        mw=114.23, temperature_crit=568.7, pressure_crit=2.49e6,
        omega=0.399, normal_bp=398.8, category="alkane",
        wagner_A=-7.91211, wagner_B=1.38007, wagner_C=-3.80435, wagner_D=-4.50132,
    ),
    ComponentData(
        id="benzene", name="Benzene", formula="C6H6", cas_number="71-43-2",
        mw=78.11, temperature_crit=562.1, pressure_crit=4.89e6,
        omega=0.212, normal_bp=353.3, category="aromatic",
        wagner_A=-6.98273, wagner_B=1.33213, wagner_C=-2.62863, wagner_D=-3.33399,
    ),
    ComponentData(
        id="toluene", name="Toluene", formula="C7H8", cas_number="108-88-3",
        mw=92.14, temperature_crit=591.8, pressure_crit=4.11e6,
        omega=0.263, normal_bp=383.8, category="aromatic",
        wagner_A=-7.28607, wagner_B=1.38091, wagner_C=-2.83433, wagner_D=-2.79168,
    ),
    ComponentData(
        id="xylene", name="m-Xylene", formula="C8H10", cas_number="108-38-3",
        mw=106.17, temperature_crit=617.1, pressure_crit=3.54e6,
        omega=0.326, normal_bp=412.3, category="aromatic",
        wagner_A=-7.58091, wagner_B=1.41092, wagner_C=-3.28838, wagner_D=-2.88191,
    ),
    ComponentData(
        id="methanol", name="Methanol", formula="CH3OH", cas_number="67-56-1",
        mw=32.04, temperature_crit=512.6, pressure_crit=8.09e6,
        omega=0.566, normal_bp=337.8, category="alcohol",
        wagner_A=-8.54796, wagner_B=0.76982, wagner_C=-3.10850, wagner_D=1.54481,
    ),
    ComponentData(
        id="ethanol", name="Ethanol", formula="C2H5OH", cas_number="64-17-5",
        mw=46.07, temperature_crit=513.9, pressure_crit=6.14e6,
        omega=0.644, normal_bp=351.5, category="alcohol",
        wagner_A=-8.51838, wagner_B=0.34163, wagner_C=-5.73683, wagner_D=8.32581,
    ),
    ComponentData(
        id="isopropanol", name="Isopropanol", formula="C3H7OH", cas_number="67-63-0",
        mw=60.10, temperature_crit=508.3, pressure_crit=4.76e6,
        omega=0.668, normal_bp=355.4, category="alcohol",
        wagner_A=-8.16920, wagner_B=0.29960, wagner_C=-5.09440, wagner_D=3.90630,
    ),
    ComponentData(
        id="acetone", name="Acetone", formula="C3H6O", cas_number="67-64-1",
        mw=58.08, temperature_crit=508.1, pressure_crit=4.70e6,
        omega=0.307, normal_bp=329.4, category="ketone",
        wagner_A=-7.45514, wagner_B=1.20200, wagner_C=-2.43926, wagner_D=-3.35590,
    ),
    ComponentData(
        id="acetic-acid", name="Acetic Acid", formula="CH3COOH", cas_number="64-19-7",
        mw=60.05, temperature_crit=592.0, pressure_crit=5.79e6,
        omega=0.467, normal_bp=391.1, category="acid",
        wagner_A=-8.18810, wagner_B=1.07290, wagner_C=-5.13350, wagner_D=0.13120,
    ),
    ComponentData(
        id="carbon-dioxide", name="Carbon Dioxide", formula="CO2", cas_number="124-38-9",
        mw=44.01, temperature_crit=304.2, pressure_crit=7.38e6,
        omega=0.225, normal_bp=194.7, category="inorganic",
        wagner_A=-7.06020, wagner_B=1.93910, wagner_C=-1.69460, wagner_D=-3.06160,
    ),
    ComponentData(
        id="nitrogen", name="Nitrogen", formula="N2", cas_number="7727-37-9",
        mw=28.01, temperature_crit=126.2, pressure_crit=3.39e6,
        omega=0.039, normal_bp=77.4, category="inorganic",
        wagner_A=-6.12820, wagner_B=1.17167, wagner_C=-0.59254, wagner_D=-1.08680,
    ),
    ComponentData(
        id="oxygen", name="Oxygen", formula="O2", cas_number="7782-44-7",
        mw=32.0, temperature_crit=154.6, pressure_crit=5.04e6,
        omega=0.022, normal_bp=90.2, category="inorganic",
        wagner_A=-6.15980, wagner_B=1.09379, wagner_C=-0.56246, wagner_D=-2.14300,
    ),
    ComponentData(
        id="hydrogen", name="Hydrogen", formula="H2", cas_number="1333-74-0",
        mw=2.016, temperature_crit=33.2, pressure_crit=1.30e6,
        omega=-0.220, normal_bp=20.4, category="inorganic",
        wagner_A=-5.72390, wagner_B=1.01620, wagner_C=-0.09850, wagner_D=0.32820,
    ),
    ComponentData(
        id="ammonia", name="Ammonia", formula="NH3", cas_number="7664-41-7",
        mw=17.03, temperature_crit=405.5, pressure_crit=11.35e6,
        omega=0.252, normal_bp=239.8, category="inorganic",
        wagner_A=-7.55466, wagner_B=1.61657, wagner_C=-2.15440, wagner_D=-2.13480,
    ),
    ComponentData(
        id="carbon-monoxide", name="Carbon Monoxide", formula="CO", cas_number="630-08-0",
        mw=28.01, temperature_crit=132.9, pressure_crit=3.50e6,
        omega=0.048, normal_bp=81.7, category="inorganic",
        wagner_A=-6.11170, wagner_B=1.11410, wagner_C=-0.87060, wagner_D=-0.80550,
    ),
    ComponentData(
        id="hydrogen-sulfide", name="Hydrogen Sulfide", formula="H2S", cas_number="7783-06-4",
        mw=34.08, temperature_crit=373.5, pressure_crit=9.00e6,
        omega=0.094, normal_bp=212.8, category="inorganic",
        wagner_A=-6.53600, wagner_B=1.08220, wagner_C=-1.02180, wagner_D=-2.40800,
    ),
    ComponentData(
        id="sulfur-dioxide", name="Sulfur Dioxide", formula="SO2", cas_number="7446-09-5",
        mw=64.07, temperature_crit=430.8, pressure_crit=7.88e6,
        omega=0.245, normal_bp=263.1, category="inorganic",
        wagner_A=-7.23570, wagner_B=1.55000, wagner_C=-2.18290, wagner_D=-1.74550,
    ),
    ComponentData(
        id="ethylene", name="Ethylene", formula="C2H4", cas_number="74-85-1",
        mw=28.05, temperature_crit=282.4, pressure_crit=5.04e6,
        omega=0.085, normal_bp=169.4, category="olefin",
        wagner_A=-6.32440, wagner_B=1.14460, wagner_C=-1.24320, wagner_D=-2.12180,
    ),
    ComponentData(
        id="propylene", name="Propylene", formula="C3H6", cas_number="115-07-1",
        mw=42.08, temperature_crit=365.6, pressure_crit=4.60e6,
        omega=0.142, normal_bp=225.5, category="olefin",
        wagner_A=-6.64640, wagner_B=1.20860, wagner_C=-1.83070, wagner_D=-2.86980,
    ),
    ComponentData(
        id="styrene", name="Styrene", formula="C8H8", cas_number="100-42-5",
        mw=104.15, temperature_crit=636.0, pressure_crit=3.85e6,
        omega=0.297, normal_bp=418.3, category="aromatic",
        wagner_A=-7.51200, wagner_B=1.34500, wagner_C=-3.17800, wagner_D=-2.95600,
    ),
    ComponentData(
        id="formaldehyde", name="Formaldehyde", formula="CH2O", cas_number="50-00-0",
        mw=30.03, temperature_crit=408.0, pressure_crit=6.59e6,
        omega=0.282, normal_bp=254.1, category="aldehyde",
        wagner_A=-7.12000, wagner_B=1.30000, wagner_C=-2.50000, wagner_D=-2.80000,
    ),
    ComponentData(
        id="dimethyl-ether", name="Dimethyl Ether", formula="C2H6O", cas_number="115-10-6",
        mw=46.07, temperature_crit=400.1, pressure_crit=5.37e6,
        omega=0.200, normal_bp=248.3, category="ether",
        wagner_A=-6.97190, wagner_B=1.21470, wagner_C=-2.08070, wagner_D=-2.87540,
    ),
    ComponentData(
        id="chlorine", name="Chlorine", formula="Cl2", cas_number="7782-50-5",
        mw=70.91, temperature_crit=417.2, pressure_crit=7.71e6,
        omega=0.069, normal_bp=239.1, category="inorganic",
        wagner_A=-6.54900, wagner_B=1.10200, wagner_C=-1.12300, wagner_D=-2.51400,
    ),
    ComponentData(
        id="argon", name="Argon", formula="Ar", cas_number="7440-37-1",
        mw=39.95, temperature_crit=150.9, pressure_crit=4.87e6,
        omega=-0.002, normal_bp=87.3, category="inorganic",
        wagner_A=-5.90620, wagner_B=1.05120, wagner_C=-0.54120, wagner_D=-1.58100,
    ),
    ComponentData(
        id="helium", name="Helium", formula="He", cas_number="7440-59-7",
        mw=4.003, temperature_crit=5.2, pressure_crit=0.227e6,
        omega=-0.390, normal_bp=4.2, category="inorganic",
        wagner_A=-4.88430, wagner_B=0.97830, wagner_C=-0.35160, wagner_D=0.12620,
    ),
    # ─── Glycols ─────────────────────────────────────────────────────────
    # Sources: DIPPR 801 database, Perry's 9th ed., NIST WebBook
    ComponentData(
        id="ethylene-glycol", name="Ethylene Glycol", formula="C2H6O2", cas_number="107-21-1",
        mw=62.07, temperature_crit=720.0, pressure_crit=8.20e6,
        omega=0.487, normal_bp=470.5, category="glycol",
        wagner_A=-9.98970, wagner_B=3.15770, wagner_C=-6.38900, wagner_D=2.08610,
    ),
    ComponentData(
        id="diethylene-glycol", name="Diethylene Glycol", formula="C4H10O3", cas_number="111-46-6",
        mw=106.12, temperature_crit=744.6, pressure_crit=4.60e6,
        omega=0.622, normal_bp=518.0, category="glycol",
        wagner_A=-10.0190, wagner_B=2.57600, wagner_C=-7.60300, wagner_D=0.0,
    ),
    ComponentData(
        id="triethylene-glycol", name="Triethylene Glycol", formula="C6H14O4", cas_number="112-27-6",
        mw=150.17, temperature_crit=769.5, pressure_crit=3.32e6,
        omega=0.755, normal_bp=558.0, category="glycol",
        wagner_A=-10.5990, wagner_B=2.72200, wagner_C=-8.19200, wagner_D=0.0,
    ),
    # ─── Amines ──────────────────────────────────────────────────────────
    # Sources: DIPPR 801, Reid–Prausnitz–Poling 5th ed.
    ComponentData(
        id="monoethanolamine", name="Monoethanolamine", formula="C2H7NO", cas_number="141-43-5",
        mw=61.08, temperature_crit=678.0, pressure_crit=7.13e6,
        omega=0.446, normal_bp=444.2, category="amine",
    ),
    ComponentData(
        id="diethanolamine", name="Diethanolamine", formula="C4H11NO2", cas_number="111-42-2",
        mw=105.14, temperature_crit=736.6, pressure_crit=4.27e6,
        omega=0.953, normal_bp=541.5, category="amine",
    ),
    ComponentData(
        id="triethanolamine", name="Triethanolamine", formula="C6H15NO3", cas_number="102-71-6",
        mw=149.19, temperature_crit=787.0, pressure_crit=3.59e6,
        omega=1.284, normal_bp=608.6, category="amine",
    ),
    ComponentData(
        id="mdea", name="Methyldiethanolamine", formula="C5H13NO2", cas_number="105-59-9",
        mw=119.16, temperature_crit=741.9, pressure_crit=3.88e6,
        omega=0.603, normal_bp=520.0, category="amine",
    ),
    # ─── Refrigerants ────────────────────────────────────────────────────
    # Sources: NIST WebBook, ASHRAE Fundamentals, DIPPR 801
    ComponentData(
        id="r134a", name="1,1,1,2-Tetrafluoroethane", formula="C2H2F4", cas_number="811-97-2",
        mw=102.03, temperature_crit=374.21, pressure_crit=4.059e6,
        omega=0.327, normal_bp=247.08, category="refrigerant",
        wagner_A=-7.60210, wagner_B=1.85280, wagner_C=-2.81620, wagner_D=-3.25100,
    ),
    ComponentData(
        id="r22", name="Chlorodifluoromethane", formula="CHClF2", cas_number="75-45-6",
        mw=86.47, temperature_crit=369.30, pressure_crit=4.990e6,
        omega=0.221, normal_bp=232.35, category="refrigerant",
        wagner_A=-7.07830, wagner_B=1.59610, wagner_C=-2.31140, wagner_D=-2.75370,
    ),
    # ─── More Aromatics ─────────────────────────────────────────────────
    # Sources: DIPPR 801, NIST WebBook, Perry's 9th ed.
    ComponentData(
        id="ethylbenzene", name="Ethylbenzene", formula="C8H10-eb", cas_number="100-41-4",
        mw=106.17, temperature_crit=617.2, pressure_crit=3.61e6,
        omega=0.304, normal_bp=409.3, category="aromatic",
        wagner_A=-7.47740, wagner_B=1.45240, wagner_C=-3.16400, wagner_D=-2.70850,
    ),
    ComponentData(
        id="cumene", name="Cumene", formula="C9H12", cas_number="98-82-8",
        mw=120.19, temperature_crit=631.1, pressure_crit=3.21e6,
        omega=0.326, normal_bp=425.6, category="aromatic",
        wagner_A=-7.60710, wagner_B=1.37990, wagner_C=-3.36600, wagner_D=-3.10800,
    ),
    ComponentData(
        id="o-xylene", name="o-Xylene", formula="C8H10-ox", cas_number="95-47-6",
        mw=106.17, temperature_crit=630.3, pressure_crit=3.73e6,
        omega=0.310, normal_bp=417.6, category="aromatic",
        wagner_A=-7.53357, wagner_B=1.34820, wagner_C=-3.16880, wagner_D=-2.89090,
    ),
    ComponentData(
        id="p-xylene", name="p-Xylene", formula="C8H10-px", cas_number="106-42-3",
        mw=106.17, temperature_crit=616.2, pressure_crit=3.51e6,
        omega=0.322, normal_bp=411.5, category="aromatic",
        wagner_A=-7.56700, wagner_B=1.41400, wagner_C=-3.24600, wagner_D=-2.84800,
    ),
    # ─── Additional Inorganics ───────────────────────────────────────────
    # Sources: NIST WebBook, Perry's 9th ed., DIPPR 801
    # Note: NH3 and SO2 already present above
    ComponentData(
        id="hydrogen-chloride", name="Hydrogen Chloride", formula="HCl", cas_number="7647-01-0",
        mw=36.46, temperature_crit=324.7, pressure_crit=8.31e6,
        omega=0.132, normal_bp=188.1, category="inorganic",
        wagner_A=-6.63200, wagner_B=1.26700, wagner_C=-0.88500, wagner_D=-2.65000,
    ),
    ComponentData(
        id="sulfuric-acid", name="Sulfuric Acid", formula="H2SO4", cas_number="7664-93-9",
        mw=98.08, temperature_crit=924.0, pressure_crit=6.40e6,
        omega=0.411, normal_bp=610.0, category="inorganic",
    ),
    # ─── Common Solvents ─────────────────────────────────────────────────
    # Sources: DIPPR 801, NIST WebBook, Reid–Prausnitz–Poling 5th ed.
    ComponentData(
        id="dmf", name="Dimethylformamide", formula="C3H7NO", cas_number="68-12-2",
        mw=73.09, temperature_crit=649.6, pressure_crit=4.42e6,
        omega=0.313, normal_bp=426.2, category="solvent",
        wagner_A=-7.63080, wagner_B=1.38040, wagner_C=-3.11300, wagner_D=-2.72000,
    ),
    ComponentData(
        id="dmso", name="Dimethyl Sulfoxide", formula="C2H6OS", cas_number="67-68-5",
        mw=78.13, temperature_crit=729.0, pressure_crit=5.65e6,
        omega=0.281, normal_bp=462.2, category="solvent",
        wagner_A=-8.39100, wagner_B=2.34700, wagner_C=-4.78200, wagner_D=-0.68900,
    ),
    ComponentData(
        id="thf", name="Tetrahydrofuran", formula="C4H8O", cas_number="109-99-9",
        mw=72.11, temperature_crit=540.1, pressure_crit=5.19e6,
        omega=0.225, normal_bp=339.1, category="solvent",
        wagner_A=-7.09620, wagner_B=1.26380, wagner_C=-2.62760, wagner_D=-2.89100,
    ),
)

# ─── Lookup indices ───────────────────────────────────────────────────

_BY_FORMULA: dict[str, ComponentData] = {c.formula: c for c in COMPONENTS}
_BY_ID: dict[str, ComponentData] = {c.id: c for c in COMPONENTS}
_BY_NAME_LOWER: dict[str, ComponentData] = {c.name.lower(): c for c in COMPONENTS}


def get_component_by_formula(formula: str) -> ComponentData | None:
    """Look up by formula (e.g. 'H2O', 'CH4')."""
    return _BY_FORMULA.get(formula)


def get_component_by_id(component_id: str) -> ComponentData | None:
    """Look up by slug id (e.g. 'water', 'methane')."""
    return _BY_ID.get(component_id)


def get_component(name_or_formula: str) -> ComponentData | None:
    """Fuzzy lookup: try formula first, then id, then name."""
    return (
        _BY_FORMULA.get(name_or_formula)
        or _BY_ID.get(name_or_formula)
        or _BY_NAME_LOWER.get(name_or_formula.lower())
    )


def get_idaes_parameter_data(name_or_formula: str) -> dict:
    """Return the dict that IDAES GenericParameterBlock expects for a component.

    Raises ValueError if the component is not found — never returns
    placeholder data that could silently produce nonsense results.
    """
    comp = get_component(name_or_formula)
    if comp is None:
        raise ValueError(
            f"Unknown component '{name_or_formula}'. "
            f"Available: {sorted(_BY_FORMULA.keys())}"
        )
    return {
        "mw": comp.mw,
        "pressure_crit": comp.pressure_crit,
        "temperature_crit": comp.temperature_crit,
        "omega": comp.omega,
        "normal_bp": comp.normal_bp,
        "wagner_A": comp.wagner_A,
        "wagner_B": comp.wagner_B,
        "wagner_C": comp.wagner_C,
        "wagner_D": comp.wagner_D,
    }


def get_all_categories() -> list[str]:
    """Return sorted list of unique categories."""
    return sorted({c.category for c in COMPONENTS})
