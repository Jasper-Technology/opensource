---
sidebar_position: 3
---

# Heater / Cooler

Heater and Cooler blocks change the temperature of a stream to a specified outlet temperature.

## Parameters

| Parameter | Type | Unit | Description |
|-----------|------|------|-------------|
| outletT | Quantity | C, K, F | Target outlet temperature |
| duty | Quantity | kW, kJ/h | Heat duty (optional, calculated if outletT set) |

## Calculation Method

The heat duty is calculated from the enthalpy change:

```
Q = n_dot * (H_out - H_in)
```

Where:
- `Q` is heat duty (positive for heating, negative for cooling)
- `n` is molar flow rate
- `H_out` and `H_in` are outlet and inlet molar enthalpies

### Enthalpy Calculation

```
H(T) = integral(Cp, T_ref, T) + Hf
```

For a polynomial Cp:

```
H(T) = a*(T - T_ref) + (b/2)*(T^2 - T_ref^2) + (c/3)*(T^3 - T_ref^3) + (d/4)*(T^4 - T_ref^4) + Hf
```

## Implementation

```typescript
// src/sim/blocks/heater.ts

export function solveHeater(
  inlet: StreamData,
  params: HeaterParams
): { outlet: StreamData; duty: number } {
  const T_out = params.outletT;

  // Calculate inlet enthalpy
  const H_in = getMixtureEnthalpy(inlet.composition, inlet.T, inlet.phase);

  // Calculate outlet enthalpy
  const H_out = getMixtureEnthalpy(inlet.composition, T_out, inlet.phase);

  // Calculate duty
  const duty = inlet.flow * (H_out - H_in);  // W

  return {
    outlet: {
      T: T_out,
      P: inlet.P,  // Pressure unchanged
      flow: inlet.flow,
      composition: inlet.composition,
      phase: inlet.phase,
      H: H_out,
    },
    duty: duty,
  };
}
```

## Ports

| Port | Direction | Description |
|------|-----------|-------------|
| in | Input | Inlet stream |
| out | Output | Heated/cooled outlet stream |

## Energy Results

The block reports:
- **Duty**: Heat transfer rate in kW
- **Steam consumption**: Estimated from duty (for heaters)
- **Cooling water**: Estimated from duty (for coolers)

## Example

```typescript
const heaterBlock = {
  id: 'heater-1',
  type: 'Heater',
  params: {
    outletT: { kind: 'quantity', q: { value: 100, unit: 'C' } }
  }
};
```
