---
sidebar_position: 1
---

# API Schema

TypeScript type definitions for Jasper.

## StreamData

```typescript
interface StreamData {
  id: string;
  T: number;           // K
  P: number;           // Pa
  flow: number;        // mol/s
  composition: Record<string, number>;
  phase?: 'L' | 'V' | 'VL';
  H?: number;          // J/mol
}
```

## BlockData

```typescript
interface BlockData {
  id: string;
  type: BlockType;
  params: Record<string, ParamValue>;
  inlet?: string;
  outlet?: string;
}

type BlockType =
  | 'Feed' | 'Sink'
  | 'Mixer' | 'Splitter'
  | 'Heater' | 'Cooler'
  | 'Pump' | 'Compressor'
  | 'Flash' | 'HeatExchanger'
  | 'Reactor' | 'DistillationColumn';
```

## SimulationResult

```typescript
interface SimulationResult {
  success: boolean;
  streams: Record<string, StreamData>;
  blocks: Record<string, BlockResult>;
  errors?: string[];
}
```

## Units

| Property | Units |
|----------|-------|
| Temperature | C, K, F |
| Pressure | Pa, bar, psi, atm |
| Flow | mol/s, kmol/h, kg/h |
