---
slug: /
sidebar_position: 1
title: Introduction
---

# Jasper Documentation

Open-source chemical process simulation engine for modern web applications.

<div className="card-grid">
  <a className="card" href="/getting-started/quickstart">
    <h3>Quick Start</h3>
    <p>Get up and running with Jasper in minutes. Learn the basics of building process flowsheets.</p>
  </a>
  <a className="card" href="/thermodynamics/overview">
    <h3>Thermodynamics</h3>
    <p>Heat capacity, enthalpy, and vapor-liquid equilibrium calculations.</p>
  </a>
  <a className="card" href="/unit-operations/feed">
    <h3>Unit Operations</h3>
    <p>Feed, mixer, flash, heater, reactor, distillation, and more equipment models.</p>
  </a>
  <a className="card" href="/components/available-components">
    <h3>Component Database</h3>
    <p>50+ chemicals with validated property data including Antoine coefficients.</p>
  </a>
  <a className="card" href="/api/schema">
    <h3>API Reference</h3>
    <p>TypeScript types and simulation engine interface documentation.</p>
  </a>
  <a className="card" href="/contributing/development-setup">
    <h3>Contributing</h3>
    <p>Development setup, adding new unit operations, and contribution guidelines.</p>
  </a>
</div>

## What is Jasper?

Jasper provides a complete toolkit for chemical process simulation:

- **Thermodynamic calculations** - Heat capacity, enthalpy, vapor-liquid equilibrium
- **Unit operation models** - Feed, mixer, splitter, flash, heater, cooler, pump, compressor, reactor, and more
- **Component database** - 50+ chemicals with validated property data
- **Equipment sizing** - Preliminary sizing correlations for common equipment
- **Cost estimation** - Order-of-magnitude capital cost estimates

## Architecture

The simulation engine uses a **sequential modular** approach:

1. **Topology analysis** - Determine calculation order from flowsheet connectivity
2. **Block solving** - Execute each unit operation in sequence
3. **Stream propagation** - Pass outlet conditions to downstream units
4. **Convergence** - Iterate on recycle streams until convergence

## Try It Online

Visit [jaspertech.org](https://jaspertech.org) to use the full visual process simulator with drag-and-drop flowsheet editing.

## Open Source

Jasper is open source under the MIT license. Contributions are welcome:

- [GitHub Repository](https://github.com/Jasper-Technology/opensource)
- [Contributing Guide](/contributing/development-setup)
