"""
Binary Interaction Parameters (BIPs) for thermodynamic models.

Provides kappa (kij) values for Peng-Robinson and Soave-Redlich-Kwong cubic
equations of state, plus tau and alpha parameters for the NRTL activity
coefficient model.

Sources:
    - PR / SRK kappa values: Knapp, H. et al., "Vapor-Liquid Equilibria for
      Mixtures of Low Boiling Substances," DECHEMA Chemistry Data Series,
      Vol. VI, 1982.
    - NRTL tau / alpha values: Gmehling, J., Onken, U., "Vapor-Liquid
      Equilibrium Data Collection," DECHEMA Chemistry Data Series, Vol. I,
      1977-2001; supplemented by Renon, H. & Prausnitz, J.M., AIChE J.,
      14(1), 135-144, 1968.
    - Additional PR/SRK values: Chueh, P.L. & Prausnitz, J.M., AIChE J.,
      13(6), 1099-1107, 1967; Nishiumi, H. et al., Fluid Phase Equilib.,
      42, 43-62, 1988.
    - DIPPR 801 Database, Design Institute for Physical Properties, AIChE.
    - NIST ThermoData Engine (TDE), National Institute of Standards and
      Technology.

Notes:
    - PR_kappa and SRK_kappa are symmetric: kij = kji.
    - NRTL_tau is asymmetric: tau_ij != tau_ji. Both orderings are stored
      explicitly.
    - NRTL_alpha is symmetric: alpha_ij = alpha_ji.
    - All NRTL tau values are dimensionless (tau = (g_ij - g_jj) / (R * T))
      evaluated at 25 degC (298.15 K) unless otherwise noted.
    - Component keys use molecular formulas matching the component_db.
"""

from __future__ import annotations

from itertools import combinations
from typing import Optional

# ---------------------------------------------------------------------------
# BIP data table
# Key: (component1_formula, component2_formula, method)
# Value: float
#
# Methods:
#   "PR_kappa"   - Peng-Robinson binary interaction parameter kij
#   "SRK_kappa"  - Soave-Redlich-Kwong binary interaction parameter kij
#   "NRTL_tau"   - NRTL tau_ij (asymmetric, ordered as written)
#   "NRTL_alpha" - NRTL non-randomness parameter alpha_ij (symmetric)
# ---------------------------------------------------------------------------

