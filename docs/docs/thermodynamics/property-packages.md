---
sidebar_position: 4
---

# Property Packages

Property packages define the thermodynamic models used to calculate phase equilibrium, enthalpies, and densities. In Quick mode, five packages are available natively. Rigorous mode adds UNIQUAC and eNRTL via the IDAES backend. Select a package via the **property method selector in the toolbar**.

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

### PR (Peng-Robinson)

The industry-standard cubic EOS for oil and gas applications. **Now available in Quick mode.**

| Aspect | Detail |
|--------|--------|
| EOS | `P = RT/(V-b) - a(T)/[V(V+b) + b(V-b)]` |
| Flash | Phi-phi: iterative K from fugacity coefficient ratios |
| Enthalpy | Ideal gas + PR departure function |
| Entropy | Ideal gas + PR departure function |
| Density | From PR compressibility factor Z |
| Best for | Hydrocarbons, natural gas, high-pressure, supercritical |

PR provides rigorous VLE via fugacity coefficients, solving the cubic equation analytically (Cardano's method) and selecting the smallest Z root for liquid, largest for vapor.

### SRK (Soave-Redlich-Kwong)

Classic cubic EOS for hydrocarbon systems and gas processing.

| Aspect | Detail |
|--------|--------|
| EOS | `P = RT/(V-b) - a(T)/[V(V+b)]` |
| Flash | Phi-phi with SRK fugacity coefficients |
| Enthalpy | Ideal gas + cubic departure function |
| Entropy | Ideal gas + cubic departure function |
| Density | From SRK compressibility factor Z |
| Best for | Hydrocarbon screening, gas transmission, vapor-liquid checks |

### RK (Redlich-Kwong)

Legacy cubic EOS with a temperature-dependent attraction term.

| Aspect | Detail |
|--------|--------|
| EOS | `P = RT/(V-b) - a(T)/[V(V+b)]` |
| Flash | Phi-phi with RK fugacity coefficients |
| Enthalpy | Ideal gas + cubic departure function |
| Entropy | Ideal gas + cubic departure function |
| Density | From RK compressibility factor Z |
| Best for | Older design correlations, quick hydrocarbon screening |

### NRTL (Non-Random Two-Liquid)

Activity coefficient model for non-ideal liquid mixtures. **Now available in Quick mode.**

| Aspect | Detail |
|--------|--------|
| Liquid phase | NRTL activity coefficients (gamma) |
| VLE | Modified Raoult's: `Ki = γi · Psat,i / P` |
| BIP database | ~20 common pairs (water-alcohol, amine-water, hydrocarbons) |
| Vapor phase | Ideal gas |
| Best for | Polar mixtures, alcohol-water systems, azeotropes |

The NRTL flash iterates K-values with composition-dependent activity coefficients until convergence.

#### Available BIP Pairs

| System | Pairs |
|--------|-------|
| Water-Alcohol | H2O/EtOH, H2O/MeOH |
| Water-Organic | H2O/Acetone, H2O/Acetic acid, H2O/Ethyl acetate |
| Amine-Water | MEA/H2O, DEA/H2O, MDEA/H2O |
| Hydrocarbon | Benzene/Cyclohexane, Benzene/Toluene, n-Hexane/Benzene |
| Alcohol-Organic | EtOH/Benzene, MeOH/Chloroform, MeOH/Benzene |
| Organic-Organic | Acetone/Chloroform, Acetone/Benzene |

:::warning
Pairs without BIP data fall back to ideal behavior (γ = 1). If your system needs specific BIPs not in the database, use Rigorous mode or contribute new BIPs.
:::

## Rigorous Mode Packages (DWSIM + IDAES Backends)

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

| System Type | Quick Mode | Rigorous |
|-------------|-----------|----------|
| Light hydrocarbons, natural gas | PR or SRK | SRK or PR |
| Legacy cubic screening | RK | RK |
| High-pressure / supercritical | PR | PR |
| Alcohol-water, polar organics | NRTL | NRTL |
| Azeotropic distillation | NRTL | NRTL |
| Amine gas treating | NRTL | eNRTL |
| Polymer solutions | Ideal | UNIQUAC |
| Screening / debugging | Ideal | Ideal |

## How to Select

1. Open the editor toolbar above the flowsheet canvas.
2. Click the **property method selector**.
3. Choose a property package.
4. Press **Run**.

The property package applies globally to the entire flowsheet. All unit operations and streams use the same thermodynamic model.

:::info
The property method selector is available in both **Quick** and **Rigorous** modes. Quick mode supports Ideal, PR, SRK, RK, and NRTL; Rigorous mode (DWSIM) additionally supports UNIQUAC, UNIFAC, IAPWS-IF97 steam, and DWSIM's electrolyte packages.
:::

## Component database

| Mode | Source | Count |
|------|--------|-------|
| Quick | Bundled in the TypeScript engine — NIST, DIPPR, Perry's, RPP | 70+ |
| Rigorous | DWSIM compound database (resolved via CAS / name / formula) | ~500 |

Each Quick-mode component includes: molecular weight, critical temperature, critical pressure, acentric factor, heat capacity coefficients, Antoine / Lee-Kesler vapor pressure coefficients, and (where available) NRTL binary interaction parameters.

In Rigorous mode, Jasper components are resolved against DWSIM's database. Add a CAS number to each Jasper component for the most reliable resolution.
