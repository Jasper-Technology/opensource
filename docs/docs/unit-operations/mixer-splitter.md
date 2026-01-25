---
sidebar_position: 2
---

# Mixer / Splitter

Mixer combines multiple streams into one. Splitter divides one stream into multiple outlets.

## Mixer

### Calculation Method

Mass and energy balances:

```
n_out = sum(n_in_j)
z_i_out = sum(n_in_j * z_i_j) / n_out
H_out = sum(n_in_j * H_in_j) / n_out
```

Outlet temperature is calculated from the mixed enthalpy.

### Implementation

```typescript
export function solveMixer(inlets: StreamData[]): StreamData {
  // Total flow
  const totalFlow = inlets.reduce((sum, s) => sum + s.flow, 0);

  // Mixed composition
  const composition: Record<string, number> = {};
  for (const stream of inlets) {
    for (const [compId, frac] of Object.entries(stream.composition)) {
      composition[compId] = (composition[compId] || 0) +
        (stream.flow / totalFlow) * frac;
    }
  }

  // Mixed enthalpy
  const totalEnthalpy = inlets.reduce((sum, s) => sum + s.flow * s.H, 0);
  const H_mixed = totalEnthalpy / totalFlow;

  // Calculate outlet temperature from enthalpy
  const T_out = getTemperatureFromEnthalpy(composition, H_mixed);

  return {
    T: T_out,
    P: Math.min(...inlets.map(s => s.P)),  // Lowest inlet pressure
    flow: totalFlow,
    composition,
    H: H_mixed,
  };
}
```

### Ports

| Port | Direction | Description |
|------|-----------|-------------|
| in-1 | Input | First inlet stream |
| in-2 | Input | Second inlet stream |
| out | Output | Mixed outlet stream |

---

## Splitter

### Parameters

| Parameter | Type | Description |
|-----------|------|-------------|
| splitRatio | Number | Fraction of flow to first outlet (0-1) |

### Calculation Method

The splitter divides flow while maintaining composition and conditions:

```
n_out_1 = alpha * n_in
n_out_2 = (1 - alpha) * n_in
```

Temperature, pressure, and composition are unchanged.

### Implementation

```typescript
export function solveSplitter(
  inlet: StreamData,
  splitRatio: number
): { out1: StreamData; out2: StreamData } {
  return {
    out1: {
      ...inlet,
      flow: inlet.flow * splitRatio,
    },
    out2: {
      ...inlet,
      flow: inlet.flow * (1 - splitRatio),
    },
  };
}
```

### Ports

| Port | Direction | Description |
|------|-----------|-------------|
| in | Input | Inlet stream |
| out-1 | Output | First outlet (splitRatio fraction) |
| out-2 | Output | Second outlet (1 - splitRatio fraction) |
