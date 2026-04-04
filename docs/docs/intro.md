---
slug: /
sidebar_position: 1
title: Jasper Documentation
---

# Jasper Documentation

<p className="lead">Open-source chemical process simulation for modern engineering teams.</p>

Jasper provides complete visibility into your chemical processes. Build flowsheets, run simulations, and analyze results with a modern, intuitive interface. Automatically calculate material balances, energy requirements, and equipment sizing across your entire system.

## Simulation Modes

Jasper offers two simulation engines to match your needs:

- **Quick mode** (browser-based) -- Ideal gas / Raoult's Law calculations running entirely in your browser. Instant results, no backend required.
- **Rigorous mode** (IDAES-powered) -- Equation-oriented process simulation using the [IDAES](https://idaes.org/) framework. Supports cubic equations of state (SRK, PR), activity coefficient models (NRTL, UNIQUAC, eNRTL), and 70+ validated components.

See [Thermodynamics Overview](/thermodynamics/overview) for details on each engine's capabilities.

## Why Jasper?

Chemical process simulation is essential for designing efficient systems. When engineers design processes, understanding material balances and energy requirements is critical. Jasper gives you:

- **Thermodynamic calculations** - Heat capacity, enthalpy, and vapor-liquid equilibrium using industry-standard correlations
- **IDAES rigorous simulation** - Equation-oriented solving with SRK, PR, NRTL, UNIQUAC, and eNRTL property packages
- **Unit operation models** - Comprehensive library including mixers, heaters, flash drums, reactors, and distillation columns
- **Component database** - 50+ chemicals in Quick mode; 70+ in Rigorous mode with validated property data from NIST, DIPPR, Perry's, and RPP

## Get started

<div className="card-grid">
  <a className="card" href="/getting-started/quickstart">
    <div className="card-icon">
      <svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M12 2v4M12 18v4M4.93 4.93l2.83 2.83M16.24 16.24l2.83 2.83M2 12h4M18 12h4M4.93 19.07l2.83-2.83M16.24 7.76l2.83-2.83"/></svg>
    </div>
    <h3>Quickstart</h3>
    <p>Get simulations running in under 5 minutes with our TypeScript SDK.</p>
  </a>
  <a className="card" href="/thermodynamics/overview">
    <div className="card-icon">
      <svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M14 4v10.54a4 4 0 1 1-4 0V4a2 2 0 0 1 4 0Z"/></svg>
    </div>
    <h3>Thermodynamics</h3>
    <p>Heat capacity, enthalpy, and VLE calculation methods.</p>
  </a>
  <a className="card" href="/unit-operations/feed">
    <div className="card-icon">
      <svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><rect x="3" y="3" width="18" height="18" rx="2"/><path d="M3 9h18"/><path d="M9 21V9"/></svg>
    </div>
    <h3>Unit Operations</h3>
    <p>Feed, mixer, flash, heater, reactor, and more equipment models.</p>
  </a>
  <a className="card" href="/components/database">
    <div className="card-icon">
      <svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><ellipse cx="12" cy="5" rx="9" ry="3"/><path d="M3 5v14a9 3 0 0 0 18 0V5"/><path d="M3 12a9 3 0 0 0 18 0"/></svg>
    </div>
    <h3>Component Database</h3>
    <p>50+ chemicals with validated thermodynamic property data.</p>
  </a>
</div>

## How it works

The simulation engine uses a **sequential modular** approach:

1. **Topology analysis** - Determine calculation order from flowsheet connectivity
2. **Block solving** - Execute each unit operation in sequence
3. **Stream propagation** - Pass outlet conditions to downstream units
4. **Convergence** - Iterate on recycle streams until convergence

## What gets calculated

For each stream and unit operation, Jasper calculates:

- Material balances (molar and mass flows)
- Energy balances (enthalpy, heat duties)
- Phase equilibrium (vapor/liquid splits)
- Equipment sizing (preliminary)
- Capital cost estimates (order of magnitude)
