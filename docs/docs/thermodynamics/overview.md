---
sidebar_position: 1
---

# Thermodynamics Overview

Jasper's thermodynamic engine calculates physical properties required for process simulation.

## Capabilities

| Property | Method | Status |
|----------|--------|--------|
| Heat capacity (Cp) | Polynomial correlation | Implemented |
| Enthalpy | Integration of Cp | Implemented |
| Vapor pressure | Antoine equation | Implemented |
| VLE | Raoult's Law | Implemented |
| Density | Ideal gas / liquid correlations | Partial |

## Property Calculation Flow

```
Component Data (MW, Tc, Pc, Cp coefficients, Antoine coefficients)
         │
         ▼
┌─────────────────┐
│  Heat Capacity  │  →  Cp(T) = a + bT + cT² + dT³
└─────────────────┘
         │
         ▼
┌─────────────────┐
│    Enthalpy     │  →  H(T) = ∫Cp dT + Hf
└─────────────────┘
         │
         ▼
┌─────────────────┐
│ Vapor Pressure  │  →  log(Psat) = A - B/(T+C)
└─────────────────┘
         │
         ▼
┌─────────────────┐
│      VLE        │  →  Ki = Psat,i / P
└─────────────────┘
```

## Rigorous Mode (IDAES)

When rigorous mode is selected, Jasper delegates thermodynamic calculations to the [IDAES](https://idaes.org/) framework. This provides equation-oriented solving with a choice of property packages:

| Property Package | Type | Best For |
|-----------------|------|----------|
| Ideal | Activity coefficient (gamma = 1) | Ideal mixtures, experiment comparison |
| SRK | Cubic EOS | Hydrocarbon systems, gas processing |
| PR (Peng-Robinson) | Cubic EOS | General-purpose, hydrocarbon VLE |
| NRTL | Activity coefficient | Polar / non-ideal liquid mixtures |
| UNIQUAC | Activity coefficient | Strongly non-ideal liquids, LLE |
| eNRTL | Electrolyte activity coefficient | Electrolyte and amine systems |

For a detailed guide on selecting and configuring property packages, see [Property Packages](/thermodynamics/property-packages).

## Assumptions

**Quick mode assumptions** (these do not apply to rigorous mode):
- Ideal gas behavior for vapor phase
- Ideal liquid solutions (Raoult's Law)
- No solid phases

**Planned improvements (Quick mode):**
- Steam tables (IAPWS-IF97)

:::tip
Peng-Robinson and SRK equations of state, as well as NRTL and UNIQUAC activity coefficient models, are already available in **rigorous mode**.
:::

## Units

All internal calculations use SI units:

| Property | Internal Unit |
|----------|---------------|
| Temperature | K |
| Pressure | Pa |
| Flow | mol/s |
| Enthalpy | J/mol |
| Heat capacity | J/(mol·K) |
