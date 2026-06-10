---
sidebar_position: 4
---

# Data Sources & Licensing

Every value in the cost database traces to one of eleven registered sources. The registry itself is queryable (`GET /api/tea/sources`) and license discipline is enforced by tests: no proprietary cost feed or licensed index series can be stored.

## The licensing rule

Cost engineering data is a licensing minefield: the standard textbooks are copyrighted, CEPCI is a paid Chemical Engineering feature, and commercial price feeds (Richardson, ICIS, IHS) cannot be redistributed. Jasper's rule:

> Coefficients enter the database **only** via open-source implementations or public government datasets, and every source's license is recorded.

This is why some source names look indirect — the provenance chain *is* the point.

## All eleven sources

| Source | What it provides | License |
|--------|-----------------|---------|
| `turton` | Turton et al. purchased-cost coefficients, bare-module factors, material factors | published coefficients via an MIT-licensed port (see below) |
| `idaes-sslw` | Seider/SSLW correlations from IDAES-PSE (`SSLW.py`) | BSD-3 (US DOE labs) |
| `bls-ppi-ces` | The Jasper Cost Index inputs: metals PPI, machinery PPI, construction wages | US Gov public domain |
| `eia-public` | Utility prices: electricity, natural gas; two-factor steam | US Gov public domain |
| `literature-prices` | Representative chemical prices from published TEAs | flagged representative |
| `eurostat-ecb` | EUR/USD reference rate, EU labor cost index | Eurostat / ECB public |
| `us-irs-statutory` | US federal corporate tax rate (21%) | US Gov public domain |
| `turton-grassroots-contingency` | Contingency by AACE class | concept attribution |
| `jasper-base` | US-GC base-region definition (all drivers ≡ 1.0) | internal, definitional |
| `location-us-mw` | US Midwest location drivers | flagged representative |
| `jasper-mapping` | Unit-type → correlation mapping (30 rows) | internal, documented |

## About `turton`

Turton et al., *Analysis, Synthesis and Design of Chemical Processes* (4th ed., Appendix A) is the de-facto standard source for module-costing coefficients — but the book is copyrighted, so Jasper does not transcribe it. The coefficients were ingested from an MIT-licensed open-source implementation that republishes them; the registry records the citation:

> Turton et al., Analysis, Synthesis and Design of Chemical Processes, 4th ed., App. A.

The same pattern applies to `idaes-sslw`: Seider et al.'s correlations arrive via the BSD-licensed IDAES-PSE codebase, not the textbook.

## What is deliberately absent

- **CEPCI values** — never stored. The [Jasper Cost Index](./cost-database#the-jasper-cost-index) replaces it from public BLS data and is validated against it only in tests.
- **Richardson / ICIS / IHS or any commercial feed** — a test fails if such a source is ever registered.
- **Invented numbers** — equipment without an open-licensed correlation is gap-logged rather than given a made-up cost.

## Representative vs. measured

Two source classes are honest approximations and flagged as such everywhere they're used:

- `literature-prices` — chemical prices are representative published values, not live quotes. Estimates that use them say so, and per-project [overrides](./prices-and-overrides) replace them with your contract prices.
- `location-us-mw` — driver values are representative differentials vs. US-GC; the *model* (composed drivers) is real, the magnitudes are study-grade.
