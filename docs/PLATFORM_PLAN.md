# Credit Data Platform — Blueprint

_v1.0 · 30 July 2026 · Internal prototype_

---

## 0. Executive summary

**What:** A cloud-hosted, systematically organised repository of every obtainable credit-risk
dataset — global and India — continuously refreshed, plus derived datasets that no one else
publishes.

**Why it can work:** The research phase established that credit-risk data is not scarce so much as
**scattered, undocumented, and locked inside documents**. 109 verified sources exist across
regulators, exchanges, bureaus, insolvency registries and company filings. Nobody has assembled
them into one queryable, versioned, refreshed store — and several genuinely valuable datasets
(India corporate workout LGD, India rating-migration history, the NBFC ECL panel) exist only as
thousands of PDF pages that no one has ever parsed.

**The differentiator is assembly, not access.** Anyone can download an IBBI newsletter. Nobody has
all 35+ of them parsed into a company-level recovery dataset with consistent fields, reconciled
totals and quarterly refresh.

**Shape of the build:** three data layers (raw → normalised → analysis-ready), eight reusable
ingestion patterns covering all 109 sources, a config-driven source registry so adding source #110
is a YAML file rather than a project, and scheduled refresh with automated reconciliation.

**Cost:** roughly **$0–40/month** through Phase 1, rising to **~$150–350/month** at full operation.
The expensive parts of this domain are the vendor licences we're deliberately not buying.

**Timeline:** Phase 0 foundations in week 1; first differentiated dataset (IBBI LGD panel) inside
a month; India crown jewels complete by ~month 3; broad coverage by ~month 6.

---

## 1. Vision, scope and success criteria

### 1.1 Vision

> The single place where any credit-risk question can be answered with real data — every
> portfolio, every geography, every risk parameter — with provenance, history and refresh.

### 1.2 In scope (now)

- Ingestion, normalisation, storage and refresh of credit-risk data: micro (loan/facility),
  entity (obligor/issuer), institution, pool, sector, geography, system, and scenario levels.
- Derived/assembled datasets built from those inputs.
- Internal use only: prototypes, modelling, analysis, teaching material.

### 1.3 Out of scope (for now, deliberately)

- Public product, API, or commercial distribution — changes the licensing calculus entirely; revisit later.
- Modelling itself. The platform *serves* models; it isn't the models. (Prototype list lives in the tracker.)
- Real-time/streaming. Credit data moves monthly-to-annually; batch is correct.
- Personal/individual-level credit data. Never in scope — see §7.

### 1.4 Success criteria

| # | Criterion | Target |
|---|---|---|
| 1 | Source coverage | 109 tracked → 100% of P1 sources live by month 3; 300+ sources by month 9 |
| 2 | Differentiated datasets | 6 assembled datasets live, refreshed, reconciled |
| 3 | Freshness | Every source refreshed within one cycle of its publication cadence |
| 4 | Reconciliation | Every gold dataset ties to a published control total, automatically checked |
| 5 | Provenance | 100% of stored figures carry source_id, URL, as-of date, extraction reference |
| 6 | Reproducibility | Any table can be rebuilt from bronze with one command |
| 7 | Owner autonomy | The owner can trigger a refresh, see status, and query data without writing code |

Criterion 7 matters as much as the rest: a platform only its builder can operate is a liability.

---

## 2. What we are building

### 2.1 Three product layers

**Layer A — The Mirror.** Faithful, refreshed copies of everything public: regulator statistics,
loan-level datasets, rating histories, bureau publications, scenario files. Value = one place,
one schema, one refresh, full history.

**Layer B — The Assembly.** Derived datasets built by stitching, parsing and normalising Layer A.
This is the moat (§2.2).

**Layer C — The Registry.** Structured knowledge *about* credit risk that exists today only as
prose scattered across rulebooks: regulatory parameters, default definitions, model assumptions
(§2.3). Genuinely novel; cheap to build once documents are being parsed anyway.

### 2.2 The differentiated datasets (the moat)

