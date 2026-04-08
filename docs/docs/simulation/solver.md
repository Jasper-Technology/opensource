---
sidebar_position: 4
---

# Block Solver

The Quick mode engine uses a **sequential modular** solver in `src/sim/solver/blockSolver.ts`.

## Algorithm

```
1. Select PropertyPackage from project.thermodynamics.propertyMethod
2. Initialize feed streams (T, P, flow, composition → enthalpy)
3. Topological sort with tear stream detection (DFS back-edge analysis)
4. If no recycles → solve blocks in order → done
5. If recycles detected:
     Initialize tear streams with defaults
     Loop (max 50 iterations):
       a. Solve all blocks in topo order
       b. Compare tear stream values
       c. Apply Wegstein acceleration
       d. If max relative change < 1e-4 → converged
```

## Property Package Threading

Every block solver receives the `PropertyPackage` instance, so K-values, enthalpy, entropy, and density all use the selected thermodynamic model consistently.

## Recycle Convergence

### Tear Stream Detection

During DFS topological sort, back-edges identify recycle loops. These become tear streams — the solver breaks the loop and iterates.

### Wegstein Acceleration

After 2+ iterations, Wegstein acceleration is applied:

```
slope = (g(x2) - g(x1)) / (x2 - x1)
q = slope / (slope - 1)      (bounded to [-5, 0])
x_new = (1-q) · g(x2) + q · x2
```

Typical convergence: 3-10 iterations for simple recycles.

## Supported Block Types

| Type | Method | Key Feature |
|------|--------|-------------|
| Feed | Initialize | Reads params or edge spec |
| Flash / Separator | VLE flash | Property-package K-values |
| Mixer | Enthalpy balance | Newton iteration for T |
| Splitter | Flow division | Split ratio parameter |
| Pump | ΔP + power | Rackett liquid density |
| Compressor | Isentropic | Entropy-based Newton iteration |
| Valve | Isenthalpic | Pressure drop |
| Heater / Cooler | Energy balance | Rigorous enthalpy duty |
| DistillationColumn | FUG shortcut | Fenske-Underwood-Gilliland |
| RStoic / RCSTR / RPfr | Stoichiometric | Heat of reaction, adiabatic/isothermal |
| REquil / RGibbs | Equilibrium | Keq from ΔG, bisection |
| Absorber | Kremser | General multi-solute absorption |
| Stripper | Kremser | General stripping |
| HeatExchanger | Counter-current | 80% effectiveness |

## Source

`src/sim/solver/blockSolver.ts`
