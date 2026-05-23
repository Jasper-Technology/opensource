---
sidebar_position: 4
---

# Property Packages

Property packages define the thermodynamic models used to calculate phase equilibrium, enthalpies, and densities. In Quick mode, five packages are available natively. Rigorous mode adds UNIQUAC and eNRTL via the IDAES backend.

## Quick Mode Packages (In-Browser)

### Ideal

Simple property calculations assuming ideal gas and ideal liquid behavior.

| Aspect | Detail |
|--------|--------|
| VLE model | Raoult's Law: `Ki = Psat,i(T) / P` |
| Vapor pressure | Lee-Kesler correlation (boiling-point anchored, 1-3% error) |
| Liquid density | Rackett equation |
| Enthalpy | Ideal gas: `H = Hf + ∫Cp dT` |
| Entropy | `S = ∫(Cp/T)dT - R·ln(P/Pref)` |
| Best for | Light gases, similar-molecule mixtures, screening studies |

:::tip
Use Ideal for initial flowsheet debugging. It converges fastest and helps isolate topology issues from thermodynamic issues.
:::

### PR (Peng-Robinson)

The industry-standard cubic EOS for oil and gas applications. **Now available in Quick mode.**

| Aspect | Detail |
|--------|--------|
| EOS | `P = RT/(V-b) - a(T)/[V(V+b) + b(V-b)]` |
| Flash | Phi-phi: iterative K from fugacity coefficient ratios |
| Enthalpy | Ideal gas + PR departure function |
| Entropy | Ideal gas + PR departure function |
| Density | From PR compressibility factor Z |
| Best for | Hydrocarbons, natural gas, high-pressure, supercritical |

PR provides rigorous VLE via fugacity coefficients, solving the cubic equation analytically (Cardano's method) and selecting the smallest Z root for liquid, largest for vapor.

### SRK (Soave-Redlich-Kwong)

Classic cubic EOS for hydrocarbon systems and gas processing.

| Aspect | Detail |
|--------|--------|
| EOS | `P = RT/(V-b) - a(T)/[V(V+b)]` |
| Flash | Phi-phi with SRK fugacity coefficients |
| Enthalpy | Ideal gas + cubic departure function |
| Entropy | Ideal gas + cubic departure function |
| Density | From SRK compressibility factor Z |
| Best for | Hydrocarbon screening, gas transmission, vapor-liquid checks |

### RK (Redlich-Kwong)

Legacy cubic EOS with a temperature-dependent attraction term.

| Aspect | Detail |
|--------|--------|
| EOS | `P = RT/(V-b) - a(T)/[V(V+b)]` |
| Flash | Phi-phi with RK fugacity coefficients |
| Enthalpy | Ideal gas + cubic departure function |
| Entropy | Ideal gas + cubic departure function |
| Density | From RK compressibility factor Z |
| Best for | Older design correlations, quick hydrocarbon screening |

### NRTL (Non-Random Two-Liquid)

Activity coefficient model for non-ideal liquid mixtures. **Now available in Quick mode.**

| Aspect | Detail |
|--------|--------|
| Liquid phase | NRTL activity coefficients (gamma) |
| VLE | Modified Raoult's: `Ki = γi · Psat,i / P` |
| BIP database | ~20 common pairs (water-alcohol, amine-water, hydrocarbons) |
| Vapor phase | Ideal gas |
| Best for | Polar mixtures, alcohol-water systems, azeotropes |

The NRTL flash iterates K-values with composition-dependent activity coefficients until convergence.

#### Available BIP Pairs

| System | Pairs |
|--------|-------|
| Water-Alcohol | H2O/EtOH, H2O/MeOH |
| Water-Organic | H2O/Acetone, H2O/Acetic acid, H2O/Ethyl acetate |
| Amine-Water | MEA/H2O, DEA/H2O, MDEA/H2O |
| Hydrocarbon | Benzene/Cyclohexane, Benzene/Toluene, n-Hexane/Benzene |
| Alcohol-Organic | EtOH/Benzene, MeOH/Chloroform, MeOH/Benzene |
| Organic-Organic | Acetone/Chloroform, Acetone/Benzene |

:::warning
Pairs without BIP data fall back to ideal behavior (γ = 1). If your system needs specific BIPs not in the database, use Rigorous mode or contribute new BIPs.
:::

## Rigorous Mode Packages (IDAES Backend)

### SRK (Soave-Redlich-Kwong)

Cubic equation of state with Soave's alpha function.

| Aspect | Detail |
|--------|--------|
| EOS | `P = RT/(V-b) - a(T)/[V(V+b)]` |
| Best for | Hydrocarbons, natural gas processing, refinery applications |

### UNIQUAC (Universal Quasi-Chemical)

Activity coefficient model based on local composition theory.

| Aspect | Detail |
|--------|--------|
| Parameters | Binary interaction parameters, molecular r and q values |
| Best for | Complex mixtures, polymer solutions, very different molecule sizes |

### eNRTL (Electrolyte NRTL)

Extended NRTL model for ionic species.

| Aspect | Detail |
|--------|--------|
| Parameters | Electrolyte binary interaction parameters |
| Best for | Acid gas treating (CO2/H2S in amine), saline solutions |

## Selection Guide

| System Type | Quick Mode | Rigorous |
|-------------|-----------|----------|
| Light hydrocarbons, natural gas | PR or SRK | SRK or PR |
| Legacy cubic screening | RK | RK |
| High-pressure / supercritical | PR | PR |
| Alcohol-water, polar organics | NRTL | NRTL |
| Azeotropic distillation | NRTL | NRTL |
| Amine gas treating | NRTL | eNRTL |
| Polymer solutions | Ideal | UNIQUAC |
| Screening / debugging | Ideal | Ideal |

## Implementation

The Quick mode engine uses a `PropertyPackage` interface:

```typescript
interface PropertyPackage {
  calculateKValues(components, T, P): Record<string, number>;
  flash(z, T, P, components): FlashResult;
  liquidDensity(composition, T, P): number;
  vaporDensity(composition, T, P): number;
  mixtureEnthalpy(composition, T, P, phase?): number;
  mixtureEntropy(composition, T, P, phase?): number;
}
```

Factory: `getPropertyPackage('PR')` returns the appropriate implementation.

Source: `src/sim/thermo/propertyMethod.ts`