| # | Dataset | What it is | Why nobody has it | Source |
|---|---|---|---|---|
| D1 | **India corporate workout-LGD panel** | ~1,400 named insolvency resolutions: admitted claims, liquidation & fair value, realisation, duration, sector | Locked in 35+ quarterly PDFs, never parsed | IBBI newsletters |
| D2 | **India rating-migration & default corpus** | Issuer-level rating histories + default events across all 7 CRAs, plus daily exchange feeds and bond-payment intimations | Requires stitching 7 disclosure regimes + entity resolution | CRA Annexure V/VI, NSE/BSE, CIC registries |
| D3 | **India NBFC ECL panel** | Stage-wise exposure, ECL, coverage, PD/LGD assumptions and scenario weights, ~50 lenders × 7 years | Buried in annual-report notes; needs LLM-assisted extraction | NBFC annual reports |
| D4 | **Global IRB parameter panel** | EAD-weighted PD/LGD/RW/EL by bank × exposure class × PD band | Newly machine-readable (EBA P3DH, Jan 2026); extend to UK/CH/CA/AU/JP Pillar 3 | P3DH + global Pillar 3 |
| D5 | **India district risk surface** | District-level NPA, credit by occupation and rate bucket, microfinance PAR | SLBC minutes are unindexed PDFs, one per state per quarter | SLBC + BSR-1 + MFIN/CRIF |
| D6 | **Harmonised global recovery panel** | Recovery rates on one definition across jurisdictions: India (IBBI), Italy (BdI), EM (GEMs), US (GSE/ABS), cross-country (Doing Business) | Definitions differ; harmonisation is the work | Multi-source |

### 2.3 The registry datasets (Layer C — novel, cheap, useful)

| # | Registry | Content |
|---|---|---|
| R1 | **Regulatory parameter registry** | Every published floor, risk weight, LGD floor, CCF, haircut, provisioning rate — by jurisdiction, instrument, date-in-force (e.g. RBI Stage-1 0.40% / Stage-2 5%, Basel SA weights, IRACP norms) |
| R2 | **Default-definition registry** | How "default" is defined per dataset/jurisdiction (90 dpd, IRACP, IBC admission, rating D, charge-off, contractual RoD) — essential for cross-dataset comparability |
| R3 | **Model-assumption registry** | Disclosed ECL model choices per lender: scenario weights, macro variables, SICR triggers, LGD floors, PD approaches |
| R4 | **Source & release calendar** | Every source's publication cadence and expected next release — drives scheduling and freshness alerts |

R1 and R2 are the ones that make everything else comparable. They should be built early, not late.

### 2.4 What we serve

- **Query access** — SQL over gold tables.
- **File extracts** — Parquet/CSV pulls for modelling.
- **A browsable catalogue** — what exists, coverage range, last refresh, provenance.
- **Freshness/health dashboard** — what ran, what broke, what's stale.

---

## 3. Coverage model — how "exhaustive" gets operationalised

Exhaustive is a claim you can only make against a defined space. Ours has six dimensions;
coverage is the cross-product, and gaps become a visible backlog rather than an unknown.

| Dimension | Values |
|---|---|
| **Geography** | India · US · EU-27 · UK · then EM tier-1 (Brazil, Mexico, Indonesia, Turkey, South Africa, Philippines, Peru, Chile, Colombia, Nigeria, Kenya, Vietnam, Thailand, Malaysia, Egypt, Bangladesh, Pakistan, Sri Lanka) · developed Asia-Pac (Japan, Korea, Singapore, HK, Australia, NZ) · Canada, Switzerland, Gulf (UAE, Saudi) · supranational (BIS, IMF, WB, MDBs) |
| **Portfolio** | Mortgage · auto · cards · personal · student · gold · BNPL · microfinance · SME/MSME · corporate · CRE · agri · trade finance · project/infra · equipment & leasing · sovereign · FI counterparty · supply-chain finance |
| **Institution type** | Banks · NBFCs/finance cos · HFCs · credit unions/co-ops · MFIs · fintech lenders · P2P · ARCs/distressed funds · DFIs & MDBs · guarantee funds · securitisation trusts |
| **Risk parameter** | PD · LGD · EAD/CCF · EL/ECL · staging & migration · prepayment · cure · correlation/concentration · recovery timing |
| **Data layer** | Micro (loan/facility) · pool · entity/obligor · institution · sector · geography · system · scenario |
| **Time shape** | Point-in-time · panel · vintage/cohort · through-the-cycle |

