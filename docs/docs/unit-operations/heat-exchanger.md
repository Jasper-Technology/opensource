---
sidebar_position: 7
---

# Shell & Tube Heat Exchanger

A two-sided exchanger that transfers heat between a hot fluid and a cold fluid. Counter-current flow is assumed by default.

## Parameters

| Parameter | Type | Unit | Description |
|-----------|------|------|-------------|
| approachT | Quantity | °C, K | Minimum approach temperature |
| UA | Quantity | W/K | Overall heat transfer coefficient × area |
| duty | Quantity | W, kW | Fixed heat duty |

Specify one of `approachT`, `UA`, or `duty` — the remaining values are back-calculated.

## Modes

| Mode | Description |
|------|-------------|
| Quick | Energy balance with constant Cp — LMTD shortcut |
| Rigorous | IDAES `HeatExchanger1D` or `HeatExchanger` model with full property evaluation on both sides |

## Ports

| Port | Direction | Side | Description |
|------|-----------|------|-------------|
| hot-in | Input | Hot | Hot fluid inlet |
| hot-out | Output | Hot | Hot fluid outlet |
| cold-in | Input | Cold | Cold fluid inlet |
| cold-out | Output | Cold | Cold fluid outlet |
