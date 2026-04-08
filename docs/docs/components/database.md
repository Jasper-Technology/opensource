---
sidebar_position: 1
---

# Component Database

Jasper includes thermodynamic data for 70+ chemicals with validated properties from NIST, DIPPR, and Perry's.

## Data Per Component

Each component stores:

| Property | Symbol | Unit | Source |
|----------|--------|------|--------|
| Molecular weight | MW | g/mol | NIST |
| Critical temperature | Tc | K | DIPPR |
| Critical pressure | Pc | bar | DIPPR |
| Acentric factor | omega | - | DIPPR |
| Normal boiling point | Tb | K | NIST |
| Heat of formation | Hf | kJ/mol | NIST |
| Cp coefficients | a,b,c,d,e | - | DIPPR |

## Light Gases

| ID | Name | Formula | MW | Tc (K) | Pc (bar) |
|----|------|---------|-----|--------|----------|
| H2 | Hydrogen | H2 | 2.02 | 33.2 | 13.1 |
| N2 | Nitrogen | N2 | 28.01 | 126.2 | 34.0 |
| O2 | Oxygen | O2 | 32.00 | 154.6 | 50.4 |
| CO2 | Carbon Dioxide | CO2 | 44.01 | 304.1 | 73.8 |
| CO | Carbon Monoxide | CO | 28.01 | 132.9 | 35.0 |
| CH4 | Methane | CH4 | 16.04 | 190.6 | 46.0 |

## Hydrocarbons

| ID | Name | Formula | MW | Tc (K) | Pc (bar) |
|----|------|---------|-----|--------|----------|
| C2H6 | Ethane | C2H6 | 30.07 | 305.3 | 48.7 |
| C3H8 | Propane | C3H8 | 44.10 | 369.8 | 42.5 |
| n-C4H10 | n-Butane | C4H10 | 58.12 | 425.1 | 38.0 |
| C6H6 | Benzene | C6H6 | 78.11 | 562.2 | 48.9 |
| C7H8 | Toluene | C7H8 | 92.14 | 591.8 | 41.1 |

## Alcohols

| ID | Name | Formula | MW | Tc (K) | Pc (bar) |
|----|------|---------|-----|--------|----------|
| CH3OH | Methanol | CH3OH | 32.04 | 512.6 | 81.0 |
| C2H5OH | Ethanol | C2H5OH | 46.07 | 513.9 | 61.5 |
| H2O | Water | H2O | 18.02 | 647.1 | 220.6 |

## Amines

| ID | Name | Formula | MW | Tc (K) | Pc (bar) |
|----|------|---------|-----|--------|----------|
| C2H7NO | MEA | C2H7NO | 61.08 | 678.2 | 71.2 |
| C5H13NO3 | MDEA | C5H13NO3 | 119.16 | 741.9 | 38.6 |
| NH3 | Ammonia | NH3 | 17.03 | 405.4 | 113.5 |

## NRTL BIP Coverage

The following binary pairs have NRTL interaction parameters in `bipDatabase.ts`:

| System | Pairs |
|--------|-------|
| Water-Alcohol | H2O/EtOH, H2O/MeOH |
| Water-Organic | H2O/Acetone, H2O/Acetic acid, H2O/Ethyl acetate |
| Amine-Water | MEA/H2O, DEA/H2O, MDEA/H2O |
| Hydrocarbon | Benzene/Cyclohexane, Benzene/Toluene, n-Hexane/Benzene |
| Alcohol-Organic | EtOH/Benzene, MeOH/Chloroform, MeOH/Benzene |
| Organic-Organic | Acetone/Chloroform, Acetone/Benzene |

Pairs without BIP data fall back to ideal behavior (gamma = 1).

## Data Sources

- NIST Chemistry WebBook
- DIPPR 801 Database
- Perry's Chemical Engineers' Handbook (9th ed.)
- Gmehling/Onken "Vapor-Liquid Equilibrium Data Collection" (NRTL BIPs)
