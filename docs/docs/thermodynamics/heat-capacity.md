---
sidebar_position: 2
---

# Heat Capacity

Heat capacity (Cp) is calculated using polynomial correlations as a function of temperature.

## Correlation

The ideal gas heat capacity is expressed as:

```
Cp(T) = a + b*T + c*T^2 + d*T^3
```

Where:
- `T` is temperature in Kelvin
- `a, b, c, d` are component-specific coefficients
- `Cp` is in J/(mol·K)

## Data Sources

Coefficients are sourced from:
- NIST Chemistry WebBook
- DIPPR database
- Perry's Chemical Engineers' Handbook

## Implementation

```typescript
// src/sim/thermo/properties.ts

export function getCp(componentId: string, T_K: number): number {
  const comp = componentData[componentId];
  if (!comp?.Cp_coef) {
    return 29.1; // Default for unknown components
  }

  const [a, b, c, d] = comp.Cp_coef;
  return a + b * T_K + c * T_K ** 2 + d * T_K ** 3;
}
```

## Example Values

| Component | a | b | c | d | Cp at 298K |
|-----------|---|---|---|---|------------|
| Water | 32.24 | 1.92e-3 | 1.06e-5 | -3.60e-9 | 33.6 J/(mol·K) |
| Methane | 19.25 | 5.21e-2 | 1.20e-5 | -1.13e-8 | 35.7 J/(mol·K) |
| Nitrogen | 29.00 | -2.20e-4 | 5.72e-6 | -2.87e-9 | 29.1 J/(mol·K) |

## Mixture Heat Capacity

For mixtures, heat capacity is calculated as a mole-fraction weighted average:

```
Cp_mix = sum(x_i * Cp_i)
```

```typescript
export function getMixtureCp(
  composition: Record<string, number>,
  T_K: number
): number {
  let totalCp = 0;
  for (const [compId, moleFrac] of Object.entries(composition)) {
    totalCp += moleFrac * getCp(compId, T_K);
  }
  return totalCp;
}
```
