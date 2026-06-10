---
sidebar_position: 4
---

# Custom Sizing

Custom units can carry their own sizing definition, so novel equipment (electrolyzers, membrane skids, proprietary reactors) gets sized and costed instead of falling out of the economics.

## Two modes

A `CustomUnit`'s sizing spec declares a size quantity (`area`, `volume`, `power`, or `heat_duty`) and one of two methods:

- **`inherit`** — reuse the built-in correlation of the unit's base type. A custom CSTR variant inherits residence-time sizing from RCSTR.
- **`formula`** — a sandboxed arithmetic expression evaluated against the unit's simulation results.

## Formula variables

| Variable | Meaning | Unit |
|----------|---------|------|
| `duty` | Heat duty (signed: + heating, − cooling) | kW |
| `work` | Mechanical work / power | kW |
| `flow_mol` | Feed molar flow | kmol/h |
| `flow_vol` | Feed volumetric flow | m³/s |
| `density_l` | Liquid outlet (or feed) density | kg/m³ |
| `density_v` | Vapor outlet density | kg/m³ |
| `T` | Feed temperature | K |
| `P` | Feed pressure | bar |

Plus any named constants the spec defines (e.g. `tau: 7200`). Example — a reactor sized by an explicit residence time:

```
expression: "flow_vol * tau"
variables:  { tau: 7200 }
sizeQuantity: volume
```

When a formula yields a volume, diameter and length are derived with the standard L/D = 3 cylinder so the result stays consistent with the vessel cost correlations.

## The expression sandbox

Formulas are evaluated by a purpose-built parser — never JavaScript `eval`. The grammar allows:

- Numbers, the declared variables, and the constants `pi`, `e`
- Operators `+ − * / % ^` and parentheses
- Functions: `sqrt`, `cbrt`, `abs`, `exp`, `ln`, `log10`, `pow`, `min`, `max`

Anything else — property access, assignment, unknown identifiers — is rejected. Formulas are validated when the unit is proposed; a formula that fails validation falls back to the base type's sizing and surfaces a warning.

## Provenance

Agent- or user-defined sizing is always distinguishable from built-in correlations. Every custom-sized result records:

- the flag `agent-defined sizing (not a validated built-in)`
- the literal formula used
- the cited source from the spec, if provided

so a reviewer can audit exactly where a size came from.
