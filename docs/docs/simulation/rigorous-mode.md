---
sidebar_position: 3
---

# Rigorous Mode

Industrial-grade simulation powered by [DWSIM](https://dwsim.org), an open-source process simulator with a ~500-component database and a full library of unit operations. Rigorous mode runs on Jasper's Railway-hosted DWSIM backend — you get DWSIM's capabilities in the browser without installing anything.

:::info Pro feature
Rigorous mode is part of the **Jasper Pro** tier. Sign in with a Pro account to enable it from the engine selector.
:::

Source: [`opensource/backends/dwsim/`](https://github.com/Jasper-Technology/opensource/tree/main/backends/dwsim)

## What it is

A C# / .NET 8 microservice wrapping DWSIM's `Automation3` API. It accepts Jasper's flowsheet JSON, translates it into a DWSIM flowsheet, solves it, and returns stream + unit results.

| Aspect | Detail |
|--------|--------|
| Engine | DWSIM (via DWSIM.Automation3) |
| Runtime | .NET 8 |
| Latency | 2 – 30 s typical |
| Auth | `X-API-Key` header + Pro tier check |
| CORS | Allowlist (required in production) |
| Per-job timeout | 5 minutes |
| Queue | In-process, single Railway instance |

## When to use it

- The flowsheet is industrial / non-ideal (azeotropes, electrolytes, polar systems at high pressure)
- You need CSTR / PFR / Gibbs / equilibrium / stoichiometric reactors
- You need DWSIM's broad property-package coverage (PR, SRK, NRTL, UNIQUAC, UNIFAC, IAPWS-IF97 steam, DWSIM electrolytes)
- You're doing final design verification rather than screening

If Quick mode converges and you only need ballpark numbers, stay in Quick. Switch to Rigorous when accuracy matters.

## Architecture

```
Browser (React)
    │
    │  POST /api/simulate   (X-API-Key)
    ▼
ASP.NET Core service (Railway)
    │
    ├─ ApiKeyAuthMiddleware  →  reject if X-API-Key invalid
    ├─ SimulationQueue.Enqueue → returns { job_id, position, queue_length }
    │
    │  Background thread:
    │     1. Directory.SetCurrentDirectory(DWSIM_PATH)   ← needed for DWSIM's compound DB
    │     2. Automation3.CreateFlowsheet()
    │     3. AddCompound() per component (CAS → name → formula fallback)
    │     4. AddPropertyPackage() via PropertyPackageMapper
    │     5. AddFlowsheetObject() per Jasper unit, wire streams
    │     6. flowsheet.RequestCalculation()
    │     7. extract stream + unit results
    │
    │  Polled by client:
    ▼
GET /api/jobs/{job_id}
    │  → { status: "done"|"running"|"failed", result, error }
    ▼
Browser (React) renders stream table + unit panels
```

The assembly resolver in `Program.cs` (top of the file) loads DWSIM's transitive dependencies from `DWSIM_PATH`. Without it, DWSIM throws `FileNotFoundException` for unresolved DLLs as soon as you touch its types.

## Endpoints

| Method | Path | Auth | Purpose |
|--------|------|------|---------|
| `GET` | `/api/health` | none | Wake ping. Returns `engine`, `engine_version`, `solver_available`. |
| `GET` | `/api/units` | none | Supported unit operations + property methods. |
| `POST` | `/api/simulate` | `X-API-Key` | Submit a flowsheet. Returns `{ job_id, status, position, queue_length }`. |
| `GET` | `/api/jobs/{job_id}` | `X-API-Key` | Poll job status. Returns `{ status, position, result, error, messages }`. |

### Submit and poll

```http
POST /api/simulate
X-API-Key: <key>
Content-Type: application/json

{ "project": { ... Jasper flowsheet ... }, "options": { ... } }
```

```json
{ "job_id": "abc-123", "status": "queued", "position": 2, "queue_length": 5 }
```

Then poll every 2 seconds:

```http
GET /api/jobs/abc-123
X-API-Key: <key>
```

```json
{ "status": "done", "result": { "streams": [...], "units": [...] }, "error": null }
```

## Supported unit operations

The Jasper-to-DWSIM mapping (`Services/DwsimSolver.cs`):

| Jasper type | DWSIM object |
|-------------|--------------|
| `Feed` | Material Stream (source) |
| `Sink` | Material Stream (sink) |
| `Flash` | Gas-Liquid Separator |
| `Mixer` | Stream Mixer |
| `Splitter` | Stream Splitter |
| `Heater` | Heater |
| `Cooler` | Cooler |
| `Pump` | Pump |
| `Compressor` | Compressor |
| `Valve` | Valve |
| `HeatExchanger` | Heat Exchanger |
| `DistillationColumn` | Distillation Column |
| `Absorber` | Absorption Column |
| `Stripper` | Absorption Column |
| `RCSTR` | Continuous Stirred Tank Reactor (CSTR) |
| `RPfr` | Plug-Flow Reactor (PFR) |
| `REquil` | Equilibrium Reactor |
| `RGibbs` | Gibbs Reactor |
| `RStoic` / `RYield` | Conversion Reactor |

## Property packages

| Jasper name | DWSIM package |
|-------------|---------------|
| `Ideal` (or `Raoults`) | Raoult's Law |
| `PR` / `Peng-Robinson` | Peng-Robinson (PR) |
| `SRK` / `Soave-Redlich-Kwong` | SRK |
| `NRTL` | NRTL |
| `UNIQUAC` | UNIQUAC |
| `UNIFAC` | UNIFAC |
| `Steam` / `IAPWS` | Steam Tables (IAPWS-IF97) |

Unmapped methods fall back to Peng-Robinson.

## Component resolution

For each Jasper component, the backend tries DWSIM's `AddCompound` in this order:

1. **CAS number** (most reliable)
2. **Name** (case-sensitive in DWSIM's DB)
3. **Formula** (fallback)

If none of the three resolve, the run fails with `"Compound not found: <name>"`. Add a CAS number to the component in Jasper to fix the most common case.

## Result schema

```typescript
interface RigorousResult {
  status: string;              // "done"
  converged: boolean;
  solve_time: number;          // seconds
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
    composition: Record<string, number>;
    enthalpy: number;          // J/mol
    entropy: number;           // J/(mol·K)
    density: number;           // kg/m³
    molecular_weight: number;  // g/mol
  }>;

  units: Array<{
    id: string;
    name: string;
    type: string;
    duty?: number;             // W
    work?: number;             // W
    pressure_drop?: number;    // Pa
    custom_results?: Record<string, number>;
  }>;
}
```

## Cold start and queue behavior

- The Railway container sleeps after inactivity. First request triggers a ~30 s cold start, then runs at normal speed.
- The simulation queue is in-process and per-Railway-instance. If multiple users submit at once, `position` reflects your spot in line.
- Per-job timeout is **5 minutes**. The thread keeps running on timeout (no hard cancel for arbitrary .NET code), but the queue slot frees so the next caller isn't blocked.

## Local development

```bash
cd backends/dwsim
export DWSIM_PATH=/usr/local/lib/dwsim         # must contain DWSIM.Automation.dll
export CORS_ORIGINS=http://localhost:5173
export JASPER_API_KEY=dev-key
export ASPNETCORE_ENVIRONMENT=Development
dotnet run
```

Or use the included `Dockerfile` and `railway.toml` to build a container.

:::info
DWSIM is GPL-licensed. The Jasper backend service that wraps it is MIT — but the DWSIM binaries loaded at runtime remain under their original GPL license. Read [DWSIM's license](https://github.com/DanWBR/dwsim) before redistributing a packaged binary.
:::

## Limitations

- 5-minute per-job timeout — difficult recycles may need to be split
- In-memory queue — restarting the Railway instance loses in-flight jobs (clients see `404` on poll, retry resubmits)
- DWSIM doesn't expose every internal solver knob through `Automation3` — advanced solver tuning still needs the DWSIM desktop app
- No degrees-of-freedom check (DWSIM is sequential modular under the hood) — flowsheet specifications are validated by DWSIM as it solves, not up front
