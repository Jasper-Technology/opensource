---
sidebar_position: 5
---

# Pump / Compressor

Increase pressure of liquids (pump) or gases (compressor).

## Pump

For incompressible liquids, power is calculated from volumetric flow and pressure rise:

```
W = (V̇ × ΔP) / η
```

Liquid density comes from the **Rackett equation** via the property package (replacing the old 1000 kg/m3 placeholder).

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| dP | Quantity | 5 bar | Pressure rise |
| efficiency | Number | 0.75 | Pump efficiency |

## Compressor

Uses **isentropic compression with efficiency correction**:

1. Compute inlet entropy: `S_in = pkg.mixtureEntropy(comp, T_in, P_in)`
2. Find isentropic outlet T via Newton iteration: solve `S(T_s, P_out) = S_in`
3. Compute isentropic work: `ΔH_s = H(T_s, P_out) - H(T_in, P_in)`
4. Actual work: `ΔH_actual = ΔH_s / η`
5. Find actual outlet T from `H(T_out, P_out) = H_in + ΔH_actual`

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| outletP | Quantity | 2× inlet | Outlet pressure |
| ratio | Number | 2 | Pressure ratio (if outletP not set) |
| efficiency | Number | 0.75 | Isentropic efficiency |

### Block Results

| Result | Unit | Description |
|--------|------|-------------|
| power | kJ/h | Actual shaft power |
| outletP | bar | Outlet pressure |
| T_out | K | Actual outlet temperature |
| isentropicT | K | Isentropic outlet temperature |
| efficiency | - | Isentropic efficiency used |

### Accuracy

For nitrogen compression (1→3 bar):
- Isentropic T_out: 410.2 K (textbook: 410.6 K, 0.1% error)
- Isentropic work: 3.22 kJ/mol (textbook: 3.22 kJ/mol)

## Ports

| Port | Direction | Phase |
|------|-----------|-------|
| in | Input | L (pump) or V (compressor) |
| out | Output | L (pump) or V (compressor) |
