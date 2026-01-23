# Jasper Simulation Engine

## Overview

Jasper now uses **rigorous thermodynamic calculations** and **sequential modular solving** - similar to AspenPlus, DWSIM, and other professional simulators.

## Architecture

```
┌─────────────────────────────────────────┐
│         Validation Phase                │
│  - Check connectivity                   │
│  - Verify specifications                │
│  - Validate compositions                │
└──────────────┬──────────────────────────┘
               │
               ▼
┌─────────────────────────────────────────┐
│      Sequential Modular Solver          │
│  1. Topological sort (feed→product)    │
│  2. Solve blocks in order              │
│  3. Pass results downstream            │
└──────────────┬──────────────────────────┘
               │
               ▼
┌─────────────────────────────────────────┐
│      Thermodynamic Properties           │
│  - Heat capacity (Cp)                  │
│  - Enthalpy (H)                        │
│  - Phase equilibrium (VLE)             │
│  - Density (ρ)                         │
└─────────────────────────────────────────┘
```

## Current Implementation

### ✅ Implemented Features

1. **Thermodynamic Properties** (`thermo/properties.ts`)
   - Ideal gas heat capacity: `Cp = f(T)` using polynomial correlations
   - Ideal gas enthalpy: `H = Hf + ∫Cp dT`
   - Vapor pressure: Clausius-Clapeyron equation
   - K-values (VLE): Raoult's Law for ideal mixtures
   - Rachford-Rice flash calculation for vapor/liquid split
   - Mixture properties (molar basis)

2. **Block Solvers** (`solver/blockSolver.ts`)
   - **Feed**: Initializes streams from specifications
   - **Flash/Separator**: Rigorous VLE flash (adiabatic)
   - **Mixer**: Mass & energy balance (adiabatic mixing)
   - **Splitter**: Equal split (or specified fractions)
   - **Pump**: Isentropic compression with efficiency
   - **Heater/Cooler**: Energy balance with specified outlet T or duty

3. **Solver Algorithm**
   - Topological sorting for execution order
   - Sequential modular approach (AspenPlus-style)
   - Cycle detection for recycles (basic)

### 🔧 Limitations & Future Improvements

