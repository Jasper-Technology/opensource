"""Component registry — name/CAS/SMILES lookup + MW/density fallbacks."""
from __future__ import annotations
from dataclasses import dataclass
from functools import lru_cache
from typing import Iterable, Optional


@dataclass(frozen=True)
class Component:
    name: str
    formula: str
    cas: str
    mw: float           # g/mol
    smiles: Optional[str] = None
    nbp: Optional[float] = None  # normal boiling point, K
    density: Optional[float] = None  # kg/m3 at 298 K for liquids
    source: str = "Jasper seed"


# ── Seed list (48 components covering R1 use cases) ─────────────────────────
# Data from PubChem + NIST WebBook; roundings are intentional for R1.

DEFAULT_COMPONENTS: tuple[Component, ...] = (
    # Gases
    Component("H2",          "H2",     "1333-74-0",  2.016,  "[H][H]",   20.3,  71.0),
    Component("N2",          "N2",     "7727-37-9",  28.014, "N#N",      77.4,  808.0),
    Component("O2",          "O2",     "7782-44-7",  31.998, "O=O",      90.2,  1141.0),
    Component("CO",          "CO",     "630-08-0",   28.010, "[C-]#[O+]", 81.6, 789.0),
    Component("CO2",         "CO2",    "124-38-9",   44.010, "O=C=O",    194.7, 1101.0),
    Component("CH4",         "CH4",    "74-82-8",    16.043, "C",        111.7, 422.6),
    Component("NH3",         "NH3",    "7664-41-7",  17.031, "N",        239.8, 681.9),
    Component("H2S",         "H2S",    "7783-06-4",  34.081, "S",        212.8, 993.0),
    Component("SO2",         "SO2",    "7446-09-5",  64.066, "O=S=O",    263.1, 1434.0),
    Component("H2O",         "H2O",    "7732-18-5",  18.015, "O",        373.15, 998.0),
    # Hydrocarbons
    Component("Ethane",      "C2H6",   "74-84-0",    30.070, "CC",       184.6, 546.0),
    Component("Ethylene",    "C2H4",   "74-85-1",    28.054, "C=C",      169.4, 569.0),
    Component("Propane",     "C3H8",   "74-98-6",    44.097, "CCC",      231.1, 493.0),
    Component("Propylene",   "C3H6",   "115-07-1",   42.081, "CC=C",     225.5, 505.0),
    Component("n-Butane",    "C4H10",  "106-97-8",   58.123, "CCCC",     272.7, 573.0),
    Component("n-Pentane",   "C5H12",  "109-66-0",   72.149, "CCCCC",    309.2, 626.0),
    Component("n-Hexane",    "C6H14",  "110-54-3",   86.175, "CCCCCC",   341.9, 655.0),
    Component("n-Heptane",   "C7H16",  "142-82-5",  100.202, "CCCCCCC",  371.6, 684.0),
    Component("n-Octane",    "C8H18",  "111-65-9",  114.229, "CCCCCCCC", 398.8, 703.0),
    Component("Benzene",     "C6H6",   "71-43-2",    78.114, "c1ccccc1", 353.2, 876.0),
    Component("Toluene",     "C7H8",   "108-88-3",   92.140, "Cc1ccccc1",383.8, 867.0),
    Component("o-Xylene",    "C8H10",  "95-47-6",   106.167, "Cc1ccccc1C",417.6, 880.0),
    # Alcohols
    Component("Methanol",    "CH4O",   "67-56-1",    32.042, "CO",       337.9, 792.0),
    Component("Ethanol",     "C2H6O",  "64-17-5",    46.068, "CCO",      351.6, 789.0),
    Component("1-Propanol",  "C3H8O",  "71-23-8",    60.096, "CCCO",     370.5, 803.0),
    Component("Isopropanol", "C3H8O",  "67-63-0",    60.096, "CC(O)C",   355.5, 786.0),
    Component("Glycerol",    "C3H8O3", "56-81-5",    92.094, "OCC(O)CO", 563.0, 1261.0),
    # Carboxylic acids / esters
    Component("AceticAcid",  "C2H4O2", "64-19-7",    60.052, "CC(=O)O",  391.1, 1049.0),
    Component("FormicAcid",  "CH2O2",  "64-18-6",    46.025, "OC=O",     373.9, 1220.0),
    Component("MethylAcetate","C3H6O2","79-20-9",    74.079, "CC(=O)OC", 330.0, 934.0),
    Component("EthylAcetate","C4H8O2", "141-78-6",   88.106, "CCOC(=O)C",350.3, 902.0),
    # Ethers / ketones / aldehydes
    Component("DME",         "C2H6O",  "115-10-6",   46.068, "COC",      248.3, 668.0),
    Component("THF",         "C4H8O",  "109-99-9",   72.106, "C1CCOC1",  339.1, 889.0),
    Component("Acetone",     "C3H6O",  "67-64-1",    58.080, "CC(=O)C",  329.2, 784.0),
    Component("MEK",         "C4H8O",  "78-93-3",    72.106, "CCC(=O)C", 352.7, 805.0),
    Component("Formaldehyde","CH2O",   "50-00-0",    30.026, "C=O",      254.0, 815.0),
    # Amines
    Component("MEA",         "C2H7NO", "141-43-5",   61.083, "OCCN",     443.1, 1013.0),
    Component("DEA",         "C4H11NO2","111-42-2", 105.136, "OCCNCCO",  541.5, 1090.0),
    Component("MDEA",        "C5H13NO2","105-59-9", 119.163, "CN(CCO)CCO",519.1, 1040.0),
    # Halogens / halides
    Component("Chlorine",    "Cl2",    "7782-50-5",  70.906, "ClCl",     239.1, 1566.0),
    Component("HCl",         "HCl",    "7647-01-0",  36.461, "Cl",       188.0, 1190.0),
    # Inorganics
    Component("NaCl",        "NaCl",   "7647-14-5",  58.443, "[Na+].[Cl-]", 1738.0, 2170.0),
    Component("NaOH",        "NaOH",   "1310-73-2",  39.997, "[Na+].[OH-]", 1663.0, 2130.0),
    Component("H2SO4",       "H2SO4",  "7664-93-9",  98.079, "OS(=O)(=O)O", 610.0, 1830.0),
    Component("HNO3",        "HNO3",   "7697-37-2",  63.013, "[N+](=O)(O)[O-]", 356.0, 1513.0),
    # Misc
    Component("Air",         "Air",    "132259-10-0",28.960, None,        78.9, 1.20),
    Component("Argon",       "Ar",     "7440-37-1",  39.948, "[Ar]",      87.3, 1400.0),
    Component("Helium",      "He",     "7440-59-7",   4.003, "[He]",       4.2, 125.0),
)


