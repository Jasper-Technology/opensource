---
sidebar_position: 2
---

# Sizing Methods

The correlations behind each sizing basis. All are standard preliminary-design methods (Towler & Sinnott, GPSA, Seider et al.), chosen to match the AACE Class 4–5 accuracy of the [economics engine](../economics/overview).

## Heat exchangers and coolers (area)

Area from the log-mean temperature difference (LMTD) method:

```
A = Q / (U · LMTD)

LMTD = (ΔT₁ − ΔT₂) / ln(ΔT₁ / ΔT₂)
  ΔT₁ = T_hot,in − T_cold,out
  ΔT₂ = T_hot,out − T_cold,in
```

- **Two-sided exchangers** (process–process): hottest inlet is assigned to the hot side, coldest to the cold side. U = 300 W/m²·K (liquid–liquid).
- **Coolers** (one process side): sized against cooling water at 30 → 40 °C. U = 600 W/m²·K (process–cooling water).
- A temperature cross (LMTD ≤ 0) is clamped to a 5 K minimum so the size stays finite; the clamp is recorded as an assumption.

Default U values by service (Towler & Sinnott, Table 19.1):

| Service | U (W/m²·K) |
|---------|-----------|
| Liquid–liquid | 300 |
| Gas–gas | 30 |
| Condenser (organic vapor) | 700 |
| Reboiler / vaporizer | 800 |
| Process–cooling water | 600 |
| Process–steam | 850 |

## Pumps, compressors, expanders (power)

Sized directly from the simulated mechanical work:

```
power = |work|   (kW)
```

No correlation is involved — the simulation engine already computed the thermodynamic work for the unit's actual path.

## Heaters (heat duty)

Sized directly from the simulated duty, `heat_duty = |duty|` in kW. The economics engine converts to BTU/hr (× 3412.142) where its fired-heater correlation requires it.

## Flash drums and separators (volume)

Two paths, selected by the phase split at the outlets:

### Vapor–liquid separators (Souders–Brown)

Used when the vessel has a vapor outlet with vapor fraction > 0.05:

```
u_max = K · √((ρ_L − ρ_V) / ρ_V)        K = 0.107 m/s
D     = √(4·Q̇_V / (π·u_max))            vapor disengagement diameter
H     = max(V_holdup / (π/4·D²), 1.5·D)  liquid holdup + disengagement space
V     = π/4 · D² · H
```

The K value assumes a vertical drum with a mesh mist eliminator (GPSA). Liquid holdup uses a 5-minute residence time at 50% fill.

### Liquid-dominated drums (residence time)

Used when there is no significant vapor outlet (surge and reflux drums):

```
V = max(Q̇_L · τ / f_fill, 0.1 m³)       τ = 5 min, f_fill = 0.5
D = ∛(4·V / (3π))                        L/D = 3
```

## Columns (volume, diameter, stages)

Distillation, absorber, and stripper shells are sized with the Fair flooding correlation (Towler & Sinnott eq. 17.34 fit):

```
u_flood  = (−0.171·lt² + 0.27·lt − 0.047) · √((ρ_L − ρ_V) / ρ_V)
u_design = 0.8 · u_flood                  design at 80% of flooding
A_net    = Q̇_V / u_design
A_column = A_net / 0.88                   ~12% downcomer allowance
D        = √(4·A_column / π)
H        = n_stages · lt · 1.15           lt = 0.6 m tray spacing
V        = π/4 · D² · H
```

- **Internal vapor traffic**: when the reflux ratio is available (Rigorous columns), internal vapor ≈ overhead vapor × (1 + R). Otherwise the overhead flow is used and the approximation is recorded.
- **Stage count**: rigorous engines report actual stages. When only a minimum stage count is available, the fallback N_actual ≈ 2 · N_min (Fenske factor) is used and flagged so you can override it.

The shell volume, diameter, and stage count feed the economics engine separately — the shell is costed as a vessel and the internals (trays or packing) as their own item. See [Costing Methods](../economics/costing-methods).

## Reactors (volume)

Reactors size by residence time with phase-dependent defaults — covered in depth in [Reactor Sizing](./reactors).

## Custom units (delegate)

`CustomUnit` nodes inherit the sizing of their base type, or carry an agent-defined sizing formula. See [Custom Sizing](./custom-sizing).
