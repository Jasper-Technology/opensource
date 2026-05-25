---
sidebar_position: 3
---

# Vapor-Liquid Equilibrium

VLE calculations determine phase splits and compositions.

:::tip
The Raoult's Law VLE described below applies to Quick mode when the **Ideal** property method is selected. Quick mode also supports **PR** (fugacity / phi-phi) and **NRTL** (activity / gamma-phi) for non-ideal systems. In **Rigorous mode** (DWSIM), VLE is handled by the selected DWSIM property package — cubic EOS (PR, SRK), activity (NRTL, UNIQUAC, UNIFAC), IAPWS-IF97 steam, or DWSIM electrolytes.
:::

## K-value calculation (Quick mode, Ideal)

Using Raoult's Law:

```
Ki = Psat_i(T) / P
```

## Vapor Pressure (Antoine)

```
log₁₀(Psat) = A - B/(T + C)
```

```typescript
export function getVaporPressure(componentId: string, T_K: number): number {
  const comp = componentData[componentId];
  if (!comp?.antoine) return 0;
  
  const [A, B, C] = comp.antoine;
  const T_C = T_K - 273.15;
  const P_mmHg = Math.pow(10, A - B / (T_C + C));
  return P_mmHg * 133.322; // Pa
}
```

## Flash Calculation

Rachford-Rice equation:

```
Σ zi(Ki - 1) / (1 + V(Ki - 1)) = 0
```

## Limitations (Quick mode, Ideal package)

- Ideal liquid solution (γ = 1)
- Ideal gas phase (φ = 1)
- No azeotrope prediction

Switch Quick mode to **PR** or **NRTL** to remove these limitations within the browser. For DWSIM's broader package set (SRK, UNIQUAC, UNIFAC, IAPWS-IF97 steam, electrolytes), switch to **Rigorous mode**.
