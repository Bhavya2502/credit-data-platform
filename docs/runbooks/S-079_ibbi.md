# Runbook — S-079 · IBBI quarterly newsletters

**Status:** Complete. All four case-level tables extracted, reconciled and on quarterly refresh.

India's only public workout-LGD micro data, assembled from 36 quarterly PDFs spanning
Oct 2016 – Mar 2026.

---

## What this source yields

| Table | Grain | Rows | What it is |
|---|---|---|---|
| `silver.ibbi_cirp_cases` | case | ~1,213 | **Going-concern recovery** — resolution plans: admitted claims, liquidation & fair value, realised amount, dates |
| `silver.ibbi_liquidation_cases` | case | ~560 | **Gone-concern recovery** — actual sale proceeds and amounts distributed |
| `silver.ibbi_liquidation_waterfall` | section × period | ~17/edition | **Seniority-conditional recovery** — distribution by statutory claim rank |
| `silver.ibbi_voluntary_liquidations` | case | ~70/edition | Solvent wind-ups. **Not credit-loss events** |
| `gold.india_corporate_lgd_panel` | case | 922 | Modelling-ready: recovery, LGD, workout duration, size band |
| `gold.india_corporate_lgd_summary` | segment | 26 | Recovery curves by size, initiator, year, claims basis |

## Headline results

- Resolution recovery: **median 22.7%**, weighted 28.7% (IBBI published cumulative 30.56%)
- Liquidation recovery: **median 3.81%**, weighted 4.04%
- Workout duration: median **626 days** against the IBC's 330-day statutory target
- Unsecured financial creditors in liquidation, s.53(1)(d): **0.52%**
- Recovery by claim size is **U-shaped**, not monotonic: 33% under ₹10cr, 16% at ₹1,000–10,000cr,
  34% above ₹10,000cr. The ₹100–10,000cr band is the worst place to hold exposure.

## Why this source is hard

Ten years of editions drift in every dimension a parser depends on. Each of these silently
returned zero rows rather than erroring — the most dangerous failure mode here, because an
empty result is indistinguishable from a table that was never printed.

| Drift | Detail | Fix |
|---|---|---|
| **Table numbering** | "Table 5" is *CIRPs Yielding Resolution Plans* in 2026, *Claim Distribution and Reasons for Withdrawal* in 2020 | Locate by header signature, never by number |
| **Column count** | 11 (2020) → 12 (2022) → 13 (2026) | Parse row text, not cell geometry |
| **Column geometry** | pdfplumber splits `2292.53` into `2292.` and `53 27.48` in 2022 | Regex on flattened row text, anchored on dates and FC/OC/CD |
| **Numbers with stray spaces** | `3251.00` rendered `3 251.00` (South East U.P. Power, Jhabua Power) | Candidate merges scored by the arithmetic check |
| **No text layer** | 7 editions are pure page scans (2022Q1, 2023Q1–Q4, 2024Q1–Q2) | Vision extraction, ~$0.40 total |
| **Terminology** | Liquidation column: "Corporate Debtor" → "Corporate Person" | Alternative signature sets |
| **Header geometry** | 2022 liquidation uses spanning cells; sub-column names absent | Title anchor "Details of Closed Liquidations" |
| **Caption location** | 2022Q2/Q3 caption sits in page text, outside the table object | Page-title fallback |
| **Two blocks, one header** | Waterfall mixes closed and ongoing liquidations | Explicit block detection |

## Design rules that earned their place

1. **Let the document adjudicate its own parse.** CIRP rows print both amounts and the
   percentages they imply; recomputing `realisable/admitted × 100` and comparing catches
   column misalignment. This found the two space-split numbers above, which would have
   understated recovery on two large power-sector insolvencies by ~1000×.
2. **Generous positive matching, strict negative exclusion.** A loose signature once pulled
   CIRP *resolution* rows into the *liquidation* set (2026: 81 → 126 rows). Blending the good
   tail into the bad tail biases every recovery statistic upward and nothing downstream
   catches it. Exclusion list: `Realisable`, `Fair Value`, `Yielding Resolution`, `Resolution Plan`.
3. **Never impute a missing value.** Ongoing liquidations have no distribution; a
   "last populated cell" heuristic reported 100% recovery for every claim class.
4. **Quarantine, never drop.** 97 CIRP rows fail the arithmetic check. They stay in silver
   with their reason and are excluded from gold.
5. **Carry definitional breaks, don't smooth them.** `claims_basis` distinguishes the
   2019–21 financial-creditors-only era from later all-creditor reporting. Pooling them
   manufactures a spurious downward trend (FC-only reads 34.7% vs 28.7%).

## Known gaps

- **Pre-2019 editions** carry case names and dates but no financial columns. The LGD panel
  therefore starts 2019; case identity reaches back to 2016.
- **2025Q1** is an *"Eight Years of the IBC"* overview edition that omits the case annexure —
  a content decision by IBBI, not an extraction failure. Do not re-investigate.
- **2021Q1** yields no liquidation table; not diagnosed.
- Case coverage is ~1,213 of IBBI's reported 1,419 resolutions (85%). Aggregate realisation
  lands at 28.7% against a published 30.56%.
- Only ~200 of 560 liquidation rows carry a usable recovery figure; many are still open.

## Modelling caveats

- **Liquidation rows carry `validation_basis='structural_only'`.** That table prints no
  percentages, so rows cannot self-reconcile. Weight against CIRP rows accordingly.
- **`extraction_method`** distinguishes `deterministic` (96% arithmetic-valid) from `vision`
  (89%). Filter to deterministic if a purely reproducible dataset is required.
- **The resolution panel is survivorship-biased by construction** — a company that liquidates
  never yields a resolution plan. Use both panels for an unconditional view:
  `E[recovery] = P(resolution) × 22.7% + P(liquidation) × 3.8%`, and note IBBI reports
  1,419 resolutions against 3,003 liquidation referrals.
- **Voluntary liquidations are not defaults.** Solvent wind-ups, creditors paid in full.
- **Realisation ratios are cutoff-sensitive**: 33.7% (Jun-25), 32.8% (Dec-25), 30.6% (Mar-26).
  Always cite the edition.
- **`RBI` is a valid fourth initiator** — s.227 financial-service-provider referrals
  (Srei, Reliance Capital).

## Operating

- **Refresh:** quarterly cron (20th of Mar/Jun/Sep/Dec), ~2 months after quarter end.
- **Manual run:** Actions → *S-079 IBBI newsletters* → mode `latest` / `backfill` / `periods`.
- **Single edition:** mode `periods`, periods `2024Q1`.
- **Full backfill:** ~50 min, ~300 MB of PDFs, ~$0.40 of vision extraction.
- **Gold rebuilds automatically** after a successful load.

## Related

- Config: [`config/sources/S-079_ibbi_newsletters.yaml`](../../config/sources/S-079_ibbi_newsletters.yaml)
- Extractors: `src/extractors/ibbi_cirp.py`, `ibbi_liquidation.py`, `ibbi_supplementary.py`, `vision.py`
- Gold: `src/transforms/gold_india_corporate_lgd.py`
