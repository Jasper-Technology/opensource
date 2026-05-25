---
sidebar_position: 5
---

# Pump / Compressor

Increase pressure of liquids (pump) or gases (compressor).

## Pump

For incompressible liquids:

```
W = (V̇ × ΔP) / η
```

| Parameter | Type | Description |
|-----------|------|-------------|
| dP | Quantity | Pressure rise |

## Compressor

For isentropic compression:

```
T_out = T_in × (P_out/P_in)^((γ-1)/γ)
```

| Parameter | Type | Description |
|-----------|------|-------------|
| outletP | Quantity | Outlet pressure |

```typescript
export function solveCompressor(inlet: StreamData, params: { outletP: number }) {
  const gamma = 1.4;
  const eta = 0.72;
  const ratio = params.outletP / inlet.P;
  
  const T_out_s = inlet.T * Math.pow(ratio, (gamma - 1) / gamma);
  const T_out = inlet.T + (T_out_s - inlet.T) / eta;
  
  return { outlet: { ...inlet, T: T_out, P: params.outletP } };
}
```
