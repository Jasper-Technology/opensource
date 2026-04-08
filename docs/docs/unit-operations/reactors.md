---
sidebar_position: 8
---

# Reactors

Jasper supports seven reactor types. In Quick mode, all reactor types support stoichiometric conversion with heat of reaction and adiabatic/isothermal modes. REquil and RGibbs additionally compute equilibrium extent from Keq. Rigorous mode uses IDAES reactor models.

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

## Quick Mode Features

### Heat of Reaction

All reactor types compute heat of reaction at temperature T:

```
ΔHrxn(T) = Σ(νi · Hf,i) + ∫[Σ(νi · Cp,i)]dT from 298.15K to T
```

### Adiabatic Mode (default)

Outlet temperature changes due to reaction heat:

```
Tout = Tin - Qrxn / (F · Cp,mix)
```

Exothermic reactions (ΔH < 0) raise the outlet temperature. Endothermic reactions lower it.

### Isothermal Mode

Set `mode: 'isothermal'` in params. Outlet T equals inlet T; the heat duty equals -Qrxn.

### Equilibrium (REquil / RGibbs)

For equilibrium reactions, the extent is found by bisection on:

```
Keq = exp(-ΔG / RT)
```

Until the reaction quotient Q equals Keq.

### Example: Water-Gas Shift

```typescript
// CO + H2O → CO2 + H2, ΔH = -41.2 kJ/mol
reactions: [{
  id: 'wgs',
  stoichiometry: { CO: -1, H2O: -1, CO2: 1, H2: 1 },
  type: 'rate',
}]
// With 90% conversion, adiabatic mode → outlet T rises
```

### Block Results

| Result | Unit | Description |
|--------|------|-------------|
| duty | kJ/h | Heat duty (0 for adiabatic) |
| conversion | - | Actual conversion achieved |
| Q_rxn | kJ/h | Total heat of reaction |
| T_out | K | Outlet temperature |

## Common Ports

All reactor types share the same port layout:

| Port | Direction | Description |
|------|-----------|-------------|
| in | Input | Feed stream |
| out | Output | Product stream |
