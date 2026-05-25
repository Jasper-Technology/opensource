---
sidebar_position: 1
---

# Simulation Modes

Jasper has **two simulation engines** you pick between via the toolbar toggle, plus **agent-driven optimization** that runs on top of either one.

| Mode | Engine | Runs On | Latency | Tier |
|------|--------|---------|---------|------|
| **Quick** | Jasper built-in (TypeScript) | Browser, no backend | &lt;100 ms | Free |
| **Rigorous** | [DWSIM](https://dwsim.org) (C# / .NET via DWSIM.Automation3) | Railway service | 2 – 30 s | Pro |
| **Optimize** | [IDAES-PSE](https://idaes-pse.readthedocs.io) (Python / Pyomo / IPOPT) | Railway service, invoked **through the Jasper agent** | 5 – 60 s | Pro |

The engine toggle in the toolbar lets you switch between **Quick** and **Rigorous** without rebuilding your flowsheet — blocks, streams, and specs are preserved.

**Optimization is not a toggle**. Ask the agent in chat:

> "minimize H1 duty by varying its outlet temperature between 305 K and 360 K, subject to T ≥ 320 K"

The agent translates the request into an IDAES call, IPOPT solves, and the result renders inline. If you want to apply the optimum, accept the plan card and Jasper patches the flowsheet for you.

## Mode-by-mode

| Capability | Quick | Rigorous (DWSIM) | Optimize (IDAES, via agent) |
|------------|-------|------------------|----------------------------|
| Property methods | Ideal, PR, SRK, RK, NRTL | Ideal, PR, SRK, NRTL, UNIQUAC, UNIFAC, IAPWS-IF97 (steam), DWSIM electrolytes | Ideal, SRK, PR, NRTL, UNIQUAC, eNRTL |
| Phase equilibrium | Raoult's Law / phi-phi / gamma-phi | Full DWSIM VLE / LLE / VLLE | Equation-oriented VLE / LLE / VLLE |
| Component library | 70+ (DIPPR / NIST validated) | DWSIM compound database (~500 compounds) | 70+ (NIST, DIPPR, Perry's, RPP) |
| Recycle handling | Wegstein iteration (tol 1e-4) | DWSIM's solver with tear-stream detection | Simultaneous equation solve (no tearing) |
| DOF check | No | Implicit (DWSIM validates as it solves) | Yes (must be exactly 0) |
| Optimization | No | No | Yes (Pyomo objectives + constraints) |
| Rate limit | None (local) | API-key + CORS | 10 req / min / IP, API-key + CORS |
| Offline | Yes | No (Railway backend) | No (Railway backend) |
| Current status | Shipped | Shipped (Pro) | Shipped (agent-only, Pro) |

## Decision guide

```
                    ┌─────────────────────────┐
                    │   What are you doing?   │
                    └────────────┬────────────┘
                                 │
        ┌────────────────────────┼────────────────────────┐
        ▼                        ▼                        ▼
  Building / teaching     Industrial flowsheet     Solving for a target
  Iterating fast          Need rigorous VLE        Tuning a param
  System nearly ideal     CSTR / PFR / Gibbs       Custom objective
        │                        │                        │
        ▼                        ▼                        ▼
      Quick                   Rigorous              Ask the agent:
                              (DWSIM)               "minimize / maximize …"
                                                    (IDAES under the hood)
```

:::tip Switching simulation modes
Use the **engine toggle in the toolbar** to switch between Quick and Rigorous. The flowsheet is preserved across modes — only the solver backend changes.
:::

:::tip Running an optimization
Open the Jasper agent (sparkles icon) and describe what you want to minimize or maximize, the variables it can adjust, and any constraints. The agent picks the right IDAES call and renders the result inline.
:::

## Deep dives

- [Quick mode](./quick-mode.md) — in-browser sequential modular engine (Jasper built-in)
- [Rigorous mode](./rigorous-mode.md) — DWSIM-powered industrial engine (Pro)
- [Optimize mode](./optimize-mode.md) — IDAES-powered equation-oriented optimization (agent-driven, Pro)
- [Troubleshooting](./troubleshooting.md) — common errors and fixes per mode

## Open source

All three engines are open source under the MIT license at [github.com/Jasper-Technology/opensource](https://github.com/Jasper-Technology/opensource):

- `src/` — Quick mode (TypeScript)
- `backends/dwsim/` — Rigorous mode service (C# / .NET 8)
- `backends/idaes/` — IDAES optimization service (Python / FastAPI)
