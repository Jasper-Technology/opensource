---
sidebar_position: 5
---

# Prices & Overrides

Operating costs are only as good as their prices. Jasper ships honest defaults and an append-only override system for replacing them with your own.

## Default prices

| Category | Source | Notes |
|----------|--------|-------|
| Electricity | EIA (US industrial average) | real public data |
| Natural gas | EIA | real public data |
| Steam | two-factor model | capital component + energy component coupled to the gas price — re-prices automatically if you override gas |
| Chemicals | published TEA literature | representative values (e.g. benzene ≈ $1.10/kg); flagged in every estimate that uses them |

Chemical prices are currently sourced for the US-GC region. Other regions scale CAPEX via location factors but may show price gaps until overridden.

## Overrides

An override is an event, not an edit:

- **Append-only.** Overrides are recorded in an event log with the new value, reason, context, and actor. A database trigger blocks updates and deletes — the audit trail is immutable.
- **Scoped.** Each override targets a scope: `scenario`, `project`, or `global`.
- **Newest wins within a scope; the most specific scope wins overall:**

```
scenario  →  project  →  global  →  default (sourced seed value)
```

A scenario-level benzene price beats the project-level one, which beats a global one, which beats the literature default. Every resolved price reports which layer it came from (`default` or `override` + scope), so estimates remain auditable.

## API

```
POST /api/tea/override          record an override event (API-key gated)
GET  /api/tea/overrides         query the event log
GET  /api/tea/price/chemical    effective price for a CAS number (override-aware)
GET  /api/tea/price/utility     effective utility price (override-aware)
```

`estimate_project` resolves all feed, product, and utility prices through the same chain — pass a project/scenario reference and the whole estimate re-prices consistently.
