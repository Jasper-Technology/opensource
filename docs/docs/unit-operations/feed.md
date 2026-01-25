---
sidebar_position: 1
---

# Feed

A Feed block defines an inlet stream to the process with specified conditions.

## Parameters

| Parameter | Type | Unit | Description |
|-----------|------|------|-------------|
| T | Quantity | C, K, F | Stream temperature |
| P | Quantity | bar, Pa, psi | Stream pressure |
| flow | Quantity | kmol/h, kg/h, mol/s | Molar or mass flow rate |
| composition | Object | - | Mole fractions by component ID |

## Calculation

Feed blocks simply define stream conditions - no calculations are performed. The outlet stream properties are set directly from the parameters.

```typescript
// src/sim/blocks/feed.ts

export function solveFeed(params: FeedParams): StreamData {
  return {
    T: params.T,  // Already in K
    P: params.P,  // Already in Pa
    flow: params.flow,  // mol/s
    composition: params.composition,
    phase: determinePhase(params.T, params.P, params.composition),
  };
}
```

## Phase Determination

The feed phase is determined by comparing the bubble and dew points:

- If T < bubble point: subcooled liquid
- If T > dew point: superheated vapor
- Otherwise: two-phase mixture

## Example

```typescript
const feedBlock = {
  id: 'feed-1',
  type: 'Feed',
  params: {
    T: { kind: 'quantity', q: { value: 25, unit: 'C' } },
    P: { kind: 'quantity', q: { value: 1, unit: 'bar' } },
    flow: { kind: 'quantity', q: { value: 100, unit: 'kmol/h' } },
    composition: {
      kind: 'composition',
      comp: { H2O: 0.5, C2H5OH: 0.5 }
    }
  }
};
```

## Ports

| Port | Direction | Description |
|------|-----------|-------------|
| out | Output | Outlet stream with specified conditions |
