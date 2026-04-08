---
sidebar_position: 9
---

# Separation Columns

Multi-stage vapor-liquid contacting equipment. Quick mode uses shortcut methods; rigorous mode uses IDAES tray-by-tray models.

## DistillationColumn

### Quick Mode: Fenske-Underwood-Gilliland

Shortcut distillation design using the classic FUG method:

1. **Fenske**: Minimum stages from relative volatility and key recovery specs
2. **Underwood**: Minimum reflux from feed composition and relative volatility
3. **Gilliland**: Actual stages from the Gilliland correlation

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| lightKey | String | First component | Light key component (formula) |
| heavyKey | String | Last component | Heavy key component (formula) |
| lkRecovery | Number | 0.99 | Fraction of LK recovered in distillate |
| hkRecovery | Number | 0.01 | Fraction of HK in distillate |
| refluxRatio | Number | 1.5 | Actual reflux ratio (L/D) |
| P | Quantity | Inlet P | Column pressure |

Relative volatilities are computed from the active property package's K-values, so PR and NRTL can be used for non-ideal systems.

#### Block Results

| Result | Unit | Description |
|--------|------|-------------|
| N_min | - | Minimum stages (Fenske) |
| R_min | - | Minimum reflux ratio (Underwood) |
| N_actual | - | Actual number of stages (Gilliland) |
| N_feed | - | Optimal feed stage |
| alpha_lk_hk | - | Relative volatility LK/HK |
| Q_condenser | kJ/h | Condenser duty |
| Q_reboiler | kJ/h | Reboiler duty |

#### Example

50/50 benzene-toluene at 1 bar with R=2.0:
- Distillate: 99.0% benzene, Bottoms: 99.0% toluene
- Nmin ≈ 9.5, Nactual ≈ 17

### Rigorous Mode: MESH Equations

IDAES tray-by-tray model with full MESH equations (Material balance, Equilibrium, Summation, entHalpy balance) on each stage.

| Parameter | Type | Unit | Description |
|-----------|------|------|-------------|
| nStages | Number | - | Number of trays |
| feedStage | Number | - | Feed tray location (counted from top) |
| refluxRatio | Number | - | Reflux ratio (L/D) |
| boilupRatio | Number | - | Boilup ratio (V/B) |
| condenserP | Quantity | bar, Pa | Condenser pressure |

### Ports

| Port | Direction | Description |
|------|-----------|-------------|
| in | Input | Feed stream |
| distillate | Output | Overhead liquid product |
| bottoms | Output | Bottom liquid product |

## Absorber

Gas-liquid contactor for removing components from a gas stream into a liquid solvent.

### Quick Mode: Kremser Equation

For each solute component, the Kremser equation determines the fraction absorbed:

```
Absorption factor:  A = L / (m · G)
Fraction absorbed = (A^(N+1) - A) / (A^(N+1) - 1)
```

Where `m` is the K-value (equilibrium slope) from the active property package.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| stages | Int | 10 | Number of theoretical stages |

#### Block Results

| Result | Unit | Description |
|--------|------|-------------|
| N_stages | - | Number of stages |
| totalAbsorbed | kmol/h | Total moles absorbed |
| L_over_G | - | Liquid-to-gas ratio |

### Ports

| Port | Direction | Description |
|------|-----------|-------------|
| gas-in | Input | Gas feed (bottom) |
| gas-out | Output | Cleaned gas (top) |
| liquid-in | Input | Solvent feed (top) |
| liquid-out | Output | Rich solvent (bottom) |

## Stripper

Regenerates loaded solvent by removing dissolved components as vapor.

### Quick Mode: Kremser Stripping

```
Stripping factor:  S = m · V / L
Fraction stripped = (S^(N+1) - S) / (S^(N+1) - 1)
```

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| stages | Int | 8 | Number of theoretical stages |
| P | Quantity | Feed P | Operating pressure |

#### Block Results

| Result | Unit | Description |
|--------|------|-------------|
| N_stages | - | Number of stages |
| totalStripped | kmol/h | Total moles stripped to overhead |

### Ports

| Port | Direction | Description |
|------|-----------|-------------|
| feed | Input | Rich liquid feed |
| overhead | Output | Stripped vapor |
| bottoms | Output | Lean liquid |
