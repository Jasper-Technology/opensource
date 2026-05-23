# Jasper Simulation Engines

Open-source simulation infrastructure powering [Jasper](https://jaspertech.org) — a modern, browser-based chemical process simulation platform.

## Overview

Jasper is built around **three complementary solver tiers**, so users can pick the right tradeoff between speed, rigor, and capability for any given flowsheet. This repository contains the source for all three engines: the in-browser Quick engine, the DWSIM-backed industrial engine, and the IDAES-backed equation-oriented engine.

| Engine | Runs On | Best For | Typical Latency |
|--------|---------|----------|-----------------|
| **Quick** | Browser (TypeScript, no backend) | Teaching, fast iteration, textbook problems, sketching flowsheets | <100 ms |
| **DWSIM** | Railway (C# / .NET wrapping [DWSIM](https://dwsim.org)) | Industrial flowsheets, rigorous VLE, recycle convergence, broad unit-op coverage | 2–30 s |
| **IDAES** | Railway (Python / FastAPI wrapping [IDAES-PSE](https://idaes-pse.readthedocs.io)) | Equation-oriented modeling, optimization, custom unit models, techno-economic analysis | 5–60 s |

The Jasper frontend selects between engines per-project. Users can switch modes at any time; the same flowsheet schema is shared across all three.

---

## 1. Quick Mode (`src/`)

An in-browser sequential-modular solver written in TypeScript. Runs entirely client-side with no backend dependency — perfect for teaching, prototyping, and instant feedback.

### Thermodynamics
Five property methods, selectable per-project:

| Method | Best For | K-Value Model |
|--------|----------|---------------|
| **Ideal** | Ideal mixtures, low pressure | Raoult's Law |
| **Peng-Robinson** | Hydrocarbons, gases, high pressure | Fugacity (phi-phi) |
| **NRTL** | Polar / non-ideal liquids (ethanol-water, amines) | Activity coefficients (gamma-phi) |
| **SRK** | Hydrocarbon screening and gas processing | Fugacity (phi-phi) |
| **RK** | Legacy cubic-EOS screening | Fugacity (phi-phi) |
| **NRTL** | Polar/non-ideal liquids (ethanol-water, amines) | Activity coefficients (gamma-phi) |

Property calculations include:
- **Lee-Kesler** vapor pressure (1–3% error, boiling-point anchored)
- **Rackett** liquid density
- **Entropy** with departure functions for isentropic equipment
- **Heat of reaction** from heats of formation + Cp integration
- **70+ component database** with DIPPR / NIST validated data
- **~20 NRTL BIP pairs** for common systems

### Unit Operations

| Unit Operation | Method |
|---------------|--------|
| Flash / Separator | Rigorous VLE with property-package K-values |
| Distillation Column | Fenske–Underwood–Gilliland shortcut |
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

### Quick-mode usage

```typescript
import { solveFlowsheet } from './src/sim/solver/blockSolver';

const result = solveFlowsheet(project);

if (result.converged) {
  for (const [streamId, state] of result.streams.entries()) {
    console.log(`${state.name}: ${state.T.toFixed(1)} K, ${state.P.toFixed(2)} bar`);
  }
}
```

Run the verification suite:

```bash
npx tsx src/sim/thermo/__tests__/quickmode-parity.test.ts
```

16 tests covering Lee-Kesler Pvap, PR flash, NRTL activity, isentropic compressor, FUG distillation, recycle convergence, and Kremser absorption.

---

## 2. DWSIM Mode (`backends/dwsim/`)

A C# / .NET 8 microservice that wraps the open-source [DWSIM](https://dwsim.org) thermodynamics + flowsheeting library and exposes it over a small HTTP API. Used in Jasper for industrial-grade simulations where the Quick engine's coverage is insufficient.

### How Jasper uses it

- Jasper's frontend posts the project's flowsheet JSON to `POST /api/simulate`.
- The backend translates Jasper's schema into a DWSIM flowsheet (`Services/DwsimSolver.cs`), maps property methods (`Services/PropertyPackageMapper.cs`), runs DWSIM's solver, and returns stream + unit results.
- Long jobs run via an in-process queue (`Services/SimulationQueue.cs`) — clients poll `GET /api/jobs/{jobId}` until completion.
- Per-solve timeout is 5 minutes; CORS allowlist and an `X-API-Key` middleware (`Middleware/ApiKeyAuthMiddleware.cs`) gate the service in production.

### Endpoints

| Route | Purpose |
|-------|---------|
| `GET /api/health` | Wake ping; returns DWSIM assembly version (no auth) |
| `GET /api/units` | Supported unit operations + property methods |
| `POST /api/simulate` | Submit simulation job → returns `jobId` |
| `GET /api/jobs/{jobId}` | Poll job status / fetch results |

### Running locally

```bash
cd backends/dwsim
# DWSIM_PATH must point at a directory containing DWSIM.Automation.dll and friends
export DWSIM_PATH=/usr/local/lib/dwsim
export CORS_ORIGINS=http://localhost:5173
export ASPNETCORE_ENVIRONMENT=Development
dotnet run
```

Or build the container directly with the included `Dockerfile` / `railway.toml`.

---

## 3. IDAES Mode (`backends/idaes/`)

A Python / FastAPI service wrapping [IDAES-PSE](https://idaes-pse.readthedocs.io) and Pyomo. Used in Jasper for equation-oriented modeling, optimization problems, custom unit models, and techno-economic analysis (TEA) workflows that the sequential-modular engines can't express naturally.

### How Jasper uses it

- **Simulation** (`app/api/routes/simulate.py`) — solves IDAES flowsheets built from Jasper's project schema using the helpers in `app/idaes_wrapper/` and `app/units/`.
- **Optimization** (`app/api/routes/optimize.py`) — exposes Pyomo objectives + constraints over the flowsheet.
- **Properties** (`app/api/routes/properties.py`) — pure-component and mixture property lookups backed by the registry in `app/components_registry/`.
- **TEA** (`app/api/routes/tea.py`, `app/tea/`) — capital cost, operating cost, and ESG estimates derived from converged simulation results.
- **Import** (`app/api/routes/import_.py`, `app/import_/`) — parses Aspen `.inp` / `.rep` files, Excel sheets, and other external formats into Jasper's schema.
- **Components / Units** (`app/api/routes/components.py`, `app/api/routes/units.py`) — metadata endpoints the frontend uses to populate selectors.

The TEA + import + units routes work without IDAES installed (useful for local dev). The heavy simulate/optimize/properties routes require the full IDAES + Pyomo + IPOPT stack and are loaded lazily — the service logs a warning and still serves the lighter endpoints when the heavy deps aren't present.

Jobs are queued in-process (`app/core/simulation_queue.py`) with a periodic 10-minute sweep of completed/failed records to keep memory bounded on long-running Railway instances.

### Running locally

```bash
cd backends/idaes
cp .env.example .env   # set CORS_ORIGINS at minimum
./run-local.sh         # or: uvicorn app.main:app --reload
```

Requirements pinned in `requirements.txt` (FastAPI, IDAES-PSE ≥ 2.4, Pydantic 2, Pint, openpyxl, etc.).

---

## Project Structure

```
opensource/
├── src/                              # Quick mode (TypeScript)
│   ├── core/
│   │   └── schema.ts                 # Zod schemas for flowsheet data
│   └── sim/
│       ├── solver/                   # Sequential modular solver
│       ├── thermo/                   # PR, NRTL, Lee-Kesler, BIP DB, component DB
│       ├── blocks/                   # Unit operation models
│       ├── engine-v2.ts
│       ├── sizing.ts                 # Equipment sizing correlations
│       └── economics.ts              # Capital cost estimation
├── backends/
│   ├── dwsim/                        # DWSIM mode (C# / .NET 8)
│   │   ├── Program.cs                # ASP.NET minimal API + assembly resolver
│   │   ├── Services/
│   │   │   ├── DwsimSolver.cs
│   │   │   ├── PropertyPackageMapper.cs
│   │   │   └── SimulationQueue.cs
│   │   ├── Models/                   # Request / response DTOs
│   │   ├── Middleware/               # API-key auth
│   │   ├── Dockerfile
│   │   └── railway.toml
│   └── idaes/                        # IDAES mode (Python / FastAPI)
│       ├── app/
│       │   ├── main.py               # FastAPI app + lifespan
│       │   ├── api/routes/           # health, simulate, optimize, properties, tea, import_, components, units, jobs
│       │   ├── idaes_wrapper/        # IDAES flowsheet builders
│       │   ├── units/                # Unit-op + unit-of-measure helpers
│       │   ├── components_registry/  # Pure-component database
│       │   ├── tea/                  # Techno-economic analysis
│       │   ├── import_/              # Aspen / Excel importers
│       │   ├── comprehend/           # Schema understanding helpers
│       │   ├── core/                 # Job queue, settings
│       │   └── models/               # Pydantic models
│       ├── tests/
│       ├── requirements.txt
│       ├── Dockerfile
│       └── railway.toml
├── docs/                             # Docusaurus documentation site
├── CONTRIBUTING.md
├── LICENSE
└── README.md
```

---
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

**Quick engine (TypeScript)**
- Wilson / UNIQUAC activity coefficient models
- Rigorous stage-by-stage distillation (MESH equations)
- Henry's Law for dissolved gases
- BIP database expansion beyond ~20 pairs
- Component database expansion beyond 70 compounds
- UNIFAC group contribution method
- Steam tables (IAPWS-IF97)

**DWSIM backend (C#)**
- Broader unit-operation coverage in `DwsimSolver.SupportedUnitTypes`
- Better property-method mappings in `PropertyPackageMapper`
- Persistent (Redis / Postgres) job queue to replace the in-memory one

**IDAES backend (Python)**
- Additional IDAES property packages and unit models
- Improved Aspen `.inp` / `.rep` import coverage
- Expanded TEA correlations (heat exchangers, distillation, reactors)
- Optimization examples and benchmarks

**Completed**
- ~~Peng-Robinson EOS~~
- ~~NRTL activity coefficients~~
- ~~Lee-Kesler Pvap + Rackett density~~
- ~~Isentropic compressor~~
- ~~Shortcut distillation (FUG)~~
- ~~Reactor heat of reaction + equilibrium~~
- ~~Recycle convergence (Wegstein)~~
- ~~Kremser absorber / stripper~~
- ~~DWSIM service with queued simulate / poll API~~
- ~~IDAES service with simulate / optimize / properties / TEA routes~~

---

## License

MIT License — see [LICENSE](LICENSE) for details.

## Links

- **Website**: [jaspertech.org](https://jaspertech.org)
- **Documentation**: [docs.jaspertech.org](https://docs.jaspertech.org)
- **Issues**: [GitHub Issues](https://github.com/Jasper-Technology/opensource/issues)
