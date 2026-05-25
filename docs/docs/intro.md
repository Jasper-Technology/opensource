---
slug: /
sidebar_position: 1
title: Jasper Documentation
---

# Jasper Documentation

<p className="lead">Open-source chemical process simulation for modern engineering teams.</p>

Jasper provides complete visibility into your chemical processes. Build flowsheets, run simulations, and analyze results with a modern, intuitive interface. Automatically calculate material balances, energy requirements, and equipment sizing across your entire system.

## Simulation Modes

Jasper has **two simulation engines** plus **agent-driven optimization** on top of either one.

- **[Quick](/simulation/quick-mode)** — Jasper's in-browser TypeScript engine. PR / NRTL / Ideal, sequential modular with Wegstein recycle. Instant feedback, runs offline. **Free.**
- **[Rigorous](/simulation/rigorous-mode)** — Railway service wrapping [DWSIM](https://dwsim.org). Industrial-grade flowsheets, ~500-compound database, full DWSIM unit-op library including CSTR / PFR / Gibbs / equilibrium reactors. **Jasper Pro.**
- **[Optimize](/simulation/optimize-mode)** — Railway service wrapping [IDAES-PSE](https://idaes-pse.readthedocs.io). Equation-oriented modeling on Pyomo + IPOPT for custom optimization objectives. **Invoked through the Jasper agent**, not a separate engine button. **Jasper Pro.**

See [Simulation Modes](/simulation/overview) for the full comparison and decision guide.

## Why Jasper?

Chemical process simulation is essential for designing efficient systems. Jasper gives you:

- **Two engines, one flowsheet** — switch between Quick and Rigorous without rebuilding your model; optimization runs through the agent on top of either
- **Industry-standard thermodynamics** — PR, SRK, NRTL, UNIQUAC, eNRTL, UNIFAC, IAPWS-IF97 across the engines
- **Full unit-op library** — flash, distillation, reactors (CSTR / PFR / Gibbs / equilibrium / stoichiometric), heat exchangers, pumps, compressors, valves, absorbers / strippers
- **Open source** — MIT-licensed at [github.com/Jasper-Technology/opensource](https://github.com/Jasper-Technology/opensource)

## Get started

<div className="card-grid">
  <a className="card" href="/docs/simulation/overview">
    <div className="card-icon">
      <svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M14 4v10.54a4 4 0 1 1-4 0V4a2 2 0 0 1 4 0Z"/></svg>
    </div>
    <h3>Simulation Modes</h3>
    <p>Quick, DWSIM, and agent-driven IDAES optimization — compare them and pick the right approach.</p>
  </a>
  <a className="card" href="/docs/unit-operations/feed">
    <div className="card-icon">
      <svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><rect x="3" y="3" width="18" height="18" rx="2"/><path d="M3 9h18"/><path d="M9 21V9"/></svg>
    </div>
    <h3>Unit Operations</h3>
    <p>Feed, mixer, flash, heater, reactor, columns, and more equipment models.</p>
  </a>
  <a className="card" href="/docs/components/database">
    <div className="card-icon">
      <svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><ellipse cx="12" cy="5" rx="9" ry="3"/><path d="M3 5v14a9 3 0 0 0 18 0V5"/><path d="M3 12a9 3 0 0 0 18 0"/></svg>
    </div>
    <h3>Component Database</h3>
    <p>70+ chemicals with validated thermodynamic property data.</p>
  </a>
</div>

## How it works

Each mode solves the same flowsheet differently:

- **Quick** — sequential modular: topology sort → block-by-block solve → Wegstein iteration on recycle streams.
- **Rigorous** — DWSIM's solver with tear-stream detection. Same flowsheet, broader thermo + unit-op coverage.
- **Optimize** — equation-oriented: every block and stream becomes equations, IPOPT solves the whole system simultaneously (no tear streams).

## What gets calculated

For each stream and unit operation, Jasper calculates:

- Material balances (molar and mass flows)
- Energy balances (enthalpy, heat duties)
- Phase equilibrium (vapor/liquid splits)
- Equipment sizing (preliminary)
- Capital cost estimates (order of magnitude)