**Method.** Maintain the matrix as a coverage grid; each cell is either (a) covered by source
S-nnn, (b) covered by a derived dataset, (c) known-gap with a documented reason, or (d) unexplored.
"Exhaustive" = zero cells in state (d). The research phase filled the India and global-core cells;
the EM and developed-Asia cells are largely unexplored and are the main expansion frontier.

**Expansion sequence:** India (deepest) → US/EU (richest) → UK/Canada/Australia/Japan/Switzerland
(Pillar 3 comparability) → EM tier-1 (Brazil first, as the best-organised) → long tail.

---

## 4. Data architecture

### 4.1 Layers

```
┌─ BRONZE ──────────────────────────────────────────────────────────┐
│  Raw, exactly as fetched. Immutable. Timestamped object per fetch. │
│  bronze/{source_id}/{yyyy}/{mm}/{dd}/{filename}                    │
│  + manifest row: source_id, url, fetched_at, bytes, sha256, status │
└────────────────────────────────────────────────────────────────────┘
                              ↓ parse
┌─ SILVER ──────────────────────────────────────────────────────────┐
│  Parsed, typed, normalised. One table per logical dataset.         │
│  Schema-validated. Units normalised. Provenance columns retained.  │
│  Parquet, partitioned by period.                                   │
└────────────────────────────────────────────────────────────────────┘
                              ↓ join / harmonise / derive
┌─ GOLD ────────────────────────────────────────────────────────────┐
│  Analysis-ready: the differentiated panels (D1–D6), registries     │
│  (R1–R4), and the long-format anchor store.                        │
└────────────────────────────────────────────────────────────────────┘

┌─ CATALOG (spans all layers) ──────────────────────────────────────┐
│  source_registry · load_log · lineage · qa_results · release_cal   │
└────────────────────────────────────────────────────────────────────┘
```

**Why bronze is immutable:** parsers will be wrong at first, especially on PDFs. When a parser
improves, we replay bronze rather than re-fetch — which also means a source going offline doesn't
cost us history.

### 4.2 Core schemas

Adopted from public standards rather than invented (see landscape doc §6):

- **Facility-level** → AnaCredit shape (instrument, counterparty, protection, accounting, default)
- **Defaulted assets & recoveries** → EBA NPL templates / openNPL
- **Aggregates** → long format: `source_id, segment (json), metric, period, value, unit, asof, url, extracted_from`
- **Ratings/defaults** → event tables: `entity_id, event_date, event_type, from/to, source_id`
- **Scenarios** → `scenario_id, variable, period, value, vintage, publisher`

### 4.3 Entity resolution (the hard problem)

Indian corporate work requires matching the same borrower across CRA files, exchange feeds,
IBBI cases, MCA records and defaulter registries — with inconsistent name spellings and no shared key.

Approach: a dedicated `catalog.entities` table keyed on a generated `entity_id`, with a
crosswalk table holding every observed identifier (CIN, PAN, LEI, ISIN, exchange symbol, name
variants) and a confidence score per link. Deterministic matching on hard identifiers first,
fuzzy name matching second, LLM-assisted adjudication for the residual, human review for
high-value cases. Never silently merge on a fuzzy match — record the evidence.

---

## 5. Technology stack — options and recommendation

Cloud-only, managed-service-first, minimal operations burden. Options given at every layer;
recommendation is the one I'd choose for a non-technical owner who wants reliability over control.

### 5.1 Decision table