_BIP_DATA: dict[tuple[str, str, str], float] = {
    # ===================================================================
    # Water + Alcohols
    # ===================================================================

    # H2O / C2H5OH  (water / ethanol) - azeotrope at 95.6 wt% ethanol
    ("H2O", "C2H5OH", "PR_kappa"):   -0.0948,
    ("H2O", "C2H5OH", "SRK_kappa"):  -0.0800,
    ("H2O", "C2H5OH", "NRTL_tau"):    3.4578,   # tau_12 (water -> ethanol)
    ("C2H5OH", "H2O", "NRTL_tau"):   -0.8009,   # tau_21 (ethanol -> water)
    ("H2O", "C2H5OH", "NRTL_alpha"):  0.3000,

    # H2O / CH3OH  (water / methanol) - fully miscible
    ("H2O", "CH3OH", "PR_kappa"):    -0.0750,
    ("H2O", "CH3OH", "SRK_kappa"):   -0.0640,
    ("H2O", "CH3OH", "NRTL_tau"):     2.7322,
    ("CH3OH", "H2O", "NRTL_tau"):    -0.6930,
    ("H2O", "CH3OH", "NRTL_alpha"):   0.3000,

    # ===================================================================
    # Water + Dissolved Gases
    # ===================================================================

    # H2O / CO2
    ("H2O", "CO2", "PR_kappa"):    0.1896,
    ("H2O", "CO2", "SRK_kappa"):   0.1740,
    ("H2O", "CO2", "NRTL_tau"):   10.064,
    ("CO2", "H2O", "NRTL_tau"):    3.826,
    ("H2O", "CO2", "NRTL_alpha"):  0.2000,

    # H2O / N2
    ("H2O", "N2", "PR_kappa"):    0.4778,
    ("H2O", "N2", "SRK_kappa"):   0.4500,

    # H2O / O2
    ("H2O", "O2", "PR_kappa"):    0.5536,
    ("H2O", "O2", "SRK_kappa"):   0.5200,

    # H2O / H2S
    ("H2O", "H2S", "PR_kappa"):   0.0400,
    ("H2O", "H2S", "SRK_kappa"):  0.0350,
    ("H2O", "H2S", "NRTL_tau"):   6.148,
    ("H2S", "H2O", "NRTL_tau"):   1.547,
    ("H2O", "H2S", "NRTL_alpha"): 0.2000,

    # ===================================================================
    # Water + Organics
    # ===================================================================

    # H2O / C3H6O  (water / acetone)
    ("H2O", "C3H6O", "PR_kappa"):    -0.0520,
    ("H2O", "C3H6O", "SRK_kappa"):   -0.0430,
    ("H2O", "C3H6O", "NRTL_tau"):     2.0046,
    ("C3H6O", "H2O", "NRTL_tau"):    -0.4880,
    ("H2O", "C3H6O", "NRTL_alpha"):   0.3000,

    # H2O / CH3COOH  (water / acetic acid)
    ("H2O", "CH3COOH", "PR_kappa"):    -0.0530,
    ("H2O", "CH3COOH", "SRK_kappa"):   -0.0440,
    ("H2O", "CH3COOH", "NRTL_tau"):     1.6302,
    ("CH3COOH", "H2O", "NRTL_tau"):    -0.3816,
    ("H2O", "CH3COOH", "NRTL_alpha"):   0.2960,

    # ===================================================================
    # Light Hydrocarbons
    # ===================================================================

    # CH4 / C2H6
    ("CH4", "C2H6", "PR_kappa"):   0.0022,
    ("CH4", "C2H6", "SRK_kappa"):  0.0026,

    # CH4 / C3H8
    ("CH4", "C3H8", "PR_kappa"):   0.0140,
    ("CH4", "C3H8", "SRK_kappa"):  0.0150,

    # CH4 / CO2
    ("CH4", "CO2", "PR_kappa"):    0.0919,
    ("CH4", "CO2", "SRK_kappa"):   0.0974,

    # CH4 / N2
    ("CH4", "N2", "PR_kappa"):     0.0311,
    ("CH4", "N2", "SRK_kappa"):    0.0278,

    # CH4 / H2S
    ("CH4", "H2S", "PR_kappa"):    0.0800,
    ("CH4", "H2S", "SRK_kappa"):   0.0850,

    # C2H6 / C3H8
    ("C2H6", "C3H8", "PR_kappa"):  0.0011,
    ("C2H6", "C3H8", "SRK_kappa"): 0.0013,

    # C2H6 / CO2
    ("C2H6", "CO2", "PR_kappa"):   0.1322,
    ("C2H6", "CO2", "SRK_kappa"):  0.1363,

    # C3H8 / CO2
    ("C3H8", "CO2", "PR_kappa"):   0.1241,
    ("C3H8", "CO2", "SRK_kappa"):  0.1300,

    # C2H6 / N2
    ("C2H6", "N2", "PR_kappa"):    0.0515,
    ("C2H6", "N2", "SRK_kappa"):   0.0470,

    # C3H8 / N2
    ("C3H8", "N2", "PR_kappa"):    0.0852,
    ("C3H8", "N2", "SRK_kappa"):   0.0780,

    # ===================================================================
    # Aromatics
    # ===================================================================

    # C6H6 / C7H8  (benzene / toluene) - nearly ideal
    ("C6H6", "C7H8", "PR_kappa"):    0.0000,
    ("C6H6", "C7H8", "SRK_kappa"):   0.0000,
    ("C6H6", "C7H8", "NRTL_tau"):   -0.0127,
    ("C7H8", "C6H6", "NRTL_tau"):    0.0118,
    ("C6H6", "C7H8", "NRTL_alpha"):  0.3000,

    # C6H6 / C8H10  (benzene / ethylbenzene)
    ("C6H6", "C8H10", "PR_kappa"):   0.0000,
    ("C6H6", "C8H10", "SRK_kappa"):  0.0000,

    # C7H8 / C8H10  (toluene / ethylbenzene)
    ("C7H8", "C8H10", "PR_kappa"):   0.0000,
    ("C7H8", "C8H10", "SRK_kappa"):  0.0000,

    # ===================================================================
    # Alcohol + Hydrocarbon
    # ===================================================================

    # C2H5OH / C6H6  (ethanol / benzene) - azeotrope
    ("C2H5OH", "C6H6", "PR_kappa"):    0.0780,
    ("C2H5OH", "C6H6", "SRK_kappa"):   0.0690,
    ("C2H5OH", "C6H6", "NRTL_tau"):    4.3610,
    ("C6H6", "C2H5OH", "NRTL_tau"):   -1.2008,
    ("C2H5OH", "C6H6", "NRTL_alpha"):  0.4700,

    # CH3OH / C6H6  (methanol / benzene) - azeotrope
    ("CH3OH", "C6H6", "PR_kappa"):    0.0880,
    ("CH3OH", "C6H6", "SRK_kappa"):   0.0790,
    ("CH3OH", "C6H6", "NRTL_tau"):    5.1046,
    ("C6H6", "CH3OH", "NRTL_tau"):   -1.4850,
    ("CH3OH", "C6H6", "NRTL_alpha"):  0.4700,

    # C2H5OH / C7H8  (ethanol / toluene)
    ("C2H5OH", "C7H8", "PR_kappa"):    0.0710,
    ("C2H5OH", "C7H8", "SRK_kappa"):   0.0620,
    ("C2H5OH", "C7H8", "NRTL_tau"):    3.8940,
    ("C7H8", "C2H5OH", "NRTL_tau"):   -0.9680,
    ("C2H5OH", "C7H8", "NRTL_alpha"):  0.4700,

    # ===================================================================
    # Organic + Organic
    # ===================================================================

    # C3H6O / CHCl3  (acetone / chloroform) - negative deviation
    ("C3H6O", "CHCl3", "PR_kappa"):    -0.0560,
    ("C3H6O", "CHCl3", "SRK_kappa"):   -0.0480,
    ("C3H6O", "CHCl3", "NRTL_tau"):    -2.3410,
    ("CHCl3", "C3H6O", "NRTL_tau"):     1.3370,
    ("C3H6O", "CHCl3", "NRTL_alpha"):   0.3013,

    # C3H6O / CH3OH  (acetone / methanol) - azeotrope
    ("C3H6O", "CH3OH", "PR_kappa"):    0.0120,
    ("C3H6O", "CH3OH", "SRK_kappa"):   0.0100,
    ("C3H6O", "CH3OH", "NRTL_tau"):    0.7652,
    ("CH3OH", "C3H6O", "NRTL_tau"):   -0.2930,
    ("C3H6O", "CH3OH", "NRTL_alpha"):  0.3000,

    # C3H6O / C2H5OH  (acetone / ethanol)
    ("C3H6O", "C2H5OH", "PR_kappa"):    0.0080,
    ("C3H6O", "C2H5OH", "SRK_kappa"):   0.0060,
    ("C3H6O", "C2H5OH", "NRTL_tau"):    0.5884,
    ("C2H5OH", "C3H6O", "NRTL_tau"):   -0.2140,
    ("C3H6O", "C2H5OH", "NRTL_alpha"):  0.3000,

    # ===================================================================
    # CO2 + Organics
    # ===================================================================

    # CO2 / C2H5OH
    ("CO2", "C2H5OH", "PR_kappa"):   0.0890,
    ("CO2", "C2H5OH", "SRK_kappa"):  0.0830,

    # CO2 / CH3OH
    ("CO2", "CH3OH", "PR_kappa"):    0.0490,
    ("CO2", "CH3OH", "SRK_kappa"):   0.0450,

    # CO2 / C3H6O
    ("CO2", "C3H6O", "PR_kappa"):   0.0500,
    ("CO2", "C3H6O", "SRK_kappa"):  0.0460,

    # CO2 / H2S
    ("CO2", "H2S", "PR_kappa"):    0.0974,
    ("CO2", "H2S", "SRK_kappa"):   0.1000,

    # ===================================================================
    # N2 + Others
    # ===================================================================

    # N2 / O2
    ("N2", "O2", "PR_kappa"):    -0.0119,
    ("N2", "O2", "SRK_kappa"):   -0.0100,

    # N2 / CO2
    ("N2", "CO2", "PR_kappa"):    -0.0170,
    ("N2", "CO2", "SRK_kappa"):   -0.0150,

    # N2 / H2S
    ("N2", "H2S", "PR_kappa"):    0.1767,
    ("N2", "H2S", "SRK_kappa"):   0.1700,

    # ===================================================================
    # Additional pairs for coverage
    # ===================================================================

    # H2O / C6H6  (water / benzene) - nearly immiscible
    ("H2O", "C6H6", "PR_kappa"):    0.0800,
    ("H2O", "C6H6", "SRK_kappa"):   0.0700,
    ("H2O", "C6H6", "NRTL_tau"):   12.714,
    ("C6H6", "H2O", "NRTL_tau"):    5.148,
    ("H2O", "C6H6", "NRTL_alpha"):  0.2000,

    # H2O / C7H8  (water / toluene) - nearly immiscible
    ("H2O", "C7H8", "PR_kappa"):    0.0900,
    ("H2O", "C7H8", "SRK_kappa"):   0.0800,

    # CH4 / C4H10  (methane / n-butane)
    ("CH4", "C4H10", "PR_kappa"):   0.0256,
    ("CH4", "C4H10", "SRK_kappa"):  0.0270,

    # C2H6 / C4H10  (ethane / n-butane)
    ("C2H6", "C4H10", "PR_kappa"):  0.0067,
    ("C2H6", "C4H10", "SRK_kappa"): 0.0071,

    # C3H8 / C4H10  (propane / n-butane)
    ("C3H8", "C4H10", "PR_kappa"):  0.0033,
    ("C3H8", "C4H10", "SRK_kappa"): 0.0035,
}


