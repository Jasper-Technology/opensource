---
sidebar_position: 2
---

# Rigorous Mode

Equation-oriented process simulation using the [IDAES](https://idaes.org/) framework, [Pyomo](https://www.pyomo.org/) algebraic modeling language, and the [IPOPT](https://coin-or.github.io/Ipopt/) nonlinear solver.

## What It Is

Rigorous mode formulates your entire flowsheet as a single system of nonlinear algebraic equations and solves them simultaneously. Unlike the sequential modular approach in Quick mode, this handles tightly coupled recycle loops, non-ideal thermodynamics, and complex unit operations without iterative tear-stream convergence.

## Backend Architecture

```
Browser (React)
    │
    │  POST /api/simulate
    ▼
FastAPI service (Railway)
    │
    ├─ Validate flowsheet JSON
    ├─ Enqueue simulation job
    │
    │  { job_id, status, position, queue_length }
    ▼
Browser (React)
    │
    │  Poll GET /api/jobs/{job_id} every 2 s
    ▼
FastAPI service (Railway)
    │
    ├─ Build IDAES model (Pyomo ConcreteModel)
    ├─ Select property package
    ├─ Apply specifications & initial guesses
    ├─ Solve with IPOPT
    │
    │  { status: "done", result: { ... } }
    ▼
Browser (React)
    │
    └─ Display results in stream table & unit panels
```

The FastAPI backend runs on Railway as a containerized service. It accepts a flowsheet payload, enqueues a simulation job, and returns a `job_id`. The client polls for results until the job completes.

## How It Works

### 1. Submit

When you press **Run** with Rigorous mode selected, the client sends a `POST /api/simulate` request containing:

- Flowsheet topology (blocks, arcs)
- Component list
- Property package selection
- Stream specifications (T, P, flow, composition)
- Unit operation parameters
- Solver configuration

The endpoint returns a job descriptor immediately:

```json
{ "job_id": "abc-123", "status": "queued", "position": 2, "queue_length": 5 }
```

### 2. Poll for Results

The client polls `GET /api/jobs/{job_id}` every 2 seconds. While the job is running, the response contains:

```json
{ "status": "running", "result": null, "error": null }
```

When the job finishes, the response contains the full simulation result:

```json
{ "status": "done", "result": { ... }, "error": null }
```

If the solve fails, the response includes an error message:

```json
{ "status": "failed", "result": null, "error": "Solver terminated with infeasible status" }
```

### 3. Result Schema

When `status` is `"done"`, the `result` object has the following shape:

```typescript
interface RigorousResult {
  status: string;              // "done"
  converged: boolean;
  solver_status: string;       // "optimal" | "infeasible" | "maxIterations" | ...
  iterations: number;
  solve_time: number;          // seconds
  degrees_of_freedom: number;
  messages: string[];

  streams: Array<{
    id: string;
    from_node: string;
    to_node: string;
    temperature: number;       // K
    pressure: number;          // Pa
    flow_mol: number;          // mol/s
    flow_mass: number;         // kg/s
    phase: string;
    vapor_fraction: number;
    composition: Record<string, number>;  // mole fractions
    enthalpy: number;          // J/mol
    entropy: number;           // J/(mol·K)
    density: number;           // kg/m³
    molecular_weight: number;  // g/mol
  }>;

  units: Array<{
    id: string;
    name: string;
    type: string;
    duty?: number;             // W (heaters, coolers, condensers)
    work?: number;             // W (pumps, compressors)
    pressure_drop?: number;    // Pa
    efficiency?: number;
    custom_results?: Record<string, number>;
  }>;
}
```

:::info
The `/api/simulate` endpoint requires an `X-API-Key` header for authentication. Set the key via the `VITE_IDAES_API_KEY` environment variable in your `.env` file.
:::

## Solver Configuration

| Parameter | Default | Description |
|-----------|---------|-------------|
| `solver` | `ipopt` | Nonlinear solver |
| `max_iterations` | `100` | Maximum solver iterations |
| `tolerance` | `1e-6` | Convergence tolerance (absolute) |

:::tip
For difficult convergence cases, you can increase `max_iterations` to 200-500. Loosening `tolerance` to `1e-5` may help borderline cases converge but reduces accuracy.
:::

## Degrees of Freedom

IDAES requires the equation system to be **square** — the number of variables must equal the number of equations. The degrees of freedom (DOF) must be exactly **0**.

```
DOF = (number of variables) - (number of equations)
```

| DOF | Meaning | Action |
|-----|---------|--------|
| 0 | Square system | Ready to solve |
| > 0 | Under-specified | Add more specifications (feed conditions, unit params) |
| < 0 | Over-specified | Remove redundant specifications |

The backend validates DOF before attempting a solve and returns an error if DOF is not 0.

## Cold Start Behavior

The Railway container may enter a sleep state after periods of inactivity. The first request after a sleep triggers a **cold start**:

- Container wake-up takes approximately **30 seconds**.
- Subsequent requests run at normal speed (2-10 s typical).
- The client automatically retries on connection timeout.

:::warning
If you see "Backend unavailable," wait ~30 seconds and try again. The container is waking up.
:::

## Rate Limiting

To protect the shared backend, rigorous mode enforces:

- **10 submissions per IP address per minute**
- Exceeding the limit returns a `429 Too Many Requests` response
- The limit resets on a rolling 60-second window

## Property Packages

Rigorous mode supports multiple thermodynamic models. Select one via the **property method selector in the toolbar**. See [Property Packages](../thermodynamics/property-packages.md) for details on each model.

## Limitations

- Requires internet connection to reach the Railway backend.
- Cold starts add latency on first use.
- Maximum flowsheet size: 50 blocks per submission.
- Reactive systems limited to stoichiometric and equilibrium reactor models.
