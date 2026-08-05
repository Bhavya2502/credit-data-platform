# CLAUDE.md — Credit Data Platform

Operating manual for AI sessions on this project. Read this first, every session.

---

## What this is

We are building **an internal credit-risk data platform**: a systematically organised,
segmented, continuously-updated repository of every obtainable credit-risk dataset —
global and India — plus **derived datasets that nobody else publishes** (our differentiator).

- **Stage:** internal prototype. Not public, not a product yet.
- **Owner:** Bhavya (non-technical). **Every technical instruction must be step-by-step,
  with options explained in plain language and a clear recommendation.** Never assume
  command-line fluency, never leave a step implicit.
- **Storage:** cloud-only. Nothing of substance lives on the local machine.
- **Downstream:** the same data will later feed other domain tasks (modelling, analytics,
  training material). Design for reuse, not for one-off analysis.

## Current phase

**Phase 0 — Foundations.** Research is complete (see `docs/credit_risk_data_landscape.md`,
109 verified sources). Platform is being stood up. No pipelines built yet.

Update this line whenever the phase changes.

---

## Where things live

| Path | What |
|---|---|
| `CLAUDE.md` | This file — operating manual |
| `docs/PLATFORM_PLAN.md` | The blueprint: architecture, stack, coverage model, roadmap |
| `docs/DECISIONS.md` | Architecture Decision Record + open decisions awaiting the owner |
| `docs/credit_risk_data_landscape.md` | The research: 109 verified sources, v2 |
| `credit_risk_data_tracker.xlsx` | Living checklist — sources, pipelines, prototypes, anchors |
| `config/sources/*.yaml` | One declarative config per source (the source registry) |
| `src/` | Connector, extractor, transform code |
| `.github/workflows/` | Scheduled pipeline runs |

The landscape doc and the tracker are the **source of record for what exists**. The plan is the
source of record for **how we build**. Don't re-research what the landscape doc already verified —
check it first.

---

## Architecture in brief

Medallion pattern, cloud-native:

```
BRONZE  raw as-fetched files, immutable, with a manifest (object storage)
   ↓
SILVER  parsed, typed, normalised tables (Parquet)
   ↓
GOLD    analysis-ready panels — including our differentiated datasets
   ↓
CATALOG source registry · load log · lineage · QA results
```

**Never mutate bronze.** Every fetch writes a new timestamped object plus a manifest row
(source_id, fetch time, URL, bytes, checksum, HTTP status). Reprocessing always replays from bronze.

---

## Conventions

- **Source IDs**: `S-001`…`S-nnn`, matching `1_Sources` in the tracker. Every artefact carries its source_id.
- **Config-first**: a new source is a YAML file in `config/sources/`, not bespoke code. Code lives in
  reusable connectors keyed by ingestion archetype (see plan §6).
- **Table naming**: `<layer>.<domain>_<grain>` — e.g. `silver.ibbi_cirp_cases`,
  `gold.india_corporate_lgd_panel`, `gold.anchor_series`.
- **Every number carries provenance**: source_id, source URL, as-of date, fetch timestamp,
  page/table reference where extracted from a document. No orphan numbers, ever.
- **Schema basis**: AnaCredit shape for facility-level, EBA NPL/openNPL for defaulted-asset and
  recovery data, long format (`source, segment, metric, period, value, asof`) for aggregates.
  Don't invent schemas — map to these.
- **Dates**: ISO-8601. Indian fiscal years written explicitly (`FY2026` = year ended 31 Mar 2026).
- **Currency**: store native + a converted column; never silently convert. Indian figures in
  crore/lakh must be normalised to absolute INR at parse time, with the original string retained.

## Adding a new source — standard workflow

