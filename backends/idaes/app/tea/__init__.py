"""
Jasper TEA cost database.

Provenance-first cost data (equipment correlations, factors, prices, index,
overrides) served from Postgres. Repo is the source of truth for seed defaults;
the DB is the serving layer. See docs/cost-db/ for the build plan and guardrails.

Guardrails enforced at the DB layer (see models.py + the initial migration):
  - every fact row references a `source` and carries a `basis_date` (NOT NULL)
  - units are validated against an allowlist (FK to `units`), never implied
  - the `overrides` table is append-only (UPDATE/DELETE blocked by trigger)
"""