| Layer | Options | Recommendation | Why | Cost |
|---|---|---|---|---|
| **Code & version control** | GitHub · GitLab · Bitbucket | **GitHub** | Universal, best CI, best AI-tool integration | Free |
| **Orchestration / scheduling** | GitHub Actions · Prefect Cloud · Dagster+ · Modal · Airflow (self-host) | **GitHub Actions** to start; **Prefect Cloud** if complexity grows | Scheduling lives beside code; nothing extra to run; free minutes cover us | Free → $0–20 |
| **Raw file storage (bronze)** | Cloudflare R2 · AWS S3 · Backblaze B2 · Google Cloud Storage | **Cloudflare R2** | S3-compatible, **zero egress fees** (the usual bill-shock source), simple pricing | ~$0.015/GB/mo |
| **Analytical store (silver/gold)** | MotherDuck (DuckDB) · BigQuery · Neon/Supabase (Postgres) · ClickHouse Cloud · Snowflake | **MotherDuck** for analytics + **Neon Postgres** for catalog/registry | DuckDB reads Parquet on R2 directly; Postgres suits the small relational catalog. Both have real free tiers | Free → $25–50 |
| **General web scraping** | Firecrawl · Apify · ScrapingBee · Bright Data · self-hosted Playwright | **Firecrawl** for most; **Apify** for complex/stateful crawls | Handles JS, retries, proxies; markdown output suits LLM extraction | $0–83/mo |
| **Browser automation (hard targets)** | Playwright on Actions · Browserless · Steel.dev · Browserbase | **Playwright in GitHub Actions**, escalate to **Browserbase** where blocked | Free for most; hosted only where genuinely needed | $0–39/mo |
| **PDF/table extraction** | pdfplumber+camelot · Docling · LlamaParse · Unstructured · **LLM vision via OpenRouter** | **Tiered**: pdfplumber/Docling first (free, deterministic), **OpenRouter vision models** for hard layouts | India work is PDF-dominated; deterministic first keeps cost and variance down | $0 + LLM usage |
| **LLM access** | **OpenRouter (owned)** · direct Anthropic/OpenAI/Google | **OpenRouter** | Already available; model choice per task; one bill | Usage-based |
| **Secrets** | GitHub Actions Secrets · Doppler · 1Password · Infisical | **GitHub Secrets** now; **Doppler** if it sprawls | Zero setup, encrypted, integrated | Free |
| **Data quality** | Great Expectations · Pandera · dbt tests · custom | **Pandera** (schemas) + **custom reconciliation** | Lightweight, Python-native, fits our anchor-check pattern | Free |
| **Transformation** | dbt Core · SQLMesh · plain Python/SQL | **dbt Core** once silver has >20 tables | Lineage, tests, docs for free; overkill before that | Free |
| **Catalogue/serving UI** | Streamlit Cloud · Evidence.dev · Metabase · Hex · Observable | **Streamlit Cloud** (internal browsing) | Simplest path to owner self-service | Free |
| **Monitoring/alerting** | GitHub notifications · Healthchecks.io · Sentry · email | **Healthchecks.io** + GitHub | Tells us when a scheduled job silently stops | Free |

### 5.2 The recommended stack, in one line

**GitHub (code + schedules) → Python connectors → Cloudflare R2 (bronze) → Parquet → MotherDuck
(query) + Neon (catalog) → Streamlit (browse) — with Firecrawl for scraping and OpenRouter for
document extraction.**

Everything is managed. Nothing runs on your machine. Total starting cost: near zero.

### 5.3 Alternative stacks worth knowing about

- **Maximum simplicity:** GitHub + R2 + MotherDuck only. Skip Postgres, keep the catalog in DuckDB.
  Fewer moving parts; slightly clumsier for the registry tables. *Good if we want fewer accounts.*
- **Maximum scale:** GCP throughout (Cloud Storage + BigQuery + Cloud Run + Composer). Better if
  loan-level data grows to hundreds of GB; more complex, real bill risk. *Revisit if Freddie/ABS-EE at
  full history becomes the centre of gravity.*
- **Maximum control:** self-hosted Airflow + Postgres + MinIO on a VPS. Cheapest at large scale,
  but it becomes a system you must operate. *Not appropriate for a non-technical owner.*

### 5.4 Cost model

| Phase | Monthly |
|---|---|
| Phase 0–1 (foundations + India crown jewels) | **$0–40** — free tiers cover nearly everything; LLM extraction is the only real spend |
| Phase 2–3 (global anchors + micro data at scale) | **$40–150** — storage grows, scraping tier, MotherDuck paid tier |
| Phase 4+ (full coverage, continuous refresh) | **$150–350** — proxies for hard targets, more LLM extraction, larger storage |

For comparison: a single seat of the vendor data we're deliberately not buying (Moody's DRD,
S&P CreditPro, Trepp) runs into five to six figures annually.

---

## 6. Ingestion patterns — eight archetypes cover all 109 sources

