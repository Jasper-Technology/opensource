---
sidebar_position: 3
---

# Vapor-Liquid Equilibrium

VLE calculations determine phase splits and compositions at given temperature and pressure.

## K-Value Calculation

For ideal mixtures, K-values are calculated using Raoult's Law:

```
K_i = Psat_i(T) / P
```

Where:
- `K_i` is the equilibrium ratio for component i
- `P_i^sat` is the saturation pressure at temperature T
- `P` is the system pressure

## Vapor Pressure (Antoine Equation)

Saturation pressure is calculated using the Antoine equation:

```
log10(Psat) = A - B / (T + C)
```

Where coefficients A, B, C are component-specific.

```typescript
export function getVaporPressure(componentId: string, T_K: number): number {
  const comp = componentData[componentId];
  if (!comp?.antoine) return 0;

  const [A, B, C] = comp.antoine;
  const T_C = T_K - 273.15;

  // Antoine equation gives pressure in mmHg
  const P_mmHg = Math.pow(10, A - B / (T_C + C));

  // Convert to Pa
  return P_mmHg * 133.322;
}
```

## Flash Calculation

The flash calculation solves for vapor fraction using the Rachford-Rice equation:

```
sum( z_i * (K_i - 1) / (1 + V * (K_i - 1)) ) = 0
```

Where:
- `z_i` is the feed composition
- `V` is the vapor fraction (0 to 1)

### Algorithm

1. Calculate K-values from vapor pressures
2. Check if mixture is subcooled liquid (all Ki < 1) or superheated vapor (all Ki > 1)
3. If two-phase, solve Rachford-Rice equation using bisection
4. Calculate vapor and liquid compositions

```typescript
export function flash(
  composition: Record<string, number>,
  T_K: number,
  P_Pa: number
): FlashResult {
  // Calculate K-values
  const K: Record<string, number> = {};
  for (const compId of Object.keys(composition)) {
    const Psat = getVaporPressure(compId, T_K);
    K[compId] = Psat / P_Pa;
  }

  // Check phase boundaries
  const Kmin = Math.min(...Object.values(K));
  const Kmax = Math.max(...Object.values(K));

  if (Kmax < 1) {
    return { phase: 'L', V: 0, x: composition, y: {} };
  }
  if (Kmin > 1) {
    return { phase: 'V', V: 1, x: {}, y: composition };
  }

  // Two-phase: solve Rachford-Rice
  const V = solveRachfordRice(composition, K);

  // Calculate phase compositions
  const x: Record<string, number> = {};
  const y: Record<string, number> = {};

  for (const [compId, z] of Object.entries(composition)) {
    x[compId] = z / (1 + V * (K[compId] - 1));
    y[compId] = K[compId] * x[compId];
  }

  return { phase: 'VL', V, x, y };
}
```

## Limitations

Current VLE implementation assumes:
- Ideal liquid solution (activity coefficients = 1)
- Ideal gas phase (fugacity coefficients = 1)
- No azeotrope prediction

For non-ideal mixtures, NRTL or UNIQUAC activity coefficients are needed.
