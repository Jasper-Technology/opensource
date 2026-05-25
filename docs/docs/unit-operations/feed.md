---
sidebar_position: 1
---

# Feed

A Feed block defines an inlet stream to the process.

## Parameters

| Parameter | Type | Unit | Description |
|-----------|------|------|-------------|
| T | Quantity | °C, K, °F | Temperature |
| P | Quantity | bar, Pa, psi | Pressure |
| flow | Quantity | kmol/h, kg/h | Flow rate |
| composition | Object | - | Mole fractions |

## Example

```typescript
const feedBlock = {
  id: 'feed-1',
  type: 'Feed',
  params: {
    T: { value: 25, unit: 'C' },
    P: { value: 1, unit: 'bar' },
    flow: { value: 100, unit: 'kmol/h' },
    composition: { H2O: 0.5, C2H5OH: 0.5 }
  }
};
```

## Ports

| Port | Direction | Description |
|------|-----------|-------------|
| out | Output | Outlet stream |
