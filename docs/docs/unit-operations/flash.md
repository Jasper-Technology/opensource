---
sidebar_position: 4
---

# Flash Drum

Separates feed into vapor and liquid phases using rigorous VLE calculations from the active property package.

## Parameters

| Parameter | Type | Unit | Description |
|-----------|------|------|-------------|
| T | Quantity | °C, K | Flash temperature (defaults to inlet T) |
| P | Quantity | bar, Pa | Flash pressure (defaults to inlet P) |

## Calculation

1. Get K-values from property package: `pkg.flash(z, T, P, components)`
   - **Ideal**: `Ki = Psat_i(T) / P` (Lee-Kesler vapor pressure)
   - **PR**: Iterative phi-phi flash with fugacity coefficients
   - **NRTL**: Iterative gamma-phi flash with activity coefficients
2. Flash result provides vapor fraction V and phase compositions (x, y)
3. Split feed flow: `F_vap = F × V`, `F_liq = F × (1 - V)`

## Ports

| Port | Direction | Phase |
|------|-----------|-------|
| in | Input | Any |
| vapor-out | Output | V |
| liquid-out | Output | L |

## Block Results

| Result | Unit | Description |
|--------|------|-------------|
| vaporFraction | - | Vapor fraction (0 to 1) |
| duty | kJ/h | Heat duty (0 for adiabatic flash) |

## Example

```typescript
const flash = {
  id: 'flash-1',
  type: 'Flash',
  params: {
    T: { kind: 'quantity', q: { value: 80, unit: 'C' } },
    P: { kind: 'quantity', q: { value: 1, unit: 'bar' } },
  }
};
```

With NRTL and an ethanol-water feed at 81°C / 1 atm, the flash correctly predicts:
- Vapor enriched in ethanol (y_EtOH > z_EtOH)
- Activity coefficient effects from NRTL BIPs
