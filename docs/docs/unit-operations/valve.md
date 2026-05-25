---
sidebar_position: 6
---

# Valve

A throttling device that reduces stream pressure with no moving parts.

## Parameters

| Parameter | Type | Unit | Description |
|-----------|------|------|-------------|
| outletP | Quantity | bar, Pa, psi | Outlet pressure (specify one) |
| dP | Quantity | bar, Pa, psi | Pressure drop (specify one) |

Specify either `outletP` or `dP` — the other is calculated automatically.

## Modes

| Mode | Description |
|------|-------------|
| Quick | Isenthalpic flash — assumes H_out = H_in and solves for outlet T at the new pressure |
| Rigorous | DWSIM `Valve` unit operation with full property-package evaluation |

## Ports

| Port | Direction | Description |
|------|-----------|-------------|
| in | Input | Inlet stream |
| out | Output | Outlet stream (lower pressure) |
