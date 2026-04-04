---
sidebar_position: 9
---

# Separation Columns

Multi-stage vapor-liquid contacting equipment. All use IDAES column models in rigorous mode.

## DistillationColumn

Multi-tray column with a condenser at the top and a reboiler at the bottom.

| Parameter | Type | Unit | Description |
|-----------|------|------|-------------|
| nStages | Number | - | Number of trays |
| feedStage | Number | - | Feed tray location (counted from top) |
| refluxRatio | Number | - | Reflux ratio (L/D) |
| boilupRatio | Number | - | Boilup ratio (V/B) |
| condenserP | Quantity | bar, Pa | Condenser pressure |

### Ports

| Port | Direction | Description |
|------|-----------|-------------|
| in | Input | Feed stream |
| distillate | Output | Overhead liquid product |
| bottoms | Output | Bottom liquid product |

## Absorber

Gas-liquid contactor for removing components from a gas stream into a liquid solvent.

| Parameter | Type | Unit | Description |
|-----------|------|------|-------------|
| nStages | Number | - | Number of stages |

### Ports

| Port | Direction | Description |
|------|-----------|-------------|
| gas-in | Input | Gas feed (bottom) |
| gas-out | Output | Cleaned gas (top) |
| liquid-in | Input | Solvent feed (top) |
| liquid-out | Output | Rich solvent (bottom) |

## Stripper

Vapor-liquid separator that uses a reboiler to strip dissolved components from the liquid phase.

| Parameter | Type | Unit | Description |
|-----------|------|------|-------------|
| nStages | Number | - | Number of stages |
| reboilerDuty | Quantity | W, kW | Reboiler heat duty |

### Ports

| Port | Direction | Description |
|------|-----------|-------------|
| in | Input | Rich liquid feed |
| vapor-out | Output | Stripped vapor |
| liquid-out | Output | Lean liquid |
