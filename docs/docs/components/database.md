---
sidebar_position: 1
---

# Component Database

Jasper includes thermodynamic data for 50+ chemicals.

## Light Gases

| ID | Name | Formula | MW |
|----|------|---------|-----|
| H2 | Hydrogen | H₂ | 2.02 |
| N2 | Nitrogen | N₂ | 28.01 |
| O2 | Oxygen | O₂ | 32.00 |
| CO2 | Carbon Dioxide | CO₂ | 44.01 |
| CH4 | Methane | CH₄ | 16.04 |

## Hydrocarbons

| ID | Name | Formula | MW |
|----|------|---------|-----|
| C2H6 | Ethane | C₂H₆ | 30.07 |
| C3H8 | Propane | C₃H₈ | 44.10 |
| nC4 | n-Butane | C₄H₁₀ | 58.12 |
| nC6 | n-Hexane | C₆H₁₄ | 86.18 |
| Benzene | Benzene | C₆H₆ | 78.11 |

## Alcohols

| ID | Name | Formula | MW |
|----|------|---------|-----|
| MeOH | Methanol | CH₃OH | 32.04 |
| EtOH | Ethanol | C₂H₅OH | 46.07 |
| H2O | Water | H₂O | 18.02 |

## Amines

| ID | Name | Formula | MW |
|----|------|---------|-----|
| MEA | Monoethanolamine | C₂H₇NO | 61.08 |
| MDEA | Methyldiethanolamine | C₅H₁₃NO₂ | 119.16 |
| NH3 | Ammonia | NH₃ | 17.03 |

## Rigorous Mode Components

In rigorous mode (IDAES), **70+ components** are available with extended property data sourced from NIST, DIPPR, Perry's Chemical Engineers' Handbook, and the RPP (Reid, Prausnitz & Poling) database. The rigorous component data includes:

- Critical properties (Tc, Pc, Vc)
- Acentric factors
- Wagner vapor pressure coefficients
- Equation-of-state interaction parameters

This expanded dataset enables accurate calculations with cubic EOS (SRK, PR) and activity coefficient models (NRTL, UNIQUAC, eNRTL).

## Data Sources

- NIST Chemistry WebBook
- DIPPR 801 Database
- Perry's Chemical Engineers' Handbook
- RPP (Reid, Prausnitz & Poling) -- used in rigorous mode
