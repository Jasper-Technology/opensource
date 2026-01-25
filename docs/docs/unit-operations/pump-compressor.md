---
sidebar_position: 4
---

# Pump / Compressor

Pumps increase liquid pressure. Compressors increase gas pressure.

## Pump

### Parameters

| Parameter | Type | Unit | Description |
|-----------|------|------|-------------|
| dP | Quantity | bar, Pa, psi | Pressure rise |

### Calculation Method

For incompressible liquids, work is calculated as:

```
W = (V_dot * dP) / eta
```

Where:
- `V_dot` is volumetric flow rate
- `dP` is pressure rise
- `eta` is pump efficiency (default 0.75)

Temperature rise is typically negligible for liquids.

### Implementation

```typescript
export function solvePump(
  inlet: StreamData,
  params: PumpParams
): { outlet: StreamData; power: number } {
  const dP = params.dP;  // Pa
  const eta = 0.75;

  // Outlet pressure
  const P_out = inlet.P + dP;

  // Estimate volumetric flow (assume liquid density ~1000 kg/m3)
  const avgMW = getMixtureMW(inlet.composition);
  const rho = 1000;  // kg/m3
  const massFlow = inlet.flow * avgMW / 1000;  // kg/s
  const volFlow = massFlow / rho;  // m3/s

  // Power calculation
  const power = (volFlow * dP) / eta;  // W

  return {
    outlet: {
      T: inlet.T,  // Temperature unchanged
      P: P_out,
      flow: inlet.flow,
      composition: inlet.composition,
      phase: 'L',
    },
    power: power,
  };
}
```

---

## Compressor

### Parameters

| Parameter | Type | Unit | Description |
|-----------|------|------|-------------|
| outletP | Quantity | bar, Pa, psi | Outlet pressure |
| ratio | Number | - | Compression ratio (optional) |

### Calculation Method

For ideal gas compression (isentropic):

```
W_s = (gamma / (gamma-1)) * n * R * T_in * [(P_out/P_in)^((gamma-1)/gamma) - 1]
```

Actual work with efficiency:

```
W_actual = W_s / eta_s
```

Outlet temperature:

```
T_out = T_in * (P_out/P_in)^((gamma-1)/gamma)
```

### Implementation

```typescript
export function solveCompressor(
  inlet: StreamData,
  params: CompressorParams
): { outlet: StreamData; power: number } {
  const P_out = params.outletP;  // Pa
  const eta = 0.72;  // Isentropic efficiency
  const gamma = 1.4;  // Cp/Cv ratio

  const ratio = P_out / inlet.P;

  // Isentropic outlet temperature
  const T_out_s = inlet.T * Math.pow(ratio, (gamma - 1) / gamma);

  // Actual outlet temperature
  const T_out = inlet.T + (T_out_s - inlet.T) / eta;

  // Work calculation
  const R = 8.314;  // J/(mol*K)
  const W_s = (gamma / (gamma - 1)) * inlet.flow * R * inlet.T *
    (Math.pow(ratio, (gamma - 1) / gamma) - 1);
  const power = W_s / eta;

  return {
    outlet: {
      T: T_out,
      P: P_out,
      flow: inlet.flow,
      composition: inlet.composition,
      phase: 'V',
    },
    power: power,
  };
}
```

### Ports

| Port | Direction | Description |
|------|-----------|-------------|
| in | Input | Inlet stream |
| out | Output | Pressurized outlet stream |
