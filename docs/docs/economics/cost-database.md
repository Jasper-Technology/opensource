---
sidebar_position: 2
---

# The Cost Database

The economics engine is backed by a relational cost database — not constants in code. The database enforces provenance at the schema level and is fully open source: seed data and the loader live in this repo under `backends/cost-db/`, with the schema migrations in `backends/idaes/alembic/`.

## Design principles

- **Provenance is a constraint, not a convention.** Every fact row has a `source_id` foreign key and a `basis_date`, both `NOT NULL` at the database layer. An unsourced insert fails.
- **Units are validated.** Size and price units reference an allowlisted `units` table — a correlation can't silently mix m² and ft².
- **Overrides are append-only.** Price overrides are events in a log; a database trigger blocks `UPDATE`/`DELETE`, so the audit trail can't be rewritten.
- **License-clean by construction.** Coefficients enter only via open-source implementations or public datasets. No proprietary cost feeds (Richardson, ICIS, IHS) and no licensed index series (CEPCI) are stored — see [Data Sources & Licensing](./data-sources).
- **The repo is the source of truth.** Seed data is versioned JSON loaded by an idempotent script; the database is a serving layer that can be rebuilt from git at any time.

## Tables

| Table | Holds |
|-------|-------|
| `sources` | One row per data source: type, license, URL, citation, access date |
| `units` | Allowlist of valid unit symbols with dimensions |
| `equipment_correlations` | Cost correlations: functional form, coefficients, size range, base index, bare-module factors, pressure model |
| `material_factors` | Material-of-construction multipliers (27-entry matrix) |
| `chemicals` | Chemical identities (CAS-keyed, linked to the component database) |
| `chemical_prices` | Dated chemical prices by region |
| `utilities` | Utility prices (electricity, gas, steam) incl. two-factor steam model |
| `location_drivers` | Composed location factors: labor rate, productivity, material index, FX, freight/duty |
| `economic_factors` | Contingency by AACE class, tax rate, discount rate |
| `cost_index` | The Jasper Cost Index: 304 monthly points, 2001 → today |
| `unit_cost_map` | Maps all 30 Jasper unit types to correlations (23 cost-bearing, 7 non-physical) |
| `overrides` | Append-only price/factor override events with scope and reason |

## Coverage

All 23 cost-bearing unit types in Jasper's catalog are covered by sourced correlations — 0 silent gaps. The 7 remaining types (Feed, Sink, Mixer, Splitter, Valve, PipeSegment, TextBox) carry no capital cost by definition. A queryable coverage report is served at `GET /api/tea/coverage`.

## The Jasper Cost Index

Cost correlations are published against old base years (Turton: 2001, Seider: 2006), so costs must be escalated to today. Licensed indices like CEPCI can't be redistributed, so Jasper builds its own from public US Bureau of Labor Statistics series:

```
Jasper(t) = 100 · [ 0.36 · WPU10(t)/WPU10(2001-01)      (metals PPI)
                  + 0.25 · WPU11(t)/WPU11(2001-01)      (machinery PPI)
                  + 0.39 · CES2000000008(t)/CES(2001-01) (construction wages) ]
```

304 monthly points from 2001-01 (= 100) to today, rebuilt from BLS bulk files by `cost-db/build_index.py`. Validation: the 2001 → 2024 escalation ratio matches CEPCI's within **0.15%** — CEPCI itself is used only as a test-time sanity constant, never stored.

## Validation

The database ships with a benchmark suite (85 tests in CI):

- **Per-unit exact match** against the upstream open-source implementations the coefficients came from — including building and solving a real IDAES costing block and reproducing its result to 0.000%.
- **HDA process benchmark** (toluene hydrodealkylation, ~70 kt/yr benzene): total CAPEX lands inside the independently cited literature band.
- **Capacity scaling**: doubling capacity raises cost by 1.71× (exponent 0.78), inside the 0.6–0.9 textbook range.
- **Corrupt-coefficient guards**: a tampered coefficient fails the benchmark instead of shipping a wrong number.

## Running it yourself

```bash
# Postgres + schema
export DATABASE_URL=postgresql+psycopg://costdb:costdb@localhost:5432/costdb
alembic upgrade head            # from backends/idaes/

# seed (idempotent — truncates and reloads fact tables)
python cost-db/load.py

# optional: rebuild the cost index from current BLS data
python cost-db/build_index.py
```

The IDAES backend mounts the `/api/tea/*` routes automatically when `DATABASE_URL` is configured, and boots stateless (simulation only) when it isn't.
