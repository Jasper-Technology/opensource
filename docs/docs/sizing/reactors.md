---
sidebar_position: 3
---

# Reactor Sizing

All seven reactor types (RCSTR, RPfr, RBatch, RStoic, RYield, REquil, RGibbs) size by **residence time**. This is the standard preliminary-design approach when reaction kinetics are not part of the flowsheet model: volume follows from the volumetric feed rate and a characteristic time for the reacting phase.

## Method

```
V = max(Q̇ · τ, 0.1 m³)

Q̇ = inlet volumetric flow (m³/s)
  = (flow_mol [kmol/h] · MW [kg/kmol] / 3600) / ρ [kg/m³]
```

The residence time τ is selected from the inlet phase:

| Inlet condition | τ | Rationale |
|-----------------|---|-----------|
| Vapor fraction ≤ 0.5 (liquid) | 3600 s (1 h) | Conservative CSTR/batch-equivalent holdup for homogeneous liquid-phase reactions |
| Vapor fraction > 0.5 (gas) | 10 s | Gas-phase space velocity ≈ 360 h⁻¹, typical of fast catalytic reactions |

## Geometry

From the volume, a cylindrical vessel with aspect ratio L/D = 3 is assumed:

```
D = ∛(4·V / (3π))
L = 3·D
```

PFRs report the same diameter/length pair; the cylinder assumption matches the geometry basis of the vessel cost correlations, so sizing and costing stay consistent.

## Worked example

Liquid-phase CSTR, 100 kmol/h aqueous feed (MW ≈ 30 kg/kmol, ρ = 1010 kg/m³):

```
Q̇ = (100 · 30 / 3600) / 1010 ≈ 0.00082 m³/s
V = Q̇ · τ = 0.00082 · 3600 ≈ 3.0 m³

D = ∛(4·3.0 / (3π)) ≈ 1.08 m,  L ≈ 3.2 m
```

## Overriding the defaults

:::tip Override residence time per reaction
The phase-based defaults are deliberately generic — a fermentation needs hours, a steam-methane reformer fractions of a second. Every reactor size records the assumption `residence time τ (phase default — OVERRIDE per reaction)` so the default is never mistaken for a kinetic result.
:::

Three ways to override:

1. **Set the reactor volume directly** — explicit `volume`/`length`+`diameter` parameters on the node take precedence over sizing.
2. **Custom sizing formula** — wrap the reactor as a CustomUnit with a sizing expression (e.g. `flow_vol * tau` with your own τ); see [Custom Sizing](./custom-sizing).
3. **Ask the agent** — the Jasper agent can propose a custom-sized unit with a cited residence time for your chemistry.

## What sizing does *not* do

Reactor sizing does not solve kinetics, catalyst loading, heat-removal limits, or pressure drop. It produces a Class 4–5 volume estimate that is consistent with the cost correlations downstream. For kinetically-limited designs, size the reactor externally and set the volume explicitly.
