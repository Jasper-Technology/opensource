---
sidebar_position: 1
---

# Development Setup

Guide to setting up the Jasper simulation engine for local development.

## Prerequisites

- Node.js 18+
- npm or yarn
- Git

## Clone the Repository

```bash
git clone https://github.com/Jasper-Technology/opensource.git
cd opensource
```

## Project Structure

```
opensource/
├── src/
│   ├── core/
│   │   └── schema.ts                    # Zod type definitions
│   └── sim/
│       ├── solver/
│       │   └── blockSolver.ts           # Sequential modular solver
│       ├── thermo/
│       │   ├── properties.ts            # Cp, enthalpy, entropy, Pvap, density
│       │   ├── pengRobinson.ts          # Peng-Robinson EOS
│       │   ├── nrtl.ts                  # NRTL activity coefficients
│       │   ├── bipDatabase.ts           # Binary interaction parameters
│       │   ├── propertyMethod.ts        # PropertyPackage interface + factory
│       │   ├── componentDatabase.ts     # 70+ component data
│       │   └── __tests__/
│       │       └── quickmode-parity.test.ts
│       ├── engine-v2.ts                 # Simulation engine orchestration
│       ├── sizing.ts                    # Equipment sizing
│       ├── economics.ts                 # Cost estimation
│       └── blocks/                      # Legacy unit operation models
├── docs/                                # Documentation (Docusaurus)
├── CONTRIBUTING.md
├── LICENSE
└── README.md
```

## Running Tests

```bash
# Thermodynamics + solver parity tests (16 tests)
npx tsx src/sim/thermo/__tests__/quickmode-parity.test.ts

# Type checking
npx tsc --noEmit
```

## Code Style

- TypeScript with strict mode
- Functional programming style preferred
- JSDoc comments for public APIs
- Units in SI (K, Pa, mol/s, J/mol)

## Making Changes

1. Create a feature branch
   ```bash
   git checkout -b feature/your-feature
   ```

2. Make changes and add tests

3. Run tests
   ```bash
   npm test
   ```

4. Commit with clear message
   ```bash
   git commit -m "Add feature: description"
   ```

5. Push and create PR
   ```bash
   git push origin feature/your-feature
   ```

## Documentation

Documentation uses Docusaurus. To run locally:

```bash
cd docs
npm install
npm start
```

## Areas for Contribution

### High Priority

- **Wilson/UNIQUAC** activity coefficient models
- **Rigorous distillation** — stage-by-stage MESH equations
- **Henry's Law** for dissolved gases

### Medium Priority

- **Expand BIP database** beyond ~20 pairs
- **UNIFAC** group contribution method
- **Steam tables** (IAPWS-IF97)

### Completed

- ~~Peng-Robinson EOS~~ — `pengRobinson.ts`
- ~~NRTL activity coefficients~~ — `nrtl.ts` + `bipDatabase.ts`
- ~~Shortcut distillation~~ — FUG in `blockSolver.ts`
- ~~Reactor heat of reaction~~ — `properties.ts`
- ~~Recycle convergence~~ — Wegstein in `blockSolver.ts`
- ~~Kremser absorber/stripper~~ — `blockSolver.ts`