# ── Registry ────────────────────────────────────────────────────────────────


class ComponentRegistry:
    """Lookup a Component by name, CAS, or SMILES. Case-insensitive on names."""

    def __init__(self, components: Iterable[Component]) -> None:
        self._by_name: dict[str, Component] = {}
        self._by_cas: dict[str, Component] = {}
        self._by_smiles: dict[str, Component] = {}
        for c in components:
            self._by_name[c.name.lower()] = c
            self._by_cas[c.cas] = c
            if c.smiles:
                self._by_smiles[c.smiles] = c

    def lookup(self, query: str) -> Optional[Component]:
        """Look up by name (case-insensitive) → CAS → SMILES. First hit wins."""
        if not query:
            return None
        q = query.strip()
        hit = self._by_name.get(q.lower())
        if hit:
            return hit
        hit = self._by_cas.get(q)
        if hit:
            return hit
        return self._by_smiles.get(q)

    def __contains__(self, query: str) -> bool:
        return self.lookup(query) is not None

    def __len__(self) -> int:
        return len(self._by_name)

    def all(self) -> tuple[Component, ...]:
        return tuple(self._by_name.values())


@lru_cache(maxsize=1)
def get_default_registry() -> ComponentRegistry:
    return ComponentRegistry(DEFAULT_COMPONENTS)
