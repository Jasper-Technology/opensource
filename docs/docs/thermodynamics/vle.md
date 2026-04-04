---
sidebar_position: 3
---

# Vapor-Liquid Equilibrium

VLE calculations determine phase splits and compositions.

:::tip
The Raoult's Law VLE described below applies to **Quick mode** only. In **Rigorous mode**, VLE is handled by the selected equation of state (SRK, PR) using proper fugacity calculations, or by activity coefficient models (NRTL, UNIQUAC) for non-ideal liquid mixtures. Use rigorous mode for azeotropic, polar, or strongly non-ideal systems.
:::

## K-Value Calculation (Quick Mode)

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

## Limitations (Quick Mode)

- Ideal liquid solution (gamma = 1)
- Ideal gas phase (phi = 1)
- No azeotrope prediction

In **rigorous mode**, these limitations are removed. Cubic EOS models (SRK, PR) compute fugacity coefficients for both phases, and activity coefficient models (NRTL, UNIQUAC, eNRTL) capture liquid-phase non-ideality including azeotrope prediction.
