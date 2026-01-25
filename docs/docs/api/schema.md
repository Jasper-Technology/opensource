---
sidebar_position: 1
---

# Schema Reference

TypeScript type definitions for the Jasper simulation engine.

## Core Types

### StreamData

Represents a process stream with thermodynamic state.

```typescript
interface StreamData {
  id: string;
  T: number;           // Temperature (K)
  P: number;           // Pressure (Pa)
  flow: number;        // Molar flow (mol/s)
  composition: Record<string, number>;  // Mole fractions
  phase?: 'L' | 'V' | 'VL';
  H?: number;          // Molar enthalpy (J/mol)
}
```

### BlockData

Represents a unit operation block.

```typescript
interface BlockData {
  id: string;
  type: BlockType;
  params: Record<string, ParamValue>;
  inlet?: string;
  outlet?: string;
}
```

### ParamValue

Parameter values with unit support.

```typescript
type ParamValue =
  | { kind: 'quantity'; q: { value: number; unit: string } }
  | { kind: 'number'; n: number }
  | { kind: 'option'; o: string };
```

## Block Types

```typescript
type BlockType =
  | 'Feed'
  | 'Sink'
  | 'Mixer'
  | 'Splitter'
  | 'Heater'
  | 'Cooler'
  | 'Pump'
  | 'Compressor'
  | 'Flash'
  | 'HeatExchanger'
  | 'Reactor'
  | 'DistillationColumn'
  | 'Absorber'
  | 'Stripper';
```

## Simulation Result

```typescript
interface SimulationResult {
  success: boolean;
  streams: Record<string, StreamData>;
  blocks: Record<string, BlockResult>;
  errors?: string[];
}

interface BlockResult {
  id: string;
  type: BlockType;
  duty?: number;       // Heat duty (W)
  work?: number;       // Shaft work (W)
  converged: boolean;
}
```

## Quantity Units

### Temperature
- `C` - Celsius
- `K` - Kelvin
- `F` - Fahrenheit

### Pressure
- `Pa` - Pascal
- `bar` - Bar
- `psi` - Pounds per square inch
- `atm` - Atmosphere

### Flow
- `mol/s` - Moles per second
- `kmol/h` - Kilomoles per hour
- `kg/h` - Kilograms per hour

### Energy
- `W` - Watts
- `kW` - Kilowatts
- `kJ/h` - Kilojoules per hour
