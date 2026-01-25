---
sidebar_position: 1
---

# Overview

Jasper's thermodynamic engine calculates physical properties required for process simulation.

## Current Capabilities

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
│  Heat Capacity  │ ──► Cp(T) = a + bT + cT² + dT³
└─────────────────┘
         │
         ▼
┌─────────────────┐
│    Enthalpy     │ ──► H(T) = ∫Cp dT + Hf
└─────────────────┘
         │
         ▼
┌─────────────────┐
│ Vapor Pressure  │ ──► log(Psat) = A - B/(T+C)
└─────────────────┘
         │
         ▼
┌─────────────────┐
│      VLE        │ ──► Ki = Psat,i / P
└─────────────────┘
```

## Assumptions and Limitations

**Current assumptions:**
- Ideal gas behavior for vapor phase
- Ideal liquid solutions (Raoult's Law)
- No solid phases
- Constant pressure heat capacities

**Planned improvements:**
- Peng-Robinson equation of state
- NRTL activity coefficient model
- Steam tables (IAPWS-IF97)

## Units

All internal calculations use SI units:

| Property | Internal Unit |
|----------|---------------|
| Temperature | K |
| Pressure | Pa |
| Flow | mol/s |
| Enthalpy | J/mol |
| Heat capacity | J/(mol·K) |

Unit conversion is handled at input/output boundaries.
