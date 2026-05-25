---
sidebar_position: 4
---

# Optimize Mode

Equation-oriented process optimization using the [IDAES-PSE](https://idaes-pse.readthedocs.io) framework, the [Pyomo](https://www.pyomo.org/) algebraic modeling language, and the [IPOPT](https://coin-or.github.io/Ipopt/) nonlinear solver. Optimize targets the case where you want to *solve for* a decision variable rather than just simulate a fixed flowsheet.

:::info Invoked through the Jasper agent
There is **no Optimize button** in the engine toolbar. Optimization is initiated by asking the Jasper agent in chat — e.g. *"minimize H1 duty by varying its outlet temperature between 305 and 360 K, subject to T ≥ 320 K"*. The agent picks the right IDAES call, IPOPT solves, and the result renders inline. If you want to apply the optimum to your flowsheet, accept the plan card the agent proposes.
:::

Source: [`opensource/backends/idaes/`](https://github.com/Jasper-Technology/opensource/tree/main/backends/idaes)

## What it is

A FastAPI service. Every block and edge in your Jasper flowsheet becomes part of one big `Pyomo.ConcreteModel`, and IPOPT solves the system simultaneously — no tear streams, no Wegstein iteration, no sequential modular pass.

| Aspect | Detail |
|--------|--------|
| Engine | IDAES-PSE + Pyomo + IPOPT |
| Runtime | Python 3.11 |
| Latency | 5 – 60 s typical |
| Auth | `X-API-Key` header |
| Rate limit | 10 requests / minute / IP |
| CORS | Allowlist (required in production) |

## When you'll want it

- You want to **solve for** a parameter (e.g. find the reboiler duty that achieves 99% bottoms purity)
- You're optimizing across multiple decision variables with constraints
- You want a hard degrees-of-freedom check before the solve
- You're building custom Pyomo-defined unit models

If you just want to evaluate a fixed flowsheet, Rigorous (DWSIM) is faster and currently has broader product support.

## Architecture

```
Browser (React)
    │
    │  POST /api/simulate   (X-API-Key)
    ▼
FastAPI service (Railway)
    │
    ├─ require_api_key      (core/auth.py)
    ├─ rate_limiter         (core/rate_limiter.py, 10 req/min/IP)
    ├─ simulation_queue.enqueue → { job_id, status, position, queue_length }
    │
    │  Background thread (CPU-bound; runs off the event loop):
    │     1. Validate composition sums (~1.0)
    │     2. IdaesModelBuilder.build()  ← Pyomo ConcreteModel
    │     3. Select property package
    │     4. Apply feed + unit specs
    │     5. Optional: apply design_specs.py constraints
    │     6. Check degrees_of_freedom() == 0
    │     7. IPOPT solve
    │     8. ResultExtractor → SI-unit stream + unit results
    │
    │  Polled by client:
    ▼
GET /api/jobs/{job_id}
```

`app/main.py`'s lifespan task sweeps completed and failed jobs every 10 minutes so a long-lived Railway instance doesn't accumulate records forever.

## Route surface

The IDAES backend exposes more than just simulate:

| Path | Purpose | Requires IDAES installed? |
|------|---------|--------------------------|
| `GET /health` | Wake ping + version | No |
| `POST /api/simulate` | Build IDAES model, solve with IPOPT, return result | **Yes** |
| `POST /api/optimize` | Same model + Pyomo objective and constraints | **Yes** |
| `POST /api/properties` | Pure-component + mixture property lookups | **Yes** |
| `POST /api/import` | Parse Aspen `.inp` / `.rep`, Excel `.xlsx`, DWSIM `.dwxmz` into a Jasper project | No |
| `GET /api/components` | Component-database metadata for the frontend selector | No |
| `GET /api/units` | Unit-op metadata for the frontend selector | No |
| `GET /api/jobs/{id}` | Poll job status (shared by `simulate` + `optimize`) | No |

The lightweight routes (`import`, `components`, `units`, `health`) load even when IDAES / Pyomo / IPOPT are not installed (`app/main.py` does a guarded import).

## Property packages

| Package | Type | Best for |
|---------|------|----------|
| Ideal | Activity (γ=1) | Ideal mixtures, validation |
| SRK | Cubic EOS | Hydrocarbons, gas processing |
| PR (Peng-Robinson) | Cubic EOS | General-purpose VLE |
| NRTL | Activity coefficient | Polar / non-ideal liquids |
| UNIQUAC | Activity coefficient | Strongly non-ideal liquids, LLE |
| eNRTL | Electrolyte activity | Electrolyte and amine systems |

See [Property Packages](../thermodynamics/property-packages.md) for details on each model.

## How a job actually runs

Inside `app/api/routes/simulate.py`:

1. **Validate** — composition on every feed edge must sum to within ±0.001 of 1.0.
2. **Build** — `IdaesModelBuilder` (in `core/model_builder.py`) constructs the Pyomo `ConcreteModel`. Each Jasper node becomes a corresponding IDAES unit model from `idaes_wrapper/unit_models.py`; each edge becomes a `Stream` with port connections.
3. **Property pkg** — `idaes_wrapper/property_packages.py` attaches the chosen package.
4. **Specs** — feed conditions, unit-op parameters, and (optionally) design specs from `core/design_specs.py` are applied as Pyomo constraints.
5. **DOF check** — `idaes.core.util.model_statistics.degrees_of_freedom(model)` must return **0**. If not, the run fails with a clear error before IPOPT is invoked.
6. **Solve** — IPOPT with the configured `max_iterations` and `tolerance`.
7. **Extract** — `core/result_extractor.py` reads every stream and unit's variable values, converts to SI units, returns the result dict.

The actual solve runs in a thread-pool worker so the asyncio event loop stays responsive.

## Optimize

`POST /api/optimize` reuses the same model-builder pipeline. Adds an objective and (optionally) extra constraints from the request body.

The objective accepts two shapes:

```python
# Per-variable (preferred for unit-level asks):
{"unit_id": "H1", "parameter": "duty", "sense": "minimize"}

# Named metric (whole-flowsheet):
{"metric": "total_duty", "sense": "minimize"}   # also: total_work, COM, total_cost
```

Frontend parameter names are accepted directly (`T`, `P`, `duty`, `dP`, `work`, `flow`, `outletT`, `outletP`); the backend's `PARAM_ALIASES` (in `core/model_builder.py`) maps them to internal IDAES attribute paths per unit type.

```python
class DecisionVariable:
    unit_id: str
    parameter: str          # e.g. "T", "duty", "split_fraction"
    lower_bound: float
    upper_bound: float
    initial_value: float

class Constraint:
    type: Literal["max", "min", "equality"]
    unit_id: str
    parameter: str
    bound: float
```

The route initializes the model first (with decision variables still at their default spec values), then unfixes them and applies bounds + initial guess — this gives IPOPT a feasible starting point and avoids "trivially infeasible" errors when the initial value falls outside the user's bounds.

IPOPT minimizes / maximizes the objective subject to the simulation constraints + user constraints. Returns the optimal point + the converged flowsheet at that point.

## Design specs

`core/design_specs.py` lets you swap a fixed parameter for a target. Classic example: instead of fixing a column reboiler duty, fix the **bottoms product purity** and let IDAES solve for the duty that achieves it. DOF stays 0 because adding the spec also frees the duty.

## Result schema

```typescript
interface OptimizeResult {
  status: string;              // "done"
  converged: boolean;
  solver_status: string;       // "optimal" | "infeasible" | "maxIterations" | ...
  iterations: number;
  solve_time: number;          // seconds
  degrees_of_freedom: number;  // must be 0 when status is "done"
  messages: string[];

  streams: Array<{ /* T, P, flow, composition, phase, ... */ }>;
  units:   Array<{ /* id, type, duty, work, pressure_drop, ... */ }>;
}
```

## Degrees of freedom

IDAES requires a square system: `DOF = 0`.

| DOF | Meaning | Action |
|-----|---------|--------|
| 0 | Square system | Ready to solve |
| &gt; 0 | Under-specified | Add specifications (feed conditions, unit params, design specs) |
| &lt; 0 | Over-specified | Remove redundant specifications |

The backend computes DOF before invoking IPOPT and returns a clear error if it's not 0.

## Import

`/api/import` accepts file uploads and returns a Jasper project. Supported formats:

- **Aspen `.inp`** — input file (`import_/aspen_inp.py`)
- **Aspen `.rep`** — solved report (`import_/aspen_report.py`)
- **Excel `.xlsx`** — Jasper's standard template (`import_/excel.py`)
- **DWSIM `.dwxmz`** — DWSIM project archive (`import_/dwsim.py`)

After parsing, [`app/comprehend/annotator.py`](https://github.com/Jasper-Technology/opensource/blob/main/backends/idaes/app/comprehend/annotator.py) optionally runs a schema-understanding pass that fills in inferred metadata when the source file is ambiguous.

## Local development

```bash
cd backends/idaes
cp .env.example .env            # set CORS_ORIGINS, JASPER_API_KEY
./run-local.sh                  # or: uvicorn app.main:app --reload
```

Without the full IDAES / IPOPT stack you still get `import`, `units`, `components`, and `health`. To run `simulate` locally, install IDAES per the [IDAES install guide](https://idaes-pse.readthedocs.io/en/stable/tutorials/getting_started/index.html).

## Limitations

- Invoked only through the Jasper agent — no standalone Optimize panel
- Requires the Railway backend to reach IPOPT — no offline mode
- 30 s cold start on first request after sleep
- DOF must be exactly 0
- Reactive systems limited to the IDAES reaction-package surface
- Binary interaction parameters for NRTL / UNIQUAC not yet populated for every component pair — falls back to PR with a warning message
