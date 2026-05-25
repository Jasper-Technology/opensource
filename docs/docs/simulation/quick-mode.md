---
sidebar_position: 2
---

# Quick Mode

In-browser, sequential-modular simulation engine written in TypeScript. Runs entirely client-side — no backend, no auth, no network round-trip.

Source: [`opensource/src/`](https://github.com/Jasper-Technology/opensource/tree/main/src)

## What it is

Quick mode is the default Jasper engine. It executes blocks one at a time in topological order, with Wegstein acceleration for recycle convergence. Designed for instant feedback during flowsheet construction, teaching, and screening studies.

| Aspect | Detail |
|--------|--------|
| Architecture | Sequential modular, client-side |
| Latency | &lt;100 ms (typical) |
| Offline | Yes |
| Property methods | Ideal, Peng-Robinson, NRTL |
| Recycle handling | Wegstein acceleration, tol 1e-4 |
| DOF check | No |
| Components | 70+ (DIPPR / NIST validated) |
| License | MIT |

## Thermodynamics

Three property packages are selectable per project:

| Method | K-value model | Best for |
|--------|---------------|----------|
| **Ideal** | Raoult's Law | Ideal mixtures, low pressure |
| **Peng-Robinson (PR)** | Fugacity (phi-phi) | Hydrocarbons, gases, high pressure |
| **NRTL** | Activity coefficients (gamma-phi) | Polar / non-ideal liquids (ethanol-water, amines) |

Underlying property calculations:

- **Lee-Kesler** vapor pressure — 1 – 3% error, boiling-point anchored
- **Rackett** liquid density
- **Entropy** with departure functions (used by isentropic equipment)
- **Heat of reaction** from heats of formation + Cp integration
- **70+ component database** with DIPPR / NIST validated data
- **~20 NRTL BIP pairs** for common systems

## Unit operations

| Unit op | Method |
|---------|--------|
| Flash / Separator | Rigorous VLE with property-package K-values |
| Distillation column | Fenske-Underwood-Gilliland shortcut |
| Reactors (RStoic, REquil, RGibbs, …) | Stoichiometric + heat of reaction, equilibrium |
| Compressor | Isentropic with entropy-based Newton iteration |
| Pump | Rackett liquid density for real power |
| Absorber / Stripper | Kremser equation (general, multi-solute) |
| Heater / Cooler | Rigorous enthalpy-based duty |
| Mixer / Splitter | Enthalpy balance with Newton T iteration |
| Valve | Isenthalpic throttling |
| Heat exchanger | Counter-current with effectiveness |

## Solver

```
Topological sort → detect tear streams → block-by-block solve
                              │
                              ▼
                      Wegstein acceleration
                          (tol 1e-4)
                              │
                              ▼
                          Converged
```

- **Sequential modular** block-by-block execution
- **Topological sort** with automatic tear stream detection
- **Wegstein acceleration** for recycle convergence (tolerance 1e-4)

## Use this when

- Building or teaching a flowsheet — you want instant feedback as you wire blocks
- Your system is nearly ideal (light hydrocarbons, dilute aqueous mixtures)
- You need to work offline
- You're screening many design variants before committing to a rigorous solve

## Switch to Rigorous (DWSIM) when

- The system is strongly non-ideal (azeotropes, electrolytes, polar solvents at high pressure)
- You need CSTR / PFR / Gibbs reactors (Quick supports shortcut reactors only)
- You need DWSIM's broader property-package coverage (UNIQUAC, UNIFAC, IAPWS steam, electrolytes)

For equation-oriented optimization, ask the Jasper agent in chat — it routes the request to IDAES + IPOPT under the hood. See [Optimize mode](./optimize-mode.md).

## Verification

The Quick engine ships with a 16-test parity suite:

```bash
npx tsx src/sim/thermo/__tests__/quickmode-parity.test.ts
```

Covers Lee-Kesler Pvap (water, ethanol, benzene, methane within 2%), PR flash (propane-butane two-phase), NRTL activity (ethanol-water gamma &gt; 5), isentropic compressor (N₂, 0.1% error vs textbook), benzene-toluene FUG distillation (99% purity), water-gas-shift reactor heat of reaction, recycle convergence with Wegstein (3 iterations), and Kremser CO₂ absorption.

## Limitations

- No degrees-of-freedom check — under- or over-specified flowsheets fail silently or with confusing errors
- No simultaneous equation solve — tightly coupled recycles can be slow or fail to converge
- No optimization
- ~20 NRTL BIPs only — other binaries fall back to estimated values
- No solid phases
