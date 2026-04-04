---
sidebar_position: 1
---

# Simulation Modes

Jasper offers two simulation modes to match different stages of process design.

## Quick Mode

The default browser-based simulation engine. Runs entirely in the client with no backend dependency.

| Aspect | Detail |
|--------|--------|
| Architecture | Sequential modular, client-side |
| Thermodynamics | Ideal assumptions (Raoult's Law VLE) |
| Solver | Direct sequential solve |
| Latency | Instant (~ms) |
| Offline | Yes |

Quick mode is ideal for:
- Rapid prototyping and screening studies
- Teaching and demonstrations
- Systems that behave nearly ideally (light hydrocarbons, simple aqueous mixtures)

## Rigorous Mode

Industrial-grade simulation powered by the [IDAES](https://idaes.org/) framework and the IPOPT nonlinear solver. Calculations run on a FastAPI backend hosted on Railway.

| Aspect | Detail |
|--------|--------|
| Architecture | Equation-oriented, server-side (IDAES + Pyomo) |
| Thermodynamics | Cubic EOS (SRK, PR), activity models (NRTL, UNIQUAC), electrolytes (eNRTL) |
| Solver | IPOPT (Interior Point Optimizer) |
| Latency | 2-30 s depending on complexity |
| Offline | No — requires backend connection |

Rigorous mode is ideal for:
- Non-ideal systems (azeotropes, strongly associating mixtures)
- Accurate energy balances and equipment sizing
- Final design verification against industrial standards

:::tip When to switch
Start with **Quick mode** to build and validate your flowsheet topology. Switch to **Rigorous mode** when you need accurate thermodynamics or your system involves non-ideal behavior.
:::

## Switching Between Modes

Use the **engine toggle in the toolbar**:

```
┌──────────────────────────────────┐
│  ⚡ Quick  │  🔬 Rigorous  ▾    │
└──────────────────────────────────┘
```

1. Open the toolbar above the flowsheet canvas.
2. Click the **engine toggle**.
3. Select **Quick** or **Rigorous**.
4. Press **Run** — the selected engine handles the solve.

:::info
Switching modes does not change your flowsheet. All blocks, streams, and specifications are preserved. Only the solver backend changes.
:::

## Comparison

| Feature | Quick | Rigorous |
|---------|-------|----------|
| Property packages | Ideal only | Ideal, SRK, PR, NRTL, UNIQUAC, eNRTL |
| Phase equilibrium | Raoult's Law | Cubic EOS / activity models |
| Component library | 50+ | 70+ (NIST, DIPPR, Perry's, RPP) |
| Recycle convergence | Wegstein iteration | Simultaneous equation solve |
| Degrees of freedom check | No | Yes (must be 0) |
| Rate limiting | None | 10 requests/min per IP |

See [Rigorous Mode](./rigorous-mode.md) for a deep dive into the IDAES backend.
