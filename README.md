# Jasper Simulation Engine

Open-source chemical process simulation engine powering [Jasper](https://jaspertech.org).

## Overview

Jasper is a modern, browser-based process simulation tool for chemical engineers. This repository contains the core simulation engine — thermodynamic calculations, unit operation models, and the sequential modular solver. The Quick mode engine runs entirely in-browser with textbook-correct thermodynamics, no backend required.

## Features

### Thermodynamics

Five property methods, selectable per-project:

| Method | Best For | K-Value Model |
|--------|----------|---------------|
| **Ideal** | Ideal mixtures, low pressure | Raoult's Law |
| **Peng-Robinson** | Hydrocarbons, gases, high pressure | Fugacity (phi-phi) |
| **SRK** | Hydrocarbon screening and gas processing | Fugacity (phi-phi) |
| **RK** | Legacy cubic-EOS screening | Fugacity (phi-phi) |
| **NRTL** | Polar/non-ideal liquids (ethanol-water, amines) | Activity coefficients (gamma-phi) |

Property calculations include:
- **Lee-Kesler** vapor pressure (1-3% error, boiling-point anchored)
- **Rackett** liquid density
- **Entropy** with departure functions for isentropic equipment
- **Heat of reaction** from heats of formation + Cp integration
- **70+ component database** with DIPPR/NIST validated data
- **~20 NRTL BIP pairs** for common systems

### Unit Operations

| Unit Operation | Method |
|---------------|--------|
| Flash / Separator | Rigorous VLE with property-package K-values |
| Distillation Column | Fenske-Underwood-Gilliland shortcut |
| Reactors (RStoic, REquil, RGibbs, etc.) | Stoichiometric + heat of reaction, equilibrium |
| Compressor | Isentropic with entropy-based Newton iteration |
| Pump | Rackett liquid density for real power |
| Absorber / Stripper | Kremser equation (general, multi-solute) |
| Heater / Cooler | Rigorous enthalpy-based duty |
| Mixer / Splitter | Enthalpy balance with Newton T iteration |
| Valve | Isenthalpic throttling |
| Heat Exchanger | Counter-current with effectiveness |

### Solver

- **Sequential modular** block-by-block execution
- **Topological sort** with automatic tear stream detection
- **Wegstein acceleration** for recycle convergence (tolerance 1e-4)

## Project Structure

```
src/
├── core/
│   └── schema.ts                    # Zod schemas for flowsheet data
├── sim/
│   ├── solver/
│   │   └── blockSolver.ts           # Sequential modular solver
│   ├── thermo/
│   │   ├── properties.ts            # Cp, enthalpy, entropy, Pvap, density
│   │   ├── pengRobinson.ts          # Peng-Robinson EOS
│   │   ├── nrtl.ts                  # NRTL activity coefficients
│   │   ├── bipDatabase.ts           # Binary interaction parameters
│   │   ├── propertyMethod.ts        # PropertyPackage interface + factory
│   │   ├── componentDatabase.ts     # 70+ component data
│   │   └── __tests__/
│   │       └── quickmode-parity.test.ts  # 16 verification tests
│   ├── blocks/                      # Legacy unit operation models
│   ├── engine-v2.ts                 # Simulation engine orchestration
│   ├── sizing.ts                    # Equipment sizing correlations
│   └── economics.ts                 # Capital cost estimation
docs/                                # Docusaurus documentation site
```

## Usage

```typescript
import { solveFlowsheet } from './sim/solver/blockSolver';

const result = solveFlowsheet(project);

if (result.converged) {
  for (const [streamId, state] of result.streams.entries()) {
    console.log(`${state.name}: ${state.T.toFixed(1)} K, ${state.P.toFixed(2)} bar`);
    console.log(`  Flow: ${state.flow.toFixed(2)} kmol/h`);
    console.log(`  Phase: ${state.phase}`);
  }

  for (const [blockId, data] of result.blockResults.entries()) {
    console.log(`Block ${blockId}:`, data);
  }
}
```

## Running Tests

```bash
npx tsx src/sim/thermo/__tests__/quickmode-parity.test.ts
```

18 tests covering all phases:
- Lee-Kesler Pvap (water, ethanol, benzene, methane within 2%)
- PR flash (propane-butane two-phase)
- SRK/RK K-value ordering sanity checks
- NRTL activity coefficients (ethanol-water gamma > 5)
- Isentropic compressor (N2, 0.1% error vs textbook)
- Benzene-toluene distillation (99% purity)
- Water-gas shift reactor heat of reaction
- Recycle convergence (3 iterations with Wegstein)
- Kremser CO2 absorption

## Contributing

Contributions are welcome! Please see our [contribution guidelines](CONTRIBUTING.md).

### Areas We Need Help

**High Priority:**
- Wilson/UNIQUAC activity coefficient models
- Rigorous stage-by-stage distillation (MESH equations)
- Henry's Law for dissolved gases

**Medium Priority:**
- Expand BIP database beyond ~20 pairs
- Component database expansion beyond 70 compounds
- UNIFAC group contribution method
- Steam tables (IAPWS-IF97)

**Completed:**
- ~~Peng-Robinson EOS~~
- ~~NRTL activity coefficients~~
- ~~Lee-Kesler Pvap + Rackett density~~
- ~~Isentropic compressor~~
- ~~Shortcut distillation (FUG)~~
- ~~Reactor heat of reaction + equilibrium~~
- ~~Recycle convergence (Wegstein)~~
- ~~Kremser absorber/stripper~~

## License

MIT License - see [LICENSE](LICENSE) for details.

## Links

- **Website**: [jaspertech.org](https://jaspertech.org)
- **Documentation**: [docs.jaspertech.org](https://docs.jaspertech.org)
- **Issues**: [GitHub Issues](https://github.com/Jasper-Technology/opensource/issues)
