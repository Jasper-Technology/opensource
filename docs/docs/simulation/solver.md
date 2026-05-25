---
sidebar_position: 1
---

# Block Solver

Jasper uses a **sequential modular** solver that processes unit operations one at a time in topological order, with recycle convergence for cyclic flowsheets.

## Algorithm

```
1. Select property package from project.thermodynamics.propertyMethod
2. Initialize feed streams (T, P, flow, composition → enthalpy)
3. Topological sort with tear stream detection
4. If no recycles:
     Solve blocks in order → done
5. If recycles detected:
     Initialize tear streams with defaults
     Loop (max 50 iterations):
       a. Solve all blocks in topo order
       b. Compare tear stream values (T, P, flow, composition)
       c. Apply Wegstein acceleration
       d. If max relative change < 1e-4 → converged
```

## Property Package Threading

The solver creates a `PropertyPackage` from the project settings and passes it to every block solver. This means:

- Flash drums use the correct K-value model (Ideal, PR, or NRTL)
- Compressors use rigorous entropy for isentropic calculations
- Distillation columns use property-package K-values for relative volatilities
- Absorbers use K-values for equilibrium slope in Kremser

```typescript
const methodName = project.thermodynamics?.propertyMethod ?? 'Ideal';
const pkg = getPropertyPackage(methodName);
```

## Recycle Convergence

### Tear Stream Detection

During topological sort, back-edges in the DFS identify recycle loops. These edges become **tear streams** — the solver breaks the loop at these points and iterates.

### Wegstein Acceleration

After 2+ iterations, Wegstein acceleration is applied to tear stream variables:

```
slope = (g(x2) - g(x1)) / (x2 - x1)
q = slope / (slope - 1)
x_new = (1 - q) · g(x2) + q · x2
```

Where `q` is bounded to [-5, 0] for stability.

### Convergence Criteria

- **Tolerance**: max relative change < 1e-4
- **Max iterations**: 50
- **Variables checked**: T, P, flow, all mole fractions

## SolverResult

```typescript
interface SolverResult {
  converged: boolean;
  streams: Map<string, StreamState>;
  blockResults: Map<string, any>;
  error?: string;
  recycleIterations?: number;
}
```

## StreamState

```typescript
interface StreamState {
  id: string;
  name: string;
  T: number;           // K
  P: number;           // bar
  flow: number;        // kmol/h
  composition: Record<string, number>;  // mole fractions
  phase: 'V' | 'L' | 'VL';
  H: number;           // kJ/mol
}
```

## Supported Block Types

| Type | Solver | Key Feature |
|------|--------|-------------|
| Feed | Initialize | Reads params or edge spec |
| Flash / Separator | VLE flash | Property-package K-values |
| Mixer | Enthalpy balance | Newton iteration for T |
| Splitter | Flow division | Split ratio parameter |
| Pump | ΔP + power | Rackett liquid density |
| Compressor | Isentropic + efficiency | Entropy-based Newton iteration |
| Valve | Isenthalpic | Pressure drop |
| Heater / Cooler | Energy balance | Rigorous enthalpy duty |
| DistillationColumn | Fenske-Underwood-Gilliland | Shortcut distillation |
| RStoic / RCSTR / RPfr / etc. | Stoichiometric + heat of rxn | Adiabatic or isothermal |
| REquil / RGibbs | Equilibrium | Keq from ΔG, bisection |
| Absorber | Kremser | General multi-solute |
| Stripper | Kremser | General stripping |
| HeatExchanger | Counter-current | 80% effectiveness |

## Source

`src/sim/solver/blockSolver.ts`