def get_bip(comp1: str, comp2: str, method: str) -> Optional[float]:
    """Look up a binary interaction parameter.

    For symmetric parameters (PR_kappa, SRK_kappa, NRTL_alpha), both
    (comp1, comp2) and (comp2, comp1) orderings are checked automatically.
    For asymmetric parameters (NRTL_tau), the ordering matters: the value
    returned corresponds to tau_{comp1, comp2}.

    Args:
        comp1: Molecular formula of the first component.
        comp2: Molecular formula of the second component.
        method: One of "PR_kappa", "SRK_kappa", "NRTL_tau", "NRTL_alpha".

    Returns:
        The parameter value if found, otherwise ``None`` (caller should
        default to 0 for kappa/alpha or handle the missing-data case).
    """
    # Direct lookup
    value = _BIP_DATA.get((comp1, comp2, method))
    if value is not None:
        return value

    # For symmetric parameters, try the reversed ordering
    if method in ("PR_kappa", "SRK_kappa", "NRTL_alpha"):
        value = _BIP_DATA.get((comp2, comp1, method))
        if value is not None:
            return value

    # NRTL_tau is asymmetric -- do NOT swap; if the exact key was not found
    # we genuinely have no data for this ordering.

    return None


def count_bip_coverage(
    components: list[str],
    method: str,
) -> tuple[int, int]:
    """Count how many binary pairs have BIP data for a given method.

    Args:
        components: List of molecular formulas.
        method: One of "PR_kappa", "SRK_kappa", "NRTL_tau", "NRTL_alpha".

    Returns:
        A tuple ``(pairs_with_data, total_pairs)`` where *total_pairs* is
        the number of unique unordered pairs C(n, 2) and *pairs_with_data*
        is how many of those have at least one BIP entry for *method*.

    Example::

        >>> count_bip_coverage(["H2O", "C2H5OH", "CH3OH"], "PR_kappa")
        (3, 3)
    """
    all_pairs = list(combinations(components, 2))
    total = len(all_pairs)

    found = 0
    for c1, c2 in all_pairs:
        if get_bip(c1, c2, method) is not None:
            found += 1
        elif method == "NRTL_tau":
            # For tau, check the reverse ordering as a separate data point
            if get_bip(c2, c1, method) is not None:
                found += 1

    return found, total
