---
sidebar_position: 1
---

# Thermodynamics Overview

Jasper's thermodynamic engine provides rigorous property calculations for process simulation. Three property methods are available, selectable per-project.

## Property Methods

| Method | Best For | K-Value Model |
|--------|----------|---------------|
| **Ideal** | Ideal mixtures, low pressure | Raoult's Law (K = Psat/P) |
| **Peng-Robinson (PR)** | Hydrocarbons, gases, high pressure | Fugacity coefficients (phi-phi) |
| **NRTL** | Polar/non-ideal liquids (alcohol-water, amines) | Activity coefficients (gamma-phi) |

Set the property method in `project.thermodynamics.propertyMethod`:

```typescript
thermodynamics: { propertyMethod: 'NRTL' }  // or 'Ideal', 'PR'
```

## Property Calculation Flow

```
Component Data (MW, Tc, Pc, omega, Tb, Hf, Cp coefficients)
         │
         ▼
┌─────────────────┐
│  Heat Capacity  │  →  Cp(T) = a + bT + cT² + dT³ + eT⁴
└─────────────────┘
         │
         ▼
┌─────────────────┐
│    Enthalpy     │  →  H(T) = Hf + ∫Cp dT  (+departure for PR)
└─────────────────┘
         │
         ▼
┌─────────────────┐
│    Entropy      │  →  S(T,P) = ∫(Cp/T)dT - R·ln(P/Pref)  (+departure)
└─────────────────┘
         │
         ▼
┌─────────────────┐
│ Vapor Pressure  │  →  Lee-Kesler: ln(Pr) = f0(Tr) + ω·f1(Tr)
└─────────────────┘
         │
         ▼
┌─────────────────┐
│  Liquid Density │  →  Rackett: Vs = (RTc/Pc)·Zra^(1+(1-Tr)^(2/7))
└─────────────────┘
         │
         ▼
┌─────────────────┐
│      VLE        │  →  Ideal: Ki = Psat/P
│                 │     PR: Ki = φL/φV  (fugacity)
│                 │     NRTL: Ki = γi·Psat/P
└─────────────────┘
```

## Capabilities

| Property | Method | Accuracy |
|----------|--------|----------|
| Heat capacity (Cp) | DIPPR polynomial (5 coeff) | < 1% |
| Enthalpy | Cp integration + departure functions | < 2% |
| Entropy | Cp/T integration + departure functions | < 2% |
| Vapor pressure | Lee-Kesler (boiling-point anchored) | < 2% at Tb |
| Liquid density | Rackett equation | 5-12% |
| VLE (ideal) | Raoult's Law | Ideal systems only |
| VLE (PR) | Phi-phi flash with fugacity coefficients | Hydrocarbons ±5% |
| VLE (NRTL) | Gamma-phi with BIP database (~20 pairs) | Polar ±5% |
| Heat of reaction | ΔHf + ΔCp integration | < 2% |

## Units

All internal calculations use SI units:

| Property | Internal Unit | StreamState Unit |
|----------|---------------|-----------------|
| Temperature | K | K |
| Pressure | Pa | bar |
| Flow | kmol/h | kmol/h |
| Enthalpy | kJ/mol | kJ/mol |
| Heat capacity | J/(mol·K) | J/(mol·K) |
| Density | kg/m³ | kg/m³ |
| Entropy | kJ/(mol·K) | kJ/(mol·K) |

## Source Files

| File | Purpose |
|------|---------|
| `src/sim/thermo/properties.ts` | Cp, enthalpy, entropy, Pvap, density, VLE |
| `src/sim/thermo/pengRobinson.ts` | PR EOS: cubic solver, fugacity, departure functions |
| `src/sim/thermo/nrtl.ts` | NRTL activity coefficients |
| `src/sim/thermo/bipDatabase.ts` | Binary interaction parameters (~20 common pairs) |
| `src/sim/thermo/propertyMethod.ts` | PropertyPackage interface and factory |
| `src/sim/thermo/componentDatabase.ts` | 70+ component property data |
