---
sidebar_position: 4
---

# Property Packages

Property packages define the thermodynamic models used to calculate phase equilibrium, enthalpies, and densities in [Rigorous mode](../simulation/rigorous-mode.md). Select a package via the **property method selector in the toolbar**.

## Available Packages

### Ideal

Simple property calculations assuming ideal gas and ideal liquid behavior.

| Aspect | Detail |
|--------|--------|
| VLE model | Raoult's Law: `Ki = Psat,i(T) / P` |
| Vapor phase | Ideal gas |
| Liquid phase | Ideal solution |
| Best for | Light gases, similar-molecule mixtures, screening studies |

:::tip
Use Ideal for initial flowsheet debugging. It converges fastest and helps isolate topology issues from thermodynamic issues.
:::

### SRK (Soave-Redlich-Kwong)

Cubic equation of state with Soave's alpha function.

| Aspect | Detail |
|--------|--------|
| EOS | `P = RT/(V-b) - a(T)/[V(V+b)]` |
| Vapor phase | SRK EOS |
| Liquid phase | SRK EOS |
| Best for | Hydrocarbons, natural gas processing, refinery applications |

SRK handles non-ideal vapor behavior well and is the standard choice for hydrocarbon systems at moderate pressures.

### PR (Peng-Robinson)

The industry-standard cubic EOS for oil and gas applications.

| Aspect | Detail |
|--------|--------|
| EOS | `P = RT/(V-b) - a(T)/[V(V+b) + b(V-b)]` |
| Vapor phase | PR EOS |
| Liquid phase | PR EOS |
| Best for | Oil & gas, high-pressure systems, supercritical fluids |

PR provides better liquid density predictions than SRK, particularly near the critical point. It is the default choice for most industrial hydrocarbon simulations.

### NRTL (Non-Random Two-Liquid)

Activity coefficient model for non-ideal liquid mixtures.

| Aspect | Detail |
|--------|--------|
| Liquid phase | NRTL activity coefficients |
| Vapor phase | Ideal gas (or PR for high pressure) |
| Parameters | Binary interaction parameters (alpha, tau) |
| Best for | Polar mixtures, alcohol-water systems, azeotropes |

:::warning
NRTL requires binary interaction parameters for each component pair. If parameters are unavailable for your system, the solver falls back to **Ideal**.
:::

### UNIQUAC (Universal Quasi-Chemical)

Activity coefficient model based on local composition theory with surface area and volume parameters.

| Aspect | Detail |
|--------|--------|
| Liquid phase | UNIQUAC activity coefficients |
| Vapor phase | Ideal gas (or PR for high pressure) |
| Parameters | Binary interaction parameters, molecular r and q values |
| Best for | Complex mixtures, polymer solutions, systems with molecules of very different sizes |

:::warning
Falls back to **Ideal** if binary interaction parameters are not available for the selected component pair.
:::

### eNRTL (Electrolyte NRTL)

Extended NRTL model for systems containing ionic species.

| Aspect | Detail |
|--------|--------|
| Liquid phase | eNRTL activity coefficients (ion-molecule, ion-ion interactions) |
| Vapor phase | Ideal gas |
| Parameters | Electrolyte binary interaction parameters |
| Best for | Acid gas treating (CO2/H2S in amine), saline solutions, electrolyte systems |

:::warning
Falls back to **Ideal** if electrolyte interaction parameters are not available.
:::

## Selection Guide

| System Type | Recommended Package |
|-------------|-------------------|
| Light hydrocarbons, natural gas | SRK or PR |
| Heavy hydrocarbons, refinery | PR |
| High-pressure / supercritical | PR |
| Alcohol-water, polar organics | NRTL |
| Azeotropic distillation | NRTL |
| Polymer solutions, mixed-size molecules | UNIQUAC |
| Amine gas treating | eNRTL |
| Screening / debugging | Ideal |

## How to Select

1. Open the editor toolbar above the flowsheet canvas.
2. Click the **property method selector**.
3. Choose a property package.
4. Press **Run**.

The property package applies globally to the entire flowsheet. All unit operations and streams use the same thermodynamic model.

:::info
The property method selector only appears when **Rigorous mode** is active. Quick mode always uses the Ideal package.
:::

## Component Database

Rigorous mode provides **70+ validated components** sourced from:

- **NIST** — National Institute of Standards and Technology
- **DIPPR** — DIPPR 801 Database
- **Perry's Chemical Engineers' Handbook** — critical properties, heat capacity correlations
- **RPP** (Reid, Prausnitz, Poling) — equation of state parameters, interaction coefficients

Each component includes: molecular weight, critical temperature, critical pressure, acentric factor, heat capacity coefficients, Antoine coefficients, and (where available) binary interaction parameters for NRTL/UNIQUAC.
