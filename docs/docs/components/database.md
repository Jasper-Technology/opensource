---
sidebar_position: 1
---

# Component Database

Quick mode ships with 70+ chemicals; Rigorous mode draws from DWSIM's ~500-compound database.

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

## Quick mode (Jasper) — 70+ components

Quick mode bundles 70+ validated components with property data sourced from NIST, DIPPR, Perry's Chemical Engineers' Handbook, and the RPP (Reid, Prausnitz & Poling) database. Each component includes:

- Critical properties (Tc, Pc, Vc)
- Acentric factors
- Wagner / Antoine / Lee-Kesler vapor pressure coefficients
- Cp polynomial coefficients
- NRTL BIPs for ~20 common pairs

This enables PR, NRTL, and Ideal calculations entirely in the browser.

## Rigorous mode (DWSIM) — ~500 components

When you switch to Rigorous mode, Jasper hands the flowsheet to the DWSIM backend, which uses **DWSIM's compound database** (~500 compounds). Jasper components are resolved against DWSIM via CAS number first, then name, then formula. If a Quick-mode component isn't in DWSIM, the simulation fails with `"Compound not found"` — add a CAS number to the Jasper component to fix.

DWSIM's database supports cubic EOS (PR, SRK), activity coefficient models (NRTL, UNIQUAC, UNIFAC), IAPWS-IF97 steam tables, and DWSIM's electrolyte property packages.

## Data sources

- NIST Chemistry WebBook
- DIPPR 801 Database
- Perry's Chemical Engineers' Handbook
- RPP (Reid, Prausnitz & Poling)
- DWSIM compound database (Rigorous mode)
