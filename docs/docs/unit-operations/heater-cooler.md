---
sidebar_position: 3
---

# Heater / Cooler

Changes stream temperature to a specified value.

## Parameters

| Parameter | Type | Unit | Description |
|-----------|------|------|-------------|
| outletT | Quantity | °C, K, °F | Target temperature |

## Calculation

```
Q = ṅ × (H_out - H_in)
```

```typescript
export function solveHeater(inlet: StreamData, params: { outletT: number }) {
  const H_in = getMixtureEnthalpy(inlet.composition, inlet.T);
  const H_out = getMixtureEnthalpy(inlet.composition, params.outletT);
  const duty = inlet.flow * (H_out - H_in);
  
  return {
    outlet: { ...inlet, T: params.outletT, H: H_out },
    duty
  };
}
```

## Example

```typescript
const heaterBlock = {
  id: 'heater-1',
  type: 'Heater',
  params: { outletT: { value: 100, unit: 'C' } }
};
```
