# Architecture Decision Record

How we record choices so that six months from now we know *why*, not just *what*.

**Format:** each decision gets a number, a date, a status (Proposed / Accepted / Superseded),
the context, the choice, and the consequences we accepted.

---

## Open decisions — awaiting owner

| # | Decision | Status |
|---|---|---|
| OD-1 | Cloud stack selection | **Resolved → ADR-007** |
| OD-2 | Monthly budget ceiling | **Resolved → ADR-008** |
| OD-3 | First source to prove the stack | **Resolved → ADR-009** |
| OD-4 | Owner working mode | **Resolved → ADR-010** |
| OD-5 | Repository visibility | **Resolved** — private GitHub repo (within ADR-007) |
| OD-6 | Owner's query surface | Open — MotherDuck web UI initially; revisit when gold tables exist |

---

## Accepted decisions

### ADR-001 — Internal prototype, not a public product (for now)
**Date:** 2026-07-30 · **Status:** Accepted

**Context.** The platform could be built as an internal research asset or as a public/commercial
data product. The two imply very different constraints: a public product requires licence clearance
for every copyrighted source, redistribution rights, and compliance review.

**Decision.** Build as an internal prototype. Defer all questions of external distribution.

**Consequences.**
- We can ingest broadly without per-source licence negotiation.
- We must nonetheless tag every source with a governance tier and retain full provenance, so that
  a future externalisation decision is a filtering exercise rather than a rebuild.
- Tier 3 (personal credit data, paywalled vendor content) stays excluded regardless of internal
  status, because that boundary is statutory/contractual rather than distributional.

---

### ADR-002 — Cloud-only, no local storage
**Date:** 2026-07-30 · **Status:** Accepted

**Context.** Owner is non-technical and explicitly does not want local data management. Datasets
will reach hundreds of GB (loan-level panels).

**Decision.** All artefacts live in cloud object storage and managed databases. The local machine
holds only code and documents (in git). No pipeline ever depends on a local path.

**Consequences.**
- Requires cloud accounts and secret management from day one.
- Pipelines run in the cloud (GitHub Actions), not on the owner's machine — so refreshes happen
  whether or not the machine is on.
- Manual-assist sources (CAPTCHA-gated) need a cloud drop location, not a local folder.

---

### ADR-003 — Medallion architecture with immutable bronze
**Date:** 2026-07-30 · **Status:** Accepted

**Context.** Much of our India data comes from PDFs where parsers will be imperfect initially and
will improve over time. Sources also disappear or change layout.

**Decision.** Three layers (bronze/silver/gold). Bronze is raw, immutable, timestamped, with a
fetch manifest. All reprocessing replays from bronze.

**Consequences.**
- Storage cost is higher (we keep raw copies forever) — mitigated by R2's cheap storage.
- Parser improvements never require re-fetching, which protects us against source removal and
  keeps us polite to publishers.
- Full auditability: any figure traces back to the exact file it came from.

---

### ADR-004 — Config-driven source registry
**Date:** 2026-07-30 · **Status:** Accepted

**Context.** 109 sources today, targeting 300+. Bespoke code per source does not scale and creates
a maintenance burden the owner cannot carry.

**Decision.** Sources are declared in YAML (`config/sources/S-nnn_*.yaml`). Code is organised as
eight reusable connectors keyed to ingestion archetypes. Adding a source is normally configuration.

**Consequences.**
- Higher upfront cost building generalised connectors.
- Adding sources becomes fast and low-risk; the tracker, registry and configs stay in sync.
- Novel sources still occasionally need new code — that's expected, and becomes a new archetype.

---

### ADR-005 — Deterministic-first document extraction
**Date:** 2026-07-30 · **Status:** Accepted

**Context.** India's differentiated datasets are locked in PDFs. LLM extraction is tempting and
fast to prototype, but non-deterministic and costly at volume.

**Decision.** Tiered extraction: `pdfplumber`/`camelot` → `Docling` → LLM vision (OpenRouter) as
last resort. **Every LLM-extracted figure must pass an arithmetic or published-total
reconciliation before it is stored.**

