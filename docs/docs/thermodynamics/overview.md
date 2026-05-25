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

## Property method availability per engine

Each engine supports a different set of property methods. The IDAES column applies when optimization is invoked through the Jasper agent.

| Method | Quick | Rigorous (DWSIM) | Optimize (IDAES, via agent) | Best for |
|--------|:-----:|:----------------:|:---------------------------:|----------|
| Ideal (Raoult's Law) | ✓ | ✓ | ✓ | Ideal mixtures, validation |
| PR (Peng-Robinson) | ✓ | ✓ | ✓ | General-purpose VLE, hydrocarbons |
| SRK (Soave-Redlich-Kwong) | — | ✓ | ✓ | Hydrocarbons, gas processing |
| NRTL | ✓ | ✓ | ✓ | Polar / non-ideal liquids |
| UNIQUAC | — | ✓ | ✓ | Strongly non-ideal liquids, LLE |
| UNIFAC | — | ✓ | — | Group contribution estimates |
| eNRTL | — | — | ✓ | Electrolytes, amines |
| IAPWS-IF97 (steam) | — | ✓ | — | Steam cycles, utilities |
| Electrolytes (DWSIM) | — | ✓ | — | Aqueous electrolyte systems |

For a detailed guide on selecting and configuring property packages, see [Property Packages](/thermodynamics/property-packages).

## Assumptions

**Quick mode** (when using the Ideal property method specifically):
- Ideal gas behavior for vapor phase
- Ideal liquid solutions (Raoult's Law)
- No solid phases

Quick mode also supports PR and NRTL with full fugacity / activity coefficient calculations — pick those for non-ideal systems before reaching for a backend.

**Planned improvements (Quick mode):**
- Steam tables (IAPWS-IF97)
- UNIQUAC / UNIFAC
- Henry's Law for dissolved gases

:::tip
For electrolytes, amines, and steam cycles, use **Rigorous mode** (DWSIM provides IAPWS-IF97 steam tables and electrolyte property packages). For equation-oriented optimization with eNRTL, ask the agent — it routes through the IDAES backend.
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
