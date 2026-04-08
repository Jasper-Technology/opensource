# Jasper Simulation Engine

## Overview

Jasper uses **rigorous thermodynamic calculations** and **sequential modular solving** — similar to AspenPlus, DWSIM, and other professional simulators. The Quick mode engine runs entirely in-browser with three property methods (Ideal, PR, NRTL).

## Architecture

```
┌─────────────────────────────────────────┐
│         Property Package Selection      │
│  Ideal / Peng-Robinson / NRTL           │
└──────────────┬──────────────────────────┘
               │
               ▼
┌─────────────────────────────────────────┐
│      Sequential Modular Solver          │
│  1. Topological sort with tear detect  │
│  2. Solve blocks in order              │
│  3. Property package threaded through  │
│  4. Wegstein recycle convergence       │
└──────────────┬──────────────────────────┘
               │
               ▼
┌─────────────────────────────────────────┐
│      Thermodynamic Properties           │
│  - Heat capacity (Cp, DIPPR 5-coeff)  │
│  - Enthalpy (H) + departure functions  │
│  - Entropy (S) + departure functions   │
│  - Vapor pressure (Lee-Kesler)         │
│  - Liquid density (Rackett)            │
│  - VLE (Raoult / PR fugacity / NRTL)  │
│  - Heat of reaction                    │
└─────────────────────────────────────────┘
```

## Implemented Features

### Thermodynamics (`thermo/`)

| File | Purpose |
|------|---------|
| `properties.ts` | Cp, enthalpy, entropy, Lee-Kesler Pvap, Rackett density, heat of reaction |
| `pengRobinson.ts` | PR EOS: cubic solver, fugacity coefficients, departure functions, phi-phi flash |
| `nrtl.ts` | NRTL activity coefficient model |
| `bipDatabase.ts` | ~20 BIP pairs (water-alcohol, amine-water, hydrocarbons, organics) |
| `propertyMethod.ts` | PropertyPackage interface + Ideal/PR/NRTL factory |
| `componentDatabase.ts` | 70+ components with DIPPR/NIST validated data |

### Block Solvers (`solver/blockSolver.ts`)

| Unit Operation | Method |
|---------------|--------|
| Feed | Initialize from params or edge spec |
| Flash / Separator | Rigorous VLE flash via property package |
| Mixer | Mass + energy balance (Newton iteration for T) |
| Splitter | Flow division by split ratio |
| Pump | Power from Rackett liquid density |
| Compressor | Isentropic with entropy-based Newton iteration |
| Valve | Isenthalpic throttling |
| Heater / Cooler | Rigorous enthalpy-based duty |
| DistillationColumn | Fenske-Underwood-Gilliland shortcut |
| RStoic / RCSTR / RPfr / RBatch / RYield | Stoichiometric + heat of reaction |
| REquil / RGibbs | Equilibrium from Keq (bisection) |
| Absorber | Kremser equation (general, multi-solute) |
| Stripper | Kremser stripping |
| HeatExchanger | Counter-current (80% effectiveness) |

### Solver Algorithm

1. Select PropertyPackage from `project.thermodynamics.propertyMethod`
2. Initialize feed streams
3. Topological sort with DFS back-edge detection → tear streams
4. Solve blocks sequentially, threading property package
5. For recycles: Wegstein-accelerated iteration (tol 1e-4, max 50 iter)

## Tests

```bash
npx tsx src/sim/thermo/__tests__/quickmode-parity.test.ts
```

16 tests verify all phases against literature/textbook values.

## Contributing

To add new unit operations, add a `solveYourUnit()` function in `solver/blockSolver.ts` following the existing pattern:

```typescript
function solveYourUnit(
  block: UnitOpNode,
  flowsheet: FlowsheetGraph,
  streams: Map<string, StreamState>,
  results: Map<string, any>,
  pkg: PropertyPackage,    // ← property package for all thermo calls
) {
  // Get inlet streams
  // Use pkg.flash(), pkg.mixtureEnthalpy(), pkg.calculateKValues(), etc.
  // Set outlet streams
  // Store results
}
```

Then add to the `switch` statement in `solveBlock()`.

## References

1. **Smith, Van Ness, Abbott** — Introduction to Chemical Engineering Thermodynamics
2. **Seader, Henley, Roper** — Separation Process Principles
3. **Fogler** — Elements of Chemical Reaction Engineering
4. **Prausnitz et al.** — The Properties of Gases and Liquids
5. **Perry's Chemical Engineers' Handbook** (9th ed.)
