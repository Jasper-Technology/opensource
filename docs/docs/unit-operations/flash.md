---
sidebar_position: 5
---

# Flash Drum

A flash drum separates a feed stream into vapor and liquid phases at specified temperature and pressure.

## Parameters

| Parameter | Type | Unit | Description |
|-----------|------|------|-------------|
| T | Quantity | C, K, F | Flash temperature |
| P | Quantity | bar, Pa, psi | Flash pressure |

## Calculation Method

1. Convert inlet stream to flash conditions (T, P)
2. Calculate K-values using Raoult's Law
3. Solve Rachford-Rice equation for vapor fraction
4. Determine vapor and liquid compositions
5. Calculate outlet stream enthalpies

### Material Balance

```
F = V + L
F * z_i = V * y_i + L * x_i
```

### Phase Equilibrium

```
y_i = K_i * x_i
K_i = Psat_i(T) / P
```

### Energy Balance

```
F * H_F = V * H_V + L * H_L + Q
```

For adiabatic flash, Q = 0.

## Implementation

```typescript
// src/sim/blocks/flash.ts

export function solveFlash(
  inlet: StreamData,
  params: FlashParams
): { vapor: StreamData; liquid: StreamData } {
  const T_K = params.T;
  const P_Pa = params.P;

  // Perform flash calculation
  const result = flash(inlet.composition, T_K, P_Pa);

  // Calculate outlet flows
  const vaporFlow = inlet.flow * result.V;
  const liquidFlow = inlet.flow * (1 - result.V);

  // Calculate enthalpies
  const H_V = getMixtureEnthalpy(result.y, T_K, 'V');
  const H_L = getMixtureEnthalpy(result.x, T_K, 'L');

  return {
    vapor: {
      T: T_K,
      P: P_Pa,
      flow: vaporFlow,
      composition: result.y,
      phase: 'V',
      H: H_V,
    },
    liquid: {
      T: T_K,
      P: P_Pa,
      flow: liquidFlow,
      composition: result.x,
      phase: 'L',
      H: H_L,
    },
  };
}
```

## Ports

| Port | Direction | Phase | Description |
|------|-----------|-------|-------------|
| in | Input | Any | Feed stream |
| vapor-out | Output | V | Vapor product |
| liquid-out | Output | L | Liquid product |

## Example

```typescript
const flashBlock = {
  id: 'flash-1',
  type: 'Flash',
  params: {
    T: { kind: 'quantity', q: { value: 50, unit: 'C' } },
    P: { kind: 'quantity', q: { value: 1, unit: 'bar' } }
  }
};
```
