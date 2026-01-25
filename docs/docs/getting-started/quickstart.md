---
sidebar_position: 1
---

# Quick Start

Get up and running with Jasper simulation engine.

## Installation

```bash
npm install @jasper-technology/simulation
```

## Basic Usage

### Create a Simple Flowsheet

```typescript
import { runSimulation } from '@jasper-technology/simulation';

const result = runSimulation({
  components: ['H2O', 'C2H5OH'],
  streams: [
    {
      id: 'feed',
      T: 25,  // C
      P: 1,   // bar
      flow: 100,  // kmol/h
      composition: { H2O: 0.5, C2H5OH: 0.5 }
    }
  ],
  blocks: [
    {
      id: 'heater',
      type: 'Heater',
      inlet: 'feed',
      outlet: 'heated',
      params: { outletT: 80 }  // C
    }
  ]
});

console.log(result.streams.heated);
```

### Flash Separation

```typescript
const flashResult = runSimulation({
  components: ['nC6', 'nC7', 'nC8'],
  streams: [
    {
      id: 'feed',
      T: 100,
      P: 2,
      flow: 100,
      composition: { nC6: 0.3, nC7: 0.4, nC8: 0.3 }
    }
  ],
  blocks: [
    {
      id: 'flash',
      type: 'Flash',
      inlet: 'feed',
      vaporOutlet: 'vapor',
      liquidOutlet: 'liquid',
      params: { T: 80, P: 1 }
    }
  ]
});
```

## Visual Editor

For a full drag-and-drop experience, visit [jaspertech.org](https://jaspertech.org) to use the visual process simulator.

## Next Steps

- [Thermodynamics Overview](/thermodynamics/overview) - Learn about the calculation methods
- [Unit Operations](/unit-operations/feed) - Explore available equipment models
- [Component Database](/components/available-components) - View available chemicals