Build each once as a reusable connector; adding a source becomes configuration.

| # | Archetype | Mechanics | Sources | Difficulty |
|---|---|---|---|---|
| **A** | **Bulk file download** | HTTP GET of CSV/ZIP/XLSX, unpack, land | Freddie, Fannie, SBA, EBA CSVs, NCUA, MIX | Easy |
| **B** | **Structured API** | REST/SDMX with pagination | FRED, FDIC, IMF, BIS, Brazil BCB, World Bank | Easy |
| **C** | **HTML table scrape** | Parse tables from regulator pages | GEMs, various EM regulators, RBI portal pages | Easy–moderate |
| **D** | **PDF table extraction** | Locate tables in PDFs, extract, normalise | **IBBI**, bureau reports, CRA studies, NeSL, CGTMSE, SLBC, NHB | **Hard — the India bottleneck** |
| **E** | **Filing/document crawl** | Index → filing list → document → parse | SEC EDGAR (ABS-EE, 10-D), exchange announcements, MCA | Moderate |
| **F** | **Browser automation** | Headless browser, JS rendering, session handling | NSE/BSE feeds, portals with dynamic content | Moderate–hard |
| **G** | **Manual-assisted** | Human fetches (CAPTCHA/login), pipeline processes from a drop folder | rbidocs (RBI FSR/T&P), some registries | Easy code, needs a routine |
| **H** | **LLM-assisted extraction** | Document → structured records via vision/text models, with validation | **NBFC ECL notes**, rating rationales, unstructured disclosures | Moderate, cost-aware |

### 6.1 On archetype D (the one that decides whether this project succeeds)

India's differentiated data is almost entirely inside PDFs. Recommended tiered approach:

1. **Deterministic first** — `pdfplumber` for text-layer tables, `camelot` for ruled tables.
   Free, fast, reproducible. Handles well-structured documents like IBBI's Table 5.
2. **Document AI second** — `Docling` (open source, strong layout understanding) for messier layouts.
3. **LLM vision last** — via OpenRouter, for genuinely irregular documents (annual-report ECL notes,
   varied SLBC formats). Always paired with a validation pass: extracted totals must reconcile to
   printed totals, or the record is flagged for review.

**Non-negotiable:** every LLM-extracted figure is checked against an arithmetic control (row/column
totals) or a published aggregate. Unvalidated LLM extraction is not data, it's a guess.

### 6.2 Politeness as engineering

Rate limits, exponential backoff, honest User-Agent, aggressive local caching, off-peak scheduling.
The reason is operational: blocked IPs and killed accounts break pipelines, and re-establishing
access costs far more than the throttling ever saved.

---

## 7. Data governance and source tiering

We are internal-only today, which removes redistribution questions but not all of them. Three tiers,
assigned in every source config:

**Tier 1 — Open.** Government, regulator, multilateral, open-licence data. ~70% of our sources
(RBI, IBBI, SEC, Fed, FDIC, EBA, ECB, IMF, BIS, World Bank, data.gov.in, NeSL, CGTMSE).
*Handling:* fetch freely, be polite, attribute.

**Tier 2 — Public but restricted.** Publicly accessible, but copyrighted or ToS-bound: bureau PDFs
(CIBIL, CRIF, MFIN, Sa-Dhan), rating-agency studies and rationales, company annual reports,
exchange content, P2P disclosures. *Handling:* fetch for internal analysis; store **extracted facts
with provenance**, not verbatim copies of proprietary tables; never redistribute. If we ever go
external, these are the rows requiring a licence conversation — the provenance record makes that
conversation straightforward rather than archaeological.

**Tier 3 — Excluded.** Personal/individual-level credit data, paywalled vendor databases, anything
needing credentials we don't legitimately hold. *Handling:* not ingested.

Two things genuinely sit in Tier 3 and are worth naming explicitly:

- **Individual credit data.** India's credit-information law (CICRA) and DPDP, plus GDPR in Europe,
  treat individual credit records as a regulated category — statutory, not contractual. Our entire
  target list is entity-level or aggregate, so we lose nothing by designing this out permanently.
