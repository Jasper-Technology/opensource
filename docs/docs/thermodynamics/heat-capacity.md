---
sidebar_position: 2
---

# Heat Capacity & Thermodynamic Properties

Heat capacity, enthalpy, entropy, and heat of reaction calculations.

## Heat Capacity

```
Cp(T) = a + b·T + c·T² + d·T³ + e·T⁴
```

Where:
- `T` is temperature in Kelvin
- `a, b, c, d, e` are DIPPR coefficients from the component database
- `Cp` is in J/(mol·K)

## Enthalpy

```
H(T) = Hf + ∫Cp dT from 298.15K to T
```

For PR property package, a departure function is added:

```
H = H_ig + H_dep(T, P, Z, a_mix, b_mix, da/dT)
```

## Entropy

```
S(T, P) = ∫(Cp/T)dT from 298.15K to T  -  R·ln(P/Pref)  -  R·Σ(xi·ln(xi))
```

For PR, a departure function is added. Entropy is used for:
- Isentropic compressor/turbine calculations
- Equilibrium constant estimation (ΔG = ΔH - TΔS)

## Heat of Reaction

```
ΔHrxn(T) = Σ(νi · Hf,i) + ∫[Σ(νi · Cp,i)]dT from 298.15K to T
```

Used by reactor models for:
- Adiabatic temperature rise/drop
- Isothermal heat duty
- Equilibrium constant from ΔG

## Example Values

| Component | Cp at 298K | Hf (kJ/mol) |
|-----------|-----------|-------------|
| Water | 33.6 J/(mol·K) | -241.83 |
| Methane | 35.7 J/(mol·K) | -74.52 |
| Nitrogen | 29.1 J/(mol·K) | 0.0 |
| CO2 | 37.1 J/(mol·K) | -393.51 |
| CO | 29.1 J/(mol·K) | -110.53 |
| Ethanol | 65.6 J/(mol·K) | -234.95 |

## Mixture Properties

```typescript
// Mixture Cp (mole-fraction weighted)
function idealGasCpMix(composition, T) {
  return Σ xi · Cp_i(T)
}

// Mixture enthalpy
function mixtureEnthalpy(composition, T, P) {
  return Σ xi · H_i(T)  // + departure for PR
}
```
