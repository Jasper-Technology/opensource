---
sidebar_position: 8
---

# Reactors

Jasper supports seven reactor types. All use IDAES reactor models in rigorous mode.

## RCSTR — Continuous Stirred Tank Reactor

Agitated vessel operating at steady state where outlet composition equals the bulk composition inside the vessel.

| Parameter | Type | Unit | Description |
|-----------|------|------|-------------|
| volume | Quantity | m³, L | Reactor volume |
| conversion | Number | - | Fractional conversion of key component |
| T | Quantity | °C, K | Operating temperature (isothermal) |

## RPfr — Plug Flow Reactor

Tubular reactor where composition varies along the axial direction.

| Parameter | Type | Unit | Description |
|-----------|------|------|-------------|
| length | Quantity | m | Tube length |
| diameter | Quantity | m | Tube diameter |
| T | Quantity | °C, K | Operating temperature (isothermal or profile) |

## RBatch — Batch Reactor

Time-dependent reactor that follows a fill-react-drain cycle.

| Parameter | Type | Unit | Description |
|-----------|------|------|-------------|
| volume | Quantity | m³, L | Reactor volume |
| time | Quantity | s, min, h | Reaction time |
| T | Quantity | °C, K | Operating temperature |

## RStoic — Stoichiometric Reactor

Simple conversion-based reactor defined by stoichiometry and fractional conversion.

| Parameter | Type | Unit | Description |
|-----------|------|------|-------------|
| conversion | Number | - | Fractional conversion of key component |
| stoichiometry | Object | - | Reaction stoichiometry map |

## RYield — Yield Reactor

Reactor with a specified product distribution (mass or mole yields).

| Parameter | Type | Unit | Description |
|-----------|------|------|-------------|
| yields | Object | - | Product yield fractions |

## REquil — Equilibrium Reactor

Computes equilibrium composition at specified temperature and pressure via Gibbs minimization with equilibrium constraints.

| Parameter | Type | Unit | Description |
|-----------|------|------|-------------|
| T | Quantity | °C, K | Equilibrium temperature |
| P | Quantity | bar, Pa | Equilibrium pressure |

## RGibbs — Gibbs Reactor

Full Gibbs free energy minimization with no reaction specification required.

| Parameter | Type | Unit | Description |
|-----------|------|------|-------------|
| T | Quantity | °C, K | Operating temperature |
| P | Quantity | bar, Pa | Operating pressure |

## Common Ports

All reactor types share the same port layout:

| Port | Direction | Description |
|------|-----------|-------------|
| in | Input | Feed stream |
| out | Output | Product stream |
