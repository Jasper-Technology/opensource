---
sidebar_position: 4
---

# Property Methods

Jasper uses a **PropertyPackage** abstraction to dispatch thermodynamic calculations to the appropriate model. Each package implements the same interface, so the solver is model-agnostic.

## PropertyPackage Interface

```typescript
interface PropertyPackage {
  name: string;
  calculateKValues(components: string[], T: number, P_Pa: number): Record<string, number>;
  flash(z: Record<string, number>, T: number, P_Pa: number, components: string[]): FlashResult;
  liquidDensity(composition: Record<string, number>, T: number, P_Pa: number): number;
  vaporDensity(composition: Record<string, number>, T: number, P_Pa: number): number;
  mixtureEnthalpy(composition: Record<string, number>, T: number, P_Pa: number, phase?: 'V' | 'L'): number;
  mixtureEntropy(composition: Record<string, number>, T: number, P_Pa: number, phase?: 'V' | 'L'): number;
}
```

## Available Packages

### IdealPropertyPackage

- **K-values**: Raoult's Law — `K = Psat(T) / P`
- **Enthalpy**: Ideal gas — `H = Hf + ∫Cp dT`
- **Entropy**: Ideal gas — `S = ∫(Cp/T)dT - R·ln(P/Pref)`
- **Density**: Ideal gas law (vapor), Rackett equation (liquid)

Use when: all components are chemically similar, low pressure, no strong interactions.

### PRPropertyPackage (Peng-Robinson)

- **K-values**: Fugacity-based — iterative phi-phi flash
- **Enthalpy**: Ideal + PR departure function
- **Entropy**: Ideal + PR departure function
- **Density**: From PR compressibility factor Z

Use when: hydrocarbons, gases, high-pressure systems, supercritical conditions.

### NRTLPropertyPackage

- **K-values**: Modified Raoult's — `K = γ · Psat / P`
- **Activity coefficients**: NRTL model with BIP database
- **Enthalpy/Entropy**: Ideal gas (excess enthalpy not yet included)
- **Density**: Rackett equation for liquid

Use when: polar mixtures, alcohol-water, amine-water, organic-organic with known non-ideality.

## Factory

```typescript
import { getPropertyPackage } from './propertyMethod';

const pkg = getPropertyPackage('PR');        // Peng-Robinson
const pkg = getPropertyPackage('NRTL');      // NRTL activity coefficients
const pkg = getPropertyPackage('Ideal');     // Raoult's Law (default)
```

Recognized strings: `'PR'`, `'PENG-ROBINSON'`, `'SRK'`, `'NRTL'`, `'NRTL-RK'`, `'IDEAL'`, `'RAOULT'`.

## Choosing a Property Method

| System Type | Recommended Method | Why |
|-------------|-------------------|-----|
| Light hydrocarbons (C1-C10) | PR | Handles non-ideal vapor, high P |
| Natural gas processing | PR | Cryogenic, high-pressure VLE |
| Alcohol-water distillation | NRTL | Azeotrope, strong liquid non-ideality |
| Amine gas treating (CO2 capture) | NRTL | Polar, aqueous amine solutions |
| Ideal mixtures (benzene-toluene) | Ideal | Fastest, accurate enough |
| Air separation | PR | Cryogenic, multi-component |
| Classroom problems (ideal) | Ideal | Simplest, matches textbooks |

## Peng-Robinson Details

The PR EOS:

```
P = RT/(V-b) - a·α(T) / (V(V+b) + b(V-b))
```

- **Alpha function**: `α = [1 + κ(1 - √Tr)]²` where `κ = 0.37464 + 1.54226ω - 0.26992ω²`
- **Mixing rules**: van der Waals one-fluid (`a_mix = ΣΣ xi·xj·√(ai·aj)`)
- **Cubic solver**: Analytical Cardano's method for Z roots
- **Phase selection**: smallest Z for liquid, largest Z for vapor

## NRTL Details

```
ln(γi) = (Σj τji·Gji·xj) / (Σk Gki·xk) + Σj [xj·Gij/(Σk Gkj·xk)] · (τij - (Σm xm·τmj·Gmj)/(Σk Gkj·xk))
```

Where:
- `τij = aij + bij/T`
- `Gij = exp(-αij · τij)`
- Parameters from `bipDatabase.ts` (~20 common pairs)