- **Paywalled vendor content** (Moody's DRD, S&P CreditPro, Trepp, EDW bulk). Not a scraping
  problem — a contract and copyright one. We have free substitutes for essentially every use
  (the free annual default studies, GCD's published summaries, ratingshistory.info), which is why
  the research phase mapped them.

The CIC defaulter registries (CIBIL/Experian/CRIF suit-filed and wilful-defaulter lists) sit at the
**Tier 2 boundary**: the data is corporate and RBI mandates public dissemination, but the portals
are search-only with ToS restrictions and active bot-blocking. Treat as Tier 2 with a documented,
throttled, low-volume access routine — and use the CRA Annexure VI files as the primary label
source instead, since they are bulk-downloadable by design.

**Provenance is the governance mechanism.** Every stored figure carries source, URL, as-of date and
extraction reference. That single discipline is what makes any future licensing, publication or
audit question answerable in minutes.

---

## 8. Quality framework

| Check | What | When |
|---|---|---|
| **Schema validation** | Types, ranges, required fields, enums (Pandera) | Every parse |
| **Reconciliation** | Extracted totals vs published control totals (e.g. IBBI case sums vs printed cumulative ratios) | Every load |
| **Anchor check** | Derived metrics vs `6_Anchors` known values | Every gold build |
| **Freshness** | Actual vs expected publication date (release calendar R4) | Daily |
| **Completeness** | Row counts, period continuity, entity coverage vs prior run | Every load |
| **Drift detection** | Source layout/schema change detection → alert, don't fail silently | Every fetch |
| **Duplicate/entity QA** | Fuzzy-match review queue for entity resolution | Weekly |

**Rule:** a dataset is not "loaded" until it reconciles. The tracker's status ladder
(Fetched → Cleaned → Loaded → Validated) encodes exactly this.

---

## 9. Operations

- **Scheduling** by source cadence: daily (rating feeds), monthly (bureau/trust data),
  quarterly (regulator statistics), semiannual (FSR, P3DH), annual (studies, annual reports).
- **Release-calendar-driven**: R4 knows when each source *should* publish; the scheduler checks
  around those dates rather than blindly polling.
- **Failure handling**: retry with backoff → alert → manual queue. Never silent.
- **Manual-assist queue** for Tier G sources: a simple list of "please download these 3 PDFs and
  drop them here" tasks, so CAPTCHA-gated sources still stay current.
- **Runbooks** per source in `docs/runbooks/`, so any failure has a documented fix path.

---

## 10. Roadmap

### Phase 0 — Foundations (week 1)
Accounts, repo, secrets, storage, catalog skeleton, and **one source end-to-end** to prove the
stack (recommend SBA 7(a): open, bulk CSV, real credit content, archetype A).
**Exit:** a scheduled job that fetches, parses, loads and reconciles one dataset without human touch.

### Phase 1 — India crown jewels (weeks 2–6)
D1 (IBBI LGD panel), then D3 (NBFC ECL panel), then D2 (rating/default corpus). Plus R1/R2
registries, which make everything comparable. These are the highest-value, least-substitutable
datasets and they exercise archetypes D, E, F, H — after this, everything else is easier.
**Exit:** three datasets nobody else has, refreshed and reconciled.

### Phase 2 — Anchor warehouse (weeks 7–10)
The long-format aggregate store: RBI FSR/T&P, bureau publications, Fed/EBA/ECB series, agency
studies, GEMs, GCD, Philly Fed. Plus D4 (P3DH IRB panel) and the scenario library.
**Exit:** every calibration number in the tracker's `6_Anchors` queryable and auto-refreshed.

### Phase 3 — Micro data at scale (weeks 11–16)
Freddie/Fannie, ABS-EE auto, SBA full history, Kaggle behavioural sets, Bondora. Storage and
compute patterns for large panels.
**Exit:** real loan-level PD/LGD/EAD modelling possible entirely from platform data.

### Phase 4 — Coverage expansion (months 5–9)
D5 (district panel), D6 (harmonised recovery), EM geographies, developed-Asia Pillar 3, the
long tail. Coverage grid driven to zero unexplored cells.

### Phase 5 — Serving & reuse (ongoing)
Catalogue UI, extract API, documentation, and the downstream domain uses the owner has in mind.

---

## 11. Risk register

| Risk | Impact | Mitigation |
|---|---|---|
| PDF parsing accuracy (India datasets) | High — the moat depends on it | Tiered extraction, mandatory reconciliation, human review queue for outliers |
| Source layout changes break parsers | Medium, recurring | Drift detection, bronze immutability (replay, don't re-fetch), per-source runbooks |
| Access blocking (NSE, CIBIL, rbidocs) | Medium | Politeness by default, manual-assist queue, documented alternatives per source |
| Entity resolution errors (India corporates) | High — corrupts D2/D1 joins | Hard identifiers first, confidence scoring, never silent merges, review queue |
| Cost creep (LLM extraction, storage) | Low–medium | Deterministic-first extraction, R2 zero-egress, monthly cost check, budget alerts |
| Owner dependency on builder | High for continuity | Runbooks, managed services, Streamlit self-service, plain-language docs |
| Scope sprawl (109 → 300 sources before anything is finished) | High | Phase gates: no Phase 2 sources until Phase 1 datasets reconcile |
| Licensing questions if we later externalise | Deferred, not absent | Tier tagging + provenance from day one makes it answerable later |

---

## 12. Open decisions (owner input needed)

| # | Decision | Options | Recommendation |
|---|---|---|---|
| 1 | Cloud stack | Recommended (GitHub+R2+MotherDuck+Neon) · Simplest (GitHub+R2+MotherDuck) · GCP-native | Recommended |
| 2 | Budget ceiling | $0 (free tiers only) · ~$50/mo · ~$200/mo · uncapped-within-reason | ~$50/mo to start |
| 3 | First source to prove the stack | SBA 7(a) (easy, real) · IBBI (hard, highest value) · RBI FSR (manual-assist) | SBA, then IBBI immediately |
| 4 | Owner's working mode | Fully guided step-by-step · Claude executes, owner approves · Hybrid | Hybrid — guided for accounts, automated for code |
| 5 | Repo visibility | Private GitHub · local-only git · no version control | Private GitHub |
| 6 | Where the owner queries data | Streamlit app · MotherDuck web UI · Excel exports · BI tool | MotherDuck UI + Excel extracts initially |

Decisions get recorded in `docs/DECISIONS.md` as they're made.

---

## Appendix A — Repository structure

```
credit_risk_data/
├── CLAUDE.md                      # AI operating manual
├── README.md                      # human orientation
├── docs/
│   ├── PLATFORM_PLAN.md           # this document
│   ├── DECISIONS.md               # ADR + open decisions
│   ├── credit_risk_data_landscape.md
│   ├── SETUP_GUIDE.md             # step-by-step account/tooling setup
│   └── runbooks/                  # one per source: how it works, how to fix it
├── config/
│   ├── sources/                   # S-nnn_<slug>.yaml — the source registry
│   └── schemas/                   # Pandera schema definitions
├── src/
│   ├── connectors/                # one per archetype A–H
│   ├── extractors/                # PDF/LLM extraction utilities
│   ├── transforms/                # silver → gold logic
│   ├── quality/                   # validation and reconciliation
│   └── common/                    # storage, catalog, config, logging
├── pipelines/                     # per-source orchestration entrypoints
├── tests/
├── .github/workflows/             # scheduled runs
└── credit_risk_data_tracker.xlsx  # living checklist
```

## Appendix B — Source config format (illustrative)

```yaml
id: S-079
name: IBBI quarterly newsletters
tier: 1                       # governance tier
archetype: D                  # PDF table extraction
publisher: Insolvency and Bankruptcy Board of India
url_pattern: https://ibbi.gov.in/en/publication
portfolios: [corporate]
parameters: [lgd, recovery_timing, default_events]
coverage: {from: 2017-Q3, to: current}
schedule: quarterly
extraction:
  method: pdfplumber
  fallback: openrouter_vision
  tables: ["Table 5", "Table 12", "Table 13"]
targets:
  silver: silver.ibbi_cirp_cases
  gold:   gold.india_corporate_lgd_panel
reconciliation:
  - check: sum(realisation)/sum(admitted_claims)
    against: published_cumulative_ratio
    tolerance: 0.005
notes: Layout varies by edition; realisation ratios are cutoff-sensitive.
```
