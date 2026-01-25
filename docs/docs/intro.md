---
slug: /
sidebar_position: 1
---

# Introduction

Jasper is an open-source chemical process simulation engine designed for modern web applications.

## What is Jasper?

Jasper provides a complete toolkit for chemical process simulation:

- **Thermodynamic calculations** - Heat capacity, enthalpy, vapor-liquid equilibrium
- **Unit operation models** - Feed, mixer, splitter, flash, heater, cooler, pump, compressor, reactor, and more
- **Component database** - 50+ chemicals with validated property data
- **Equipment sizing** - Preliminary sizing correlations for common equipment
- **Cost estimation** - Order-of-magnitude capital cost estimates

## Quick Start

### Installation

```bash
npm install @jasper-technology/simulation
```

### Basic Usage

```typescript
import { runSimulation } from '@jasper-technology/simulation';

const result = runSimulation({
  components: ['H2O', 'C2H5OH'],
  streams: [
    {
      id: 'feed',
      T: 25,  // °C
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
      params: { outletT: 80 }  // °C
    }
  ]
});

console.log(result.streams.heated);
// { T: 353.15, P: 1, flow: 100, composition: {...}, H: ... }
```

## Architecture

The simulation engine uses a **sequential modular** approach:

1. **Topology analysis** - Determine calculation order from flowsheet connectivity
2. **Block solving** - Execute each unit operation in sequence
3. **Stream propagation** - Pass outlet conditions to downstream units
4. **Convergence** - Iterate on recycle streams until convergence

## Try It Online

Visit [jaspertech.org](https://jaspertech.org) to use the full visual process simulator with drag-and-drop flowsheet editing.

## Contributing

Jasper is open source under the MIT license. Contributions are welcome:

- [GitHub Repository](https://github.com/Jasper-Technology/opensource)
- [Contributing Guide](/contributing/development-setup)
