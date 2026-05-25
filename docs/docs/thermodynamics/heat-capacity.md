---
sidebar_position: 2
---

# Heat Capacity

Heat capacity (Cp) is calculated using polynomial correlations.

## Correlation

```
Cp(T) = a + b*T + c*T² + d*T³
```

Where:
- `T` is temperature in Kelvin
- `a, b, c, d` are component-specific coefficients
- `Cp` is in J/(mol·K)

## Implementation

```typescript
export function getCp(componentId: string, T_K: number): number {
  const comp = componentData[componentId];
  if (!comp?.Cp_coef) return 29.1;
  
  const [a, b, c, d] = comp.Cp_coef;
  return a + b * T_K + c * T_K ** 2 + d * T_K ** 3;
}
```

## Example Values

| Component | Cp at 298K |
|-----------|------------|
| Water | 33.6 J/(mol·K) |
| Methane | 35.7 J/(mol·K) |
| Nitrogen | 29.1 J/(mol·K) |

## Mixture Heat Capacity

```typescript
export function getMixtureCp(composition: Record<string, number>, T_K: number): number {
  let totalCp = 0;
  for (const [compId, moleFrac] of Object.entries(composition)) {
    totalCp += moleFrac * getCp(compId, T_K);
  }
  return totalCp;
}
```