1. Confirm it's in the tracker (`1_Sources`); if not, add a row first.
2. Classify its **ingestion archetype** (plan §6) and **governance tier** (plan §7).
3. Write `config/sources/S-nnn_<slug>.yaml` — URL patterns, schedule, parser, target table, tier.
4. Run the matching connector against it; land bronze.
5. Write/extend the parser to silver; add schema validation.
6. Add a **reconciliation check** against a published figure (tracker `6_Anchors` where possible).
7. Register in the catalog; set the refresh schedule.
8. Update the tracker row status.

## Source governance tiers (applies to every source)

- **Tier 1 — Open**: government, regulator, open-licence data. Fetch freely; be polite (rate limits, identified UA).
- **Tier 2 — Public but restricted**: public web content under ToS, copyrighted reports.
  Fetch for internal use; **record provenance; never republish source tables verbatim**;
  keep extraction to facts/figures rather than wholesale copies.
- **Tier 3 — Restricted**: personal/individual credit data, paywalled vendor content, anything
  requiring credentials we don't hold. **Do not ingest.** Our target datasets are entity-level or
  aggregate, so this tier is designed out, not worked around. Flag and escalate to the owner
  rather than improvising.

Tier is a required field in every source config. When in doubt, tier up and ask.

## Operating rules

**Always**
- Be polite to sources: rate-limit, back off on errors, set a real User-Agent, cache aggressively.
  This is a **reliability** requirement — banned IPs break pipelines — not merely an etiquette one.
- Make pipelines idempotent and resumable. Assume every run can fail halfway.
- Validate against a published total before declaring a dataset loaded.
- Prefer a boring, managed, cheap service over self-hosting.
- Explain any technical step in plain language, give options, then recommend one.

**Never**
- Store credentials in code or config. Secrets live in the secret store only (plan §5).
- Hard-code file paths to the local machine.
- Ship extracted numbers without provenance.
- Ingest Tier 3 data.
- Silently drop rows in a parse — log and surface every rejection.

---

## Tech stack (decided — ADR-007)

| Layer | Service | Notes |
|---|---|---|
| Code, scheduling, secrets | **GitHub** (private repo) + Actions + Secrets | Pipelines run here, not locally |
| Bronze object storage | **Cloudflare R2** | Bucket `credit-data-lake`; zero egress fees |
| Silver/gold analytical store | **MotherDuck** (DuckDB) | Also the owner's query surface |
| LLM extraction | **OpenRouter** (340+ models) | Last-resort tier for irregular PDFs, always validated |
| Quality | Pandera schemas + custom reconciliation | A dataset isn't "loaded" until it reconciles |

Deferred: Neon Postgres (only if DuckDB proves awkward for entity crosswalks); dbt (once silver
exceeds ~20 tables); paid scraping services (only if a target genuinely blocks us).

**Budget rule (ADR-008):** default to free tiers. Propose any spend individually — cost, what it
buys, and the free alternative — before committing. Never incur cost silently.

**Working mode (ADR-010):** owner does account creation and anything needing their password or
card; Claude writes/runs/debugs all code and reports results. Credentials never pass through chat —
they go from the issuing service straight into GitHub Secrets.

The single biggest engineering challenge is PDF/document extraction for the India datasets
(IBBI newsletters, NBFC annual-report ECL notes, bureau reports, SLBC minutes). Deterministic
tools first, LLM vision last, reconciliation always.

## Key project facts worth remembering

- The moat is **derived datasets**, not raw collection: IBBI case-level corporate LGD,
  India rating/default corpus, NBFC ECL panel, EU IRB parameter panel, India district-risk panel,
  and a regulatory-parameter registry. See plan §2.2.
- **RBI ECL Directions take effect 1 Apr 2027** — every Indian commercial bank needs PD/LGD/EAD
  models and none has an IRB legacy. That deadline sets our India priority order.
- India has almost no public loan-level data; the platform's India value comes from
  **assembling** aggregates and document-locked micro data that nobody has stitched together.
- `rbidocs.rbi.org.in` is CAPTCHA-gated; CIBIL blocks bots; NSE needs cookie/UA handling.
  These are known engineering constraints, documented per-source in the tracker.
