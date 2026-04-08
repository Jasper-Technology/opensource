---
sidebar_position: 1
---

# Simulation Modes

Jasper offers two simulation modes to match different stages of process design.

## Quick Mode

The default browser-based simulation engine. Runs entirely in the client with no backend dependency. Now features **full ChemE parity** with textbook-correct thermodynamics.

| Aspect | Detail |
|--------|--------|
| Architecture | Sequential modular, client-side |
| Thermodynamics | Ideal, Peng-Robinson EOS, NRTL activity coefficients |
| Vapor pressure | Lee-Kesler correlation (1-3% error) |
| Liquid density | Rackett equation |
| Entropy | Ideal gas + PR departure functions |
| Solver | Topological sort + Wegstein recycle convergence |
| Latency | Instant (~ms) |
| Offline | Yes |

Quick mode handles every standard ChemE use case:
- **Ideal systems**: Light hydrocarbons, screening studies
- **Hydrocarbons/high-pressure**: PR EOS with fugacity-based flash
- **Polar/non-ideal**: NRTL with ~20 BIP pairs (ethanol-water, amine-water, etc.)
- **Distillation**: Fenske-Underwood-Gilliland shortcut
- **Reactors**: Stoichiometric + heat of reaction, equilibrium
- **Recycles**: Wegstein-accelerated convergence
- **Absorbers/strippers**: Kremser equation

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
- Final design verification against industrial standards
- Systems requiring UNIQUAC, eNRTL, or Henry's Law
- Rigorous stage-by-stage distillation (MESH equations)
- Equation-oriented simultaneous convergence

:::tip When to switch
For most student coursework and conceptual design, **Quick mode** is sufficient. Switch to **Rigorous mode** when you need UNIQUAC/eNRTL, rigorous tray-by-tray distillation, or equation-oriented solving.
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
| Property packages | Ideal, PR, NRTL | Ideal, SRK, PR, NRTL, UNIQUAC, eNRTL |
| Phase equilibrium | Raoult's / PR fugacity / NRTL gamma-phi | Cubic EOS / activity models |
| Vapor pressure | Lee-Kesler | Antoine / Wagner |
| Distillation | Shortcut (FUG) | Rigorous MESH |
| Reactors | Stoichiometric + equilibrium | Kinetic, equilibrium, Gibbs |
| Recycle convergence | Wegstein iteration | Simultaneous equation solve |
| Component library | 70+ | 70+ (NIST, DIPPR, Perry's, RPP) |
| Degrees of freedom check | No | Yes (must be 0) |
| Rate limiting | None | 10 requests/min per IP |

See [Rigorous Mode](./rigorous-mode.md) for a deep dive into the IDAES backend.
