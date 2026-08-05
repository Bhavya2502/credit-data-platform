# Credit Data Platform

An internal, cloud-hosted repository of credit-risk data — global and India — systematically
organised, continuously refreshed, and including derived datasets that no one else publishes.

**Status:** Phase 0 — Foundations. Research complete (109 verified sources); platform being stood up.

---

## Start here

| If you want to… | Read |
|---|---|
| Understand the whole plan | [`docs/PLATFORM_PLAN.md`](docs/PLATFORM_PLAN.md) |
| Set up the accounts and tools | [`docs/SETUP_GUIDE.md`](docs/SETUP_GUIDE.md) |
| Know what data exists and where | [`docs/credit_risk_data_landscape.md`](docs/credit_risk_data_landscape.md) |
| Track progress, tick things off | [`credit_risk_data_tracker.xlsx`](credit_risk_data_tracker.xlsx) |
| Know why something was built this way | [`docs/DECISIONS.md`](docs/DECISIONS.md) |
| Work on this with AI assistance | [`CLAUDE.md`](CLAUDE.md) |

## What makes this different

Anyone can download a public dataset. The value here is **assembly**: six datasets that exist only
as thousands of unparsed PDF pages and scattered disclosures.

- **D1** India corporate workout-LGD panel — ~1,400 named insolvency resolutions with claims,
  recoveries and durations, from 35+ quarterly IBBI newsletters
- **D2** India rating-migration & default corpus — issuer-level histories across all 7 credit
  rating agencies, plus daily exchange feeds
- **D3** India NBFC ECL panel — stage-wise exposures, coverage and disclosed PD/LGD assumptions,
  ~50 lenders × 7 years of annual reports
- **D4** Global IRB parameter panel — bank-level PD/LGD/RW by exposure class
- **D5** India district risk surface — district NPAs from state banking committee minutes
- **D6** Harmonised global recovery panel — recovery rates on one definition across jurisdictions

Plus registries of regulatory parameters, default definitions and disclosed model assumptions —
structured knowledge that today exists only as prose scattered across rulebooks.

## Why now

RBI's Expected Credit Loss Directions take effect **1 April 2027**. Every Indian commercial bank
must build PD, LGD and EAD models, and none has an internal-ratings legacy to build them from.
The data gap is structural, and it is about to become expensive for a lot of institutions.

## Architecture in one picture

```
sources → BRONZE (raw, immutable) → SILVER (parsed, typed) → GOLD (analysis-ready) → query
                                  ↳ CATALOG (registry · lineage · QA · provenance)
```

Cloud-only. Nothing of substance lives on a local machine.
