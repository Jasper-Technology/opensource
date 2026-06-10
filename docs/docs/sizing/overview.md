---
sidebar_position: 1
---

# Equipment Sizing Overview

Jasper sizes equipment automatically after every converged simulation. Sizing is a deterministic post-processing pass: it reads the standardized simulation result (streams, duties, work, stage counts) and produces a size for every cost-bearing unit — no extra solver iterations, no engine-specific code paths.

## How it works

```
Simulation (Quick / Rigorous / Optimize)
        │  streams (T, P, flow, density, vapor fraction, composition)
        │  unit results (duty, work, stages, reflux ratio)
        ▼
Sizing pass (per unit, closed-form correlations)
        │  size + derived geometry + every assumption recorded
        ▼
Equipment sizes (shown per node, feed the economics engine)
```

Because the pass runs on the standardized result format, the same correlations produce the same sizes regardless of which engine solved the flowsheet. Identical inputs always produce identical sizes.

## Sizing basis by unit type

Every unit type declares one sizing basis, which is also the size variable the economics engine costs against:

| Basis | Unit types | Output |
|-------|-----------|--------|
| Power | Pump, Compressor, Expander | kW (from simulated work) |
| Heat duty | Heater | kW (from simulated duty) |
| Area | Cooler, HeatExchanger | m² (LMTD method) |
| Volume | Flash, Separator, ThreePhaseSeparator, columns, all reactors | m³ (+ diameter, height) |
| Delegate | CustomUnit | inherits its base type, or an agent-defined formula |
| None | Feed, Sink, Mixer, Splitter, Valve, PipeSegment | not sized |

See [Sizing Methods](./methods) for the correlations behind each basis and [Reactor Sizing](./reactors) for reactors in depth.

## Honesty rules

- **Every assumption is recorded.** Each size carries the list of assumptions used to produce it (U value, residence time, flooding fraction, …), visible in the node's Sizing panel.
- **Missing inputs are flagged, never fabricated.** A pump with no simulated work is reported as unsized, with the reason.
- **Defaults are conservative and overridable.** The weakest defaults (e.g. reactor residence time) are explicitly marked "OVERRIDE per reaction" in the recorded assumptions.

## Units

Sizing computes in SI (m², m³, kW) and displays in SI or US units (ft², ft³, hp, MMBTU/hr) with a single toggle. Conversion happens at display time only — stored sizes are always SI.

## Where it lives in this repo

The sizing engine is `src/sim/sizing/` — `index.ts` (the dispatcher), `correlations.ts` (the closed-form math), `assumptions.ts` (every named default), `safeEval.ts` (the custom-formula sandbox), with its test suite alongside. Sizes are the inputs to capital cost estimation; see [Economics Overview](../economics/overview).
