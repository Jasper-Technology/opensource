---
sidebar_position: 6
---

# Economics API

The cost database is served by the IDAES backend under `/api/tea/*`. Routes mount only when `DATABASE_URL` is configured; the backend boots stateless without it. Read routes are open; the override write route requires the backend API key.

## Endpoints

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/api/tea/health` | DB liveness + correlation count |
| POST | `/api/tea/cost-equipment` | Cost one piece of equipment by type/subtype/material/size/pressure |
| POST | `/api/tea/cost-unit` | Cost by Jasper unit type (resolves via the unit-cost map) |
| POST | `/api/tea/cost-column` | Column: shell + internals (trays or packing) |
| GET | `/api/tea/cost-blended` | Multi-source blended estimate with inter-source range |
| POST | `/api/tea/estimate` | Full project: equipment list + feeds + products + utilities → CAPEX, OPEX, revenue, margin, gaps |
| GET | `/api/tea/coverage` | Unit-type coverage report (23/23 cost-bearing covered) |
| GET | `/api/tea/sources` | The queryable source registry with licenses |
| GET | `/api/tea/price/chemical` | Effective chemical price (override-aware) |
| GET | `/api/tea/price/utility` | Effective utility price (override-aware) |
| POST | `/api/tea/override` | Record a price override event (API-key gated) |
| GET | `/api/tea/overrides` | Query the override event log |

## Example: cost one unit

```bash
curl -X POST $BACKEND/api/tea/cost-equipment \
  -H 'Content-Type: application/json' \
  -d '{
    "equipment_type": "HeatExchanger",
    "subtype": "FloatingHead",
    "material": "CarbonSteel",
    "size": 100,
    "pressure": 25,
    "region": "US-GC",
    "aace_class": 5
  }'
```

Response (abridged):

```json
{
  "purchased_cost": 126141,
  "bare_module_cost": 444734,
  "total_module_cost": 524786,
  "Fp": 1.137, "Fm": 1.0,
  "accuracy_class": "AACE Class 4-5 (+/-30-40%)",
  "in_range": true,
  "provenance": {
    "correlation": "turton",
    "cost_index": "bls-ppi-ces",
    "contingency": "turton-grassroots-contingency"
  }
}
```

## Example: full estimate

`POST /api/tea/estimate` takes the flowsheet's sized equipment plus annual feed/product/utility flows and returns totals, a per-item breakdown with provenance, and a `gaps` array for anything that couldn't be costed (excluded from totals, never invented). Common parameters: `region` (`US-GC` | `US-MW` | `EU`), `aace_class` (`5` | `4`), and optional `project` / `scenario` refs for override resolution.
