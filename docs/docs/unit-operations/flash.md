---
sidebar_position: 4
---

# Flash Drum

Separates feed into vapor and liquid phases.

## Parameters

| Parameter | Type | Unit | Description |
|-----------|------|------|-------------|
| T | Quantity | °C, K | Flash temperature |
| P | Quantity | bar, Pa | Flash pressure |

## Calculation

1. Calculate K-values: `Ki = Psat_i(T) / P`
2. Solve Rachford-Rice for vapor fraction V
3. Calculate phase compositions

```typescript
export function solveFlash(inlet: StreamData, params: { T: number, P: number }) {
  const result = flash(inlet.composition, params.T, params.P);
  
  return {
    vapor: {
      T: params.T,
      P: params.P,
      flow: inlet.flow * result.V,
      composition: result.y
    },
    liquid: {
      T: params.T,
      P: params.P,
      flow: inlet.flow * (1 - result.V),
      composition: result.x
    }
  };
}
```

## Ports

| Port | Direction | Phase |
|------|-----------|-------|
| in | Input | Any |
| vapor-out | Output | V |
| liquid-out | Output | L |
