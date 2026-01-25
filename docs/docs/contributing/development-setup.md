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
│   │   └── schema.ts       # Zod type definitions
│   └── sim/
│       ├── engine-v2.ts    # Main simulation engine
│       ├── converter.ts    # Schema conversion
│       ├── validator.ts    # Flowsheet validation
│       ├── sizing.ts       # Equipment sizing
│       ├── economics.ts    # Cost estimation
│       ├── blocks/         # Unit operation models
│       │   ├── feed.ts
│       │   ├── mixer.ts
│       │   ├── flash.ts
│       │   └── ...
│       ├── thermo/         # Thermodynamic calculations
│       │   ├── properties.ts
│       │   ├── vle.ts
│       │   └── componentDatabase.ts
│       └── solver/
│           └── blockSolver.ts
├── docs/                   # Documentation (Docusaurus)
├── CONTRIBUTING.md
├── LICENSE
└── README.md
```

## Running Tests

```bash
npm test
```

## Building

```bash
npm run build
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

- **Peng-Robinson EOS** - Replace ideal gas for vapor phase
- **Activity coefficients** - NRTL or UNIQUAC for non-ideal liquids
- **More unit operations** - Absorption column, packed column

### Medium Priority

- **Property database expansion** - Add more chemicals
- **Steam tables** - IAPWS-IF97 implementation
- **Documentation** - Examples and tutorials

### Low Priority

- **Performance optimization** - Solver speed improvements
- **Additional cost correlations** - More equipment types
