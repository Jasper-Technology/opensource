---
sidebar_position: 1
---

# Economics Overview

Jasper turns a converged flowsheet into a provenance-tracked CAPEX + OPEX estimate. Every number in the result traces back to a cited source with a basis date — the engine never invents a cost.

## The pipeline

```
Converged flowsheet
        ▼
Equipment sizing            (area, power, volume per unit — see Equipment Sizing)
        ▼
Cost database lookup        (correlation + material factor, by unit type)
        ▼
Purchased cost              (at the correlation's base year)
        ▼
Bare-module cost            (installation factors)
        ▼
Escalation                  (Jasper Cost Index, monthly 2001 → today)
        ▼
Location factor             (US-GC base · US-MW · EU)
        ▼
Contingency                 (by AACE class)
        ▼
CAPEX  +  OPEX (feeds, utilities) − revenue (products)
```

Each step's math is documented in [Costing Methods](./costing-methods); the data layer behind it in [The Cost Database](./cost-database).

## Accuracy: AACE Class 4–5

Every result is stamped `AACE Class 4-5 (+/-30-40%)`. This is a *feasibility / study-grade* estimate built from published correlations (Turton, Seider et al.) — not vendor quotes. The class is honest: where two independent sources cost the same equipment, they agree within a few percent for some classes (heat exchangers, 3.3%) and disagree by up to ~67% for others (compressors), which is exactly the band Class 4–5 declares.

## Honesty principles

- **Provenance on every value.** Each cost carries the source of its correlation, material factor, escalation index, and contingency. Sources are listed in [Data Sources & Licensing](./data-sources).
- **Gaps, not guesses.** Anything that can't be costed (missing correlation, unpriced chemical) becomes a gap row — visible, excluded from totals, never silently filled.
- **Representative prices are flagged.** Chemical prices are literature values until you override them; the estimate says so whenever they're used.
- **Margins are computed, not promised.** Revenue − feeds − utilities can be negative; the engine reports what the numbers say.

## Where it lives in this repo

- **Engine** — `backends/idaes/app/tea/` (`models.py` schema, `costing.py` math, `repository.py` query API), served under `/api/tea/*` by the IDAES backend when `DATABASE_URL` is set.
- **Data** — `backends/cost-db/`: versioned JSON seeds, the idempotent loader (`load.py`), and the cost-index builder (`build_index.py`). The repo is the source of truth; the database is a serving layer.
- **Tests** — `backends/idaes/tests/test_cost_db_*.py`: 85 tests covering schema guarantees, per-unit benchmark matches against upstream implementations, and an end-to-end HDA process benchmark.

The hosted Jasper editor ([jaspertech.org](https://jaspertech.org)) surfaces this engine as its Economics panel; everything it computes is reproducible from this repo. Annualization uses the project's operating hours (default 8000 h/yr).

## Prices you can override

Chemical and utility prices resolve through an append-only override system with scope precedence (scenario → project → global → default), so you can pin contract prices without losing the audit trail. See [Prices & Overrides](./prices-and-overrides).