**Consequences.**
- Slower initial build for irregular documents.
- Reproducible results and controlled cost.
- A validation harness is mandatory infrastructure, not an optional extra.

---

### ADR-006 — Provenance on every figure
**Date:** 2026-07-30 · **Status:** Accepted

**Context.** The platform's credibility rests on being able to say where any number came from —
for modelling defensibility, for QA, and for any future licensing question.

**Decision.** Every stored value carries `source_id`, source URL, as-of date, fetch timestamp, and
an extraction reference (page/table/cell) where extracted from a document.

**Consequences.**
- Wider tables, marginally more storage.
- Any number is auditable in seconds; QA and licensing questions become tractable.

---

### ADR-007 — Cloud stack: GitHub + Cloudflare R2 + MotherDuck
**Date:** 2026-07-30 · **Status:** Accepted

**Context.** Needed a cloud-only stack operable by a non-technical owner, with predictable cost and
minimal moving parts. Alternatives considered: a no-card path (MotherDuck only, deferring object
storage) and a GCP-native path (GCS + BigQuery).

**Decision.** Full recommended stack from day one:
- **GitHub** (private repo) — code, version history, scheduled runs via Actions, secret storage
- **Cloudflare R2** — bronze object storage; chosen for zero egress fees
- **MotherDuck** — silver/gold analytical store and the owner's query surface
- **OpenRouter** — LLM-assisted document extraction
- **GitHub Actions Secrets** — credential storage

**Consequences.**
- A payment card is on file at Cloudflare (free tier; no expected charge below 10 GB).
- No rebuild needed later — the architecture is the target architecture.
- Neon Postgres may be added for small relational catalog tables if DuckDB proves awkward for
  the entity crosswalk; deferred until there is evidence it is needed.
- GCP-native remains the documented escape hatch if loan-level volume becomes the centre of gravity.

---

### ADR-008 — Per-item budget approval rather than a standing ceiling
**Date:** 2026-07-30 · **Status:** Accepted

**Context.** Costs are dominated by AI document extraction and (later) paid scraping services.
Owner preferred visibility over a blanket allowance.

**Decision.** Default to free tiers. Any spend is proposed individually with its cost, what it buys,
and the free alternative, before committing.

**Consequences.**
- Deterministic-first extraction (ADR-005) becomes doubly important — it is both the quality
  choice and the default-free choice.
- Slightly slower on irregular PDFs, where AI extraction would be the fast path.
- Set a hard credit limit on the OpenRouter key so no runaway loop can spend unattended.

---

### ADR-009 — SBA 7(a) as the first end-to-end source
**Date:** 2026-07-30 · **Status:** Accepted

**Context.** Needed a first source that validates the entire pipeline without conflating platform
bugs with extraction bugs.

**Decision.** SBA 7(a) & 504 FOIA data (S-012) first: open US government data, bulk CSV
(archetype A), ~1.79M small-business loans with actual charge-off amounts. Then IBBI (D1)
immediately after.

**Consequences.**
- Proves fetch → bronze → parse → silver → load → reconcile with a simple format.
- Delivers genuine analytical value on day one (a real SME PD/LGD dataset), not a throwaway test.
- IBBI's PDF extraction difficulty is then isolated to extraction, on proven plumbing.

---

### ADR-010 — Hybrid working mode
**Date:** 2026-07-30 · **Status:** Accepted

**Context.** Owner is non-technical but wants professional execution and understanding.

**Decision.** Owner handles anything requiring their identity, password or payment method
(account creation, key generation, secret entry). Claude writes, runs and debugs all code, then
reports results. Owner approves direction at phase boundaries.

**Consequences.**
- Setup guidance must stay in plain language with options and recommendations (a standing rule
  in `CLAUDE.md`).
- Credentials never pass through chat — they go from the source service into GitHub Secrets directly.
- Phase-boundary reviews are the control point, not per-commit approval.

---

## Decision log template

```
### ADR-nnn — <title>
**Date:** YYYY-MM-DD · **Status:** Proposed | Accepted | Superseded by ADR-mmm

**Context.** What forced a choice.

**Decision.** What we chose.

**Consequences.** What we gain, what we accept, what this closes off.
```
