---
sidebar_position: 3
---

# Costing Methods

The math from equipment size to total module cost, and from annual flows to OPEX. Every step pulls its numbers from the [cost database](./cost-database) with full provenance.

## Correlation forms

The database stores six functional forms. Each correlation row declares its form, coefficients, valid size range, currency, and base index/year.

### Turton log-polynomial (`turton_log10`)

Purchased cost at the correlation's base year (2001, CEPCI 397):

```
log₁₀(Cp⁰) = K₁ + K₂·log₁₀(S) + K₃·(log₁₀ S)²
```

Pressure factor (piecewise, pressure in barg):

```
log₁₀(Fp) = C₁ + C₂·log₁₀(P) + C₃·(log₁₀ P)²
```

Bare-module cost (installation, piping, instrumentation):

```
C_BM = Cp⁰ · (B₁ + B₂·F_M·F_P)        two-factor (exchangers, vessels, pumps)
C_BM = Cp⁰ · F_BM·F_M·F_P             single-factor (heaters, some reactors)
```

### Seider/SSLW log-natural (`sslw_ln`)

```
Cp = exp(a₁ + a₂·ln(S) + a₃·(ln S)²)         base year 2006 (CE 500)
Fp = c₀ + c₁·(P/P_ref) + c₂·(P/P_ref)²
C_BM = F_M · F_P · Cp · F_install             F_install default 2.19
```

SSLW publishes purchased costs without Turton's bare-module split, so an installation factor reconciles the two bases — this is why multi-source comparisons are possible at the bare-module level.

### Vessels by weight (`sslw_vessel`)

Volume → cylindrical geometry (L/D = 4) → shell weight → cost:

```
W = π·(D + t)·(L + 0.8·D)·t·ρ          shell weight, lb
Cp = exp(a₁ + a₂·ln W + a₃·(ln W)²)
```

### Pumps by size factor (`sslw_pump`)

Power → flow at an assumed head (50 m, η = 0.7) → size factor:

```
S = Q_gpm · √(H_ft)
Cp = exp(a₁ + a₂·ln S + a₃·(ln S)²)
```

### Column internals (`sslw_trays`, `packing`)

Trays: cost per tray from diameter, with a count factor and type/material factors:

```
C = N · N_factor · F_type · F_material(D) · base(D) · escalation · F_install
```

Packing: bed volume × unit cost by packing type/material, plus a distributor allowance. Columns are costed as shell (vessel correlation) + internals, each with its own provenance.

## From purchased cost to CAPEX

Worked example — floating-head heat exchanger, 100 m², 25 barg, carbon steel, US-GC, Class 5:

| Step | Calculation | Value |
|------|------------|-------|
| Purchased cost (2001) | `10^(4.8306 − 0.8509·2 + 0.3187·4)` | $54.5K |
| Pressure factor | Turton C-coefficients @ 25 barg | 1.137 |
| Material factor | carbon steel | 1.0 |
| Bare-module (2001) | `54.5K · (1.63 + 1.66·1.0·1.137)` | $192K |
| Escalation | Jasper Index 2001 → today (≈ 2.3×) | $445K |
| Location factor | US-GC (base) | × 1.0 |
| Contingency | Class 5, +18% | **$525K total module** |

## Escalation

All costs escalate by the ratio of the [Jasper Cost Index](./cost-database#the-jasper-cost-index) at the estimate date to its value at the correlation's base year. Correlations with different base years (2001, 2006) are brought to the same basis before assembly.

## Location factors

Location is a composed model, not a country constant:

```
factor = 0.6 · (material_index · fx · freight_duty) + 0.4 · (labor_rate / productivity)
```

| Region | Factor | Basis |
|--------|--------|-------|
| US-GC (Gulf Coast) | 1.000 | definitional base |
| US-MW (Midwest) | 1.032 | representative drivers |
| EU | 1.176 | real ECB FX (1.082) + representative labor/freight |

Because the factor is composed from drivers, editing a single driver (say, FX) propagates correctly instead of requiring a new hand-tuned constant.

## Contingency

Applied by AACE class on located bare-module cost: Class 5 → 18%, Class 4 → 15% (Turton grassroots recommendation). Selecting the class in the UI changes only this step.

## OPEX and revenue

`estimate_project` composes the operating side from annual flows × effective prices:

| Item | Formula |
|------|---------|
| Feed cost /yr | Σ annual kg × chemical price (override-aware) |
| Utility cost /yr | Σ annual kWh / GJ × utility price; steam uses a two-factor model that re-prices when gas price changes |
| Revenue /yr | Σ product annual kg × price, for Sinks marked `product` |
| Gross margin /yr | revenue − feeds − utilities (sign reported, never assumed) |

Any item that can't be priced becomes a gap row, excluded from totals and listed in the result.

## Multi-source blending

Where two independent sources cover the same equipment class (heat exchangers, compressors, vessels, pumps), the engine can return a blended estimate with the inter-source range — a built-in honesty check on the single-source numbers. Observed spreads: 3.3% (heat exchangers) to ~146% (vessels, method-sensitive), which empirically justifies the Class 4–5 accuracy band.
