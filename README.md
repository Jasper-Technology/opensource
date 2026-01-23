# Jasper Simulation Engine

Open-source chemical process simulation engine powering [Jasper](https://jaspertech.org).

## Overview

Jasper is a modern, browser-based process simulation tool for chemical engineers. This repository contains the core simulation engine, thermodynamic calculations, and unit operation models.

## Features

- **Thermodynamic Properties**: Heat capacity correlations, vapor pressure (Antoine equation), enthalpy calculations for 50+ chemicals
- **VLE Calculations**: Flash calculations with Raoult's Law for ideal mixtures
- **Unit Operations**: Feed, Mixer, Splitter, Flash, Heater, Cooler, Pump, Compressor, Valve, Heat Exchanger, Reactor, Separator, Distillation Column
- **Sequential Modular Solver**: Automatic calculation order with recycle stream handling
- **Equipment Sizing**: Preliminary sizing correlations for pumps, compressors, vessels, heat exchangers
- **Capital Cost Estimation**: Order-of-magnitude cost estimates using standard correlations

## Project Structure

```
src/
├── core/
│   └── schema.ts          # Zod schemas for flowsheet data structures
├── sim/
│   ├── engine-v2.ts       # Main simulation engine (sequential modular)
│   ├── converter.ts       # V1 to V2 schema conversion
│   ├── validator.ts       # Flowsheet validation
│   ├── sizing.ts          # Equipment sizing correlations
│   ├── economics.ts       # Capital cost estimation
│   ├── blocks/            # Unit operation models
│   │   ├── feed.ts
│   │   ├── mixer.ts
│   │   ├── splitter.ts
│   │   ├── flash.ts
│   │   ├── heater.ts
│   │   ├── pump.ts
│   │   └── ...
│   ├── thermo/            # Thermodynamic calculations
│   │   ├── properties.ts  # Heat capacity, enthalpy
│   │   ├── vle.ts         # Vapor-liquid equilibrium
│   │   └── componentDatabase.ts  # Chemical database
│   └── solver/
│       └── sequential.ts  # Calculation sequencing
```

## Usage

```typescript
import { runSimulation } from './sim/engine-v2';
import { convertProject } from './sim/converter';

// Convert flowsheet to simulation format
const simInput = convertProject(project);

// Run simulation
const results = runSimulation(simInput);

console.log(results.streams);  // Stream properties
console.log(results.blocks);   // Unit operation results
```

## Thermodynamic Models

Currently implemented:
- **Heat Capacity**: Polynomial correlations (Cp = a + bT + cT² + dT³)
- **Vapor Pressure**: Antoine equation
- **VLE**: Raoult's Law (ideal mixtures)
- **Enthalpy**: Integration of Cp with reference state

Planned improvements:
- Peng-Robinson equation of state
- NRTL/UNIQUAC activity coefficients
- Steam tables

## Contributing

Contributions are welcome! Please see our [contribution guidelines](CONTRIBUTING.md).

Areas where we need help:
- Additional thermodynamic models (PR EOS, activity coefficients)
- More unit operation models
- Rigorous distillation calculations
- Property database expansion
- Documentation and examples

## License

MIT License - see [LICENSE](LICENSE) for details.

## Links

- **Website**: [jaspertech.org](https://jaspertech.org)
- **Documentation**: Coming soon
- **Issues**: [GitHub Issues](https://github.com/Jasper-Technology/opensource/issues)