1. **Thermodynamic Models** (Currently: Ideal Gas + Raoult's Law)
   - [ ] Add **Peng-Robinson EOS** for real gases
   - [ ] Add **NRTL/UNIQUAC** for non-ideal liquid mixtures
   - [ ] Add **CO2-MEA** reaction equilibrium (for carbon capture)
   - [ ] Integrate **CoolProp** or **Cantera** for rigorous properties

2. **Phase Equilibrium**
   - [x] Basic VLE flash (Rachford-Rice)
   - [ ] Multi-stage columns (McCabe-Thiele, Fenske-Underwood-Gilliland)
   - [ ] Reactive distillation
   - [ ] LLE (liquid-liquid equilibrium)

3. **Reaction Kinetics**
   - [ ] Add reactor models (CSTR, PFR, PBR)
   - [ ] Arrhenius kinetics
   - [ ] CO2 absorption/desorption kinetics

4. **Convergence**
   - [x] Sequential modular (acyclic flowsheets)
   - [ ] **Wegstein acceleration** for recycles
   - [ ] **Direct substitution** with under-relaxation
   - [ ] Equation-oriented solving (optional)

5. **Column Models**
   - [ ] Absorber (tray-by-tray)
   - [ ] Stripper (rigorous)
   - [ ] Distillation column (MESH equations)

## Mathematical Foundations

### Mass Balance

For any block:
```
Σ(F_in * z_in) = Σ(F_out * z_out)
```

Where:
- `F` = molar flow rate (kmol/h)
- `z` = mole fraction of component i

### Energy Balance

```
Σ(F_in * H_in) + Q + W = Σ(F_out * H_out)
```

Where:
- `H` = molar enthalpy (kJ/mol)
- `Q` = heat duty (kJ/h)
- `W` = work (kJ/h)

### Phase Equilibrium (VLE)

Raoult's Law (ideal):
```
K_i = P_vap_i / P_total
y_i = K_i * x_i
```

Rachford-Rice:
```
Σ[z_i(K_i - 1) / (1 + V(K_i - 1))] = 0
```

Solve for vapor fraction `V`.

### Enthalpy Calculation

Ideal gas:
```
H(T) = Hf + ∫[Cp dT] from T0 to T
Cp = a + bT + cT² + dT³ + eT⁴
```

### Flash Calculation

Given: Feed (F, z, T, P)

1. Calculate K-values at (T, P)
2. Solve Rachford-Rice for V
3. Calculate phase compositions:
   ```
   x_i = z_i / [1 + V(K_i - 1)]
   y_i = K_i * x_i
   ```

## Component Database

Currently supported pure components:
- H2O (Water)
- CO2 (Carbon Dioxide)
- N2 (Nitrogen)
- O2 (Oxygen)
- MEA (Monoethanolamine)

Data sources: DIPPR, NIST Chemistry WebBook

### Adding New Components

Edit `thermo/properties.ts`:

```typescript
'YOUR_COMPONENT': {
  name: 'Component Name',
  MW: 44.01,        // Molecular weight (g/mol)
  Tc: 304.13,       // Critical temperature (K)
  Pc: 73.77,        // Critical pressure (bar)
  omega: 0.228,     // Acentric factor
  Tb: 194.65,       // Normal boiling point (K)
  Hf: -393.5,       // Heat of formation (kJ/mol)
  Cp_coef: [a, b, c, d, e], // Cp coefficients
},
```

## Validation Rules

Before solving, the validator checks:

✅ Feed streams have complete specifications (T, P, flow, composition)  
✅ All compositions sum to 1.0  
✅ No orphaned blocks (disconnected units)  
✅ All required block parameters are set  
✅ Stream connections reference valid ports  

## Usage Example

```typescript
import { solveFlowsheet } from './solver/blockSolver';

// Solve the flowsheet
const result = solveFlowsheet(project);

if (result.converged) {
  // Access stream results
  for (const [streamId, state] of result.streams.entries()) {
    console.log(`${state.name}: ${state.T} K, ${state.P} bar`);
    console.log(`  Flow: ${state.flow} kmol/h`);
    console.log(`  Composition:`, state.composition);
  }

  // Access block results
  for (const [blockId, data] of result.blockResults.entries()) {
    console.log(`Block ${blockId}:`, data);
  }
} else {
  console.error('Solver failed:', result.error);
}
```

## Performance Notes

- **Sequential modular** is fast for acyclic flowsheets
- Recycles require iteration (not yet optimized)
- Flash calculations converge in ~5-10 iterations typically
- Large flowsheets (>100 blocks) may need optimization

## Contributing

To add new unit operations:

1. Add solver logic in `solver/blockSolver.ts`
2. Follow the pattern:
   ```typescript
   function solveYourUnit(
     block: UnitOpNode,
     project: JasperProject,
     streams: Map<string, StreamState>,
     results: Map<string, any>
   ) {
     // Get inlet streams
     // Solve mass & energy balances
     // Set outlet streams
     // Store results
   }
   ```
3. Add to switch statement in `solveBlock()`

## References

1. **Felder & Rousseau** - Elementary Principles of Chemical Processes
2. **Seader, Henley, Roper** - Separation Process Principles
3. **Fogler** - Elements of Chemical Reaction Engineering
4. **Prausnitz et al.** - The Properties of Gases and Liquids
5. **AspenPlus Documentation** - Sequential Modular Algorithm

## License

MIT - See LICENSE file

---

**Next Steps:**
- Integrate Peng-Robinson EOS
- Add multi-stage column models
- Implement Wegstein acceleration for recycles
- Add reaction kinetics module
- Optimize for large flowsheets

