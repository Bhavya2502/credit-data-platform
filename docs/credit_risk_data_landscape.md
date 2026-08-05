# Credit Risk Data Landscape — Sources for Prototyping (Global + India)

_v2 — research compiled 30 July 2026. This revision adds a five-workstream verification pass
(global consumer micro · global wholesale · EM/cross-country · India micro · India regulatory),
with every new claim checked against a live source._

---

## What changed in v2

**Major additions**

1. **EBA Pillar 3 Data Hub went live 26 Jan 2026** — machine-readable IRB PD/LGD/RW tables (template CR6)
   for all large EU banks, bulk-downloadable from one endpoint (§3.1). This is the biggest new piece of
   infrastructure in the whole landscape.
2. **IBBI's quarterly newsletter contains a company-named, case-level LGD annexure** ("Table 5: CIRPs
   Yielding Resolution Plans"): admitted claims, liquidation value, fair value, realised amount and dates
   per resolved corporate debtor. Stitched across quarters ≈ a ~1,400-case Indian corporate LGD dataset (§4.2).
3. **The rating agencies' annual default & recovery studies are free** (S&P openly, Moody's via
   registration/mirrors) — a free global corporate PD + seniority-LGD calibration layer that makes the
   paid DRD/CreditPro optional for prototyping (§2.6).
4. **Philadelphia Fed publishes FR Y-14M-based card and mortgage aggregates** — utilization, minimum-payment
   share, originations by score band, quarterly since 2012 — the best public EAD/CCF anchor found anywhere (§3.2).
5. **Banca d'Italia publishes an actual NPL workout-recovery time series** from its credit register
   (2024 avg recovery 41%; secured 44% / unsecured 37%; with Excel appendix) (§3.3).
6. Two modern behavioural Kaggle datasets verified: **Amex Default Prediction** (459k customers × monthly
   statements) and **Home Credit "Model Stability" 2024** (relational, out-of-time weekly evaluation) (§2.5).
7. **Bondora's recovery-cash-flow loan book survives** under the rebranded "Go & Grow" (API dead, XLSX +
   archived snapshots live) — still the only free consumer loan-level dataset with workout data (§2.5).
8. India micro layer mapped: **four public defaulter registries** (all CICs), **NeSL default-incidence
   statistics by ticket size**, **NSDL corporate bond database + exchange default intimations + daily CRA
   rating feeds on NSE/BSE (new, Aug 2025)**, **CGTMSE claims data**, **LTFS hackathon loan-level data
   (live Kaggle mirrors)**, **NBFC-P2P mandatory monthly NPA disclosures**, **SLBC district-wise NPA
   annexures**, **ARC security-receipt recovery studies**, **NAFSCOB co-op bank NPAs** (§4).
9. **Formal researcher access to European loan-level credit registers** (Bundesbank RDSC, Banco de España
   BELab, Banco de Portugal BPLIM — the last with remote execution) — a route to registry-grade microdata
   for methodology work that v1 missed entirely (§7.4).
10. EM open-data comparators (Brazil's SCR.data is the world benchmark), cross-country layers (IMF FSI,
    OECD SME Scoreboard 2026, BIS, Doing Business recovery-rate archive), the freshly updated
    **Laeven–Valencia crisis database (through 2025)** for stress-severity anchors, and **NGFS climate
    scenarios** (§3.5–3.7).

**Corrections to v1**

- The final RBI ECL directions are titled **"RBI (Commercial Banks — Asset Classification, Provisioning
  and Income Recognition) Directions, 2026"** (not "Scheduled Commercial Banks…"). Confirmed: issued
  27 Apr 2026, effective 1 Apr 2027, PD/LGD/EAD-based, **prudential floors ~0.40% Stage 1 / ~5% Stage 2**,
  30-dpd SICR presumption, glide path to 31 Mar 2031. SFBs, payments banks and LABs are **excluded
  entirely** (no standardized fallback).
- **CRA default studies do NOT name defaulted entities** in annexures (verified CRISIL & India Ratings
  FY2025). Entity-level default labels come instead from the SEBI-mandated half-yearly **Annexure V
  (full rating history Excel) and Annexure VI (list of defaults)** on each CRA's website — plus, since
  Aug 2025, daily prescribed-format rating files auto-published by NSE/BSE.
- **BCBS Basel III Monitoring Report does not publish IRB PD/LGD by portfolio** — the EBA Credit Risk
  Benchmarking exercise is the source for that.
- **KBRA presale reports moved behind a paywall** (KBRA Premium); don't plan on free KBRA pool strats.
- **Credit cards have no ABS-EE loan-level data** — card disclosure is pool-level (monthly 10-D master
  trust reports). Finsight is free to browse but its cleaned loan-level CSV exports are a paid tier;
  the free route is raw ABS-EE XML on EDGAR.
- RBI's Aug 2024 credit-model-risk circular **was only ever a draft and was never finalized**; RBI
  restarted with a broader draft Model Risk Management guidance on 24 Jun 2026. The climate disclosure
  framework (draft Feb 2024) is also still not final; RB-CRIS is the shipped artifact.
- IBBI cumulative realisation vs admitted claims drifts with the cutoff: 33.7% (Jun 2025) → 32.8%
  (Dec 2025) → **30.6% (Mar 2026)**. Always cite the quarter.
- LTFS FinHack **2** is a volume-forecasting dataset, not default data (FinHack 1 = vehicle-loan default;
  FinHack 3 = top-up cross-sell with bureau behavioural tables).

---

## 0. The headline finding

**There is no single "Fannie Mae of credit risk" outside US mortgage.** The world's credit-risk data is
fragmented along a predictable fault line:

| | Loan/facility-level micro data | Aggregate benchmarks |
|---|---|---|
| **Retail, US/EU** | Abundant and free (agency MBS, ABS-EE, P2P archives) | Abundant |
| **Wholesale/corporate** | Almost nowhere public — locked in bank consortia and paid vendors | Abundant, and now machine-readable (P3DH) |
| **India, any portfolio** | Near-zero public micro data (a handful of exceptions mapped in §4.7–4.8) | Surprisingly rich, and improving |

The practical consequence: **you cannot source a complete prototype from one place. You assemble it.**
The realistic architecture is a *three-layer stack* — real micro data where it exists, published
aggregates as calibration anchors everywhere else, and synthetic generation to fill the shape in
between. Section 7 lays this out.

### The single most important India insight

Two RBI rulebooks land on the **same date, 1 April 2027**:

1. **RBI (Commercial Banks — Asset Classification, Provisioning and Income Recognition) Directions, 2026**
   — final ECL directions issued **27 April 2026** (draft 7 Oct 2025). Banks must estimate ECL using
   **PD, LGD and EAD models**; three-stage IFRS-9-style classification with a **30-dpd SICR presumption**
   (90-dpd Stage 3 line retained); EIR discounting for post-Apr-2027 originations; **prudential floors
   (~0.40% Stage 1 standard exposures, ~5% Stage 2)**; four-year glide path to 31 March 2031 for
   provisioning the existing book. SFBs, payments banks and local area banks are excluded for now.
2. **RBI (Commercial Banks — Capital Charge for Credit Risk — Standardised Approach) Directions, 2026**
   — Basel III finalisation, issued the same day, also effective 1 April 2027.

So India is about to require **every commercial bank to build PD/LGD/EAD models** — while **no Indian
bank has ever been approved to use IRB for regulatory capital**. That means:

- There is **no legacy of published Indian PD/LGD estimates** the way EBA disclosures give you for Europe.
- The only Indian institutions with a real ECL modelling track record are **NBFCs**, on Ind AS 109 since
  FY2018-19 (and they stay on it — the Apr 2026 package amended NBFC IRACP/credit-risk directions rather
  than moving NBFCs to the bank framework).
- Governance requirements are converging too: RBI's draft **Model Risk Management guidance (24 Jun 2026)**
  wants board-approved MRM frameworks, model inventories/tiering, independent validation and human
  oversight — any scorecard prototype should ship with validation documentation from day one.
- **Demand for exactly these prototypes is about to spike, and the data gap is structural, not
  incidental.** This is the opportunity, not just the obstacle.

### Ten concrete takeaways (v2)

1. **A complete free global calibration stack now exists**: S&P/Moody's annual studies (PD/transitions
   since 1981/1920 + recovery by seniority) + GCD/GEMs/Banca d'Italia published LGDs (≈22–44% depending
   on collateral/market) + Philly Fed/CFPB utilization data (EAD/CCF) — enough to prototype PD/LGD/EAD
   without buying anything.
2. **EBA P3DH replaces PDF-scraping for IRB parameters**: build the cross-bank PD/LGD-by-portfolio panel
   from one bulk endpoint.
3. **India corporate LGD is no longer "aggregates only"**: IBBI Table 5 gives case-level,
   company-named recovery outcomes with timing; ARC/SR studies and the T&P recovery-by-channel table
   (IBC ~37%, SARFAESI 31.5%, Lok Adalats 2.4% in FY25) complete the channel-conditional picture.
4. **India corporate default labels are assemblable from public sources**: CRA Annexure V/VI files +
   daily NSE/BSE rating feeds (Aug 2025 onward) + Reg 57 non-payment intimations + the four CIC defaulter
   registries + NeSL incidence stats triangulate into a public default-event history.
5. **The NBFC ECL panel is proven feasible**: Bajaj Finance, Cholamandalam and Shriram all disclose
   stage-wise EAD/ECL; Chola even publishes a **standalone public ECL methodology document with
   segment-wise PD term structures and LGDs**.
6. **India has exactly one real public loan-level retail dataset** (LTFS vehicle-loan hackathon data,
   ~233k loans with bureau fields and default labels, live Kaggle mirrors) — plus monthly NBFC-P2P
   portfolio disclosures as an unsecured-consumer aggregate series.
7. **EAD/CCF is no longer hopeless**: Philadelphia Fed Y-14M aggregates (utilization & payment behaviour
   by score band, quarterly since 2012), CFPB CARD Act report, card master-trust payment rates, and
   published Fed revolver-utilization research give usable anchors even without micro data.
8. **Microfinance India handed you a complete stress cycle**: four independent trackers (MFIN, Sa-Dhan,
   CRIF, Equifax) document PAR 31-180 going ~2% → 6.3% → 2.0% across FY24–FY26 — rare through-the-cycle
   calibration + cure-rate material at state granularity.
9. **Stress severity should anchor on Laeven–Valencia (2026 update)**: median peak NPL ≈11% in advanced
   economies, ≈30% in EM crises — a defensible tail for ICAAP/ECL severe scenarios; BoE Dec 2025
   bank-level stress results and NGFS Phase V provide the scenario architecture.
10. **If registry-grade micro data is essential, Europe will host you**: Bundesbank RDSC, BdE BELab and
    Banco de Portugal BPLIM (remote execution) accept external research projects on loan-level credit
    registers — develop methodology there, transfer it (not the data) to India.

---

## 1. Frame first: what "credit risk data" actually means

Different prototypes need genuinely different data. Sourcing goes badly when these get conflated.

| Use case | What you need | Hardest part to source |
|---|---|---|
| **Application scorecard** | Applicant attributes at origination + binary outcome over a fixed window. Needs **rejects** too, for reject inference. | Rejected-application data (almost never published) |
| **Behavioural scorecard** | Monthly account-level performance panel (balances, utilisation, DPD, payments) | Long panels with transaction detail |
| **PD model / rating** | Obligor characteristics + default flag + observation window; ideally through-the-cycle | Corporate/SME default flags at obligor level |
| **LGD model** | Defaulted facilities only + full **post-default recovery cashflows**, costs, timing, collateral | The scarcest data in all of credit risk |
| **EAD / CCF model** | Undrawn commitments and limits over time, drawdown behaviour before default | Revolver limit history — essentially unpublished |
| **IFRS 9 / ECL provisioning** | Lifetime PD term structures, SICR triggers, forward-looking macro overlays, stage migration | Stage migration histories |
| **Stress testing** | Macro scenario paths + historically estimated portfolio-level loss sensitivity | Nothing, actually — this is the best-served area |
| **Portfolio / concentration** | Exposure by sector, geography, rating, size; correlation/contagion structure | Exposure-level granularity |

**Key structural point:** PD data is comparatively easy; **LGD and EAD data are the real bottleneck**, in
*every* jurisdiction. Most public datasets end at "default = yes/no". Plan for this — it drives the whole
sourcing strategy. (v2 materially improves both: LGD via IBBI/Banca d'Italia/Bondora/GEMs, EAD via
Philly Fed/CFPB/master trusts.)

### 1.1 Coverage audit — by scorecard type

| Scorecard type | Best supporting data (global) | India status |
|---|---|---|
| **Application** | Home Credit 2018 (multi-table app + bureau), GSE/HMDA origination fields, LendingClub, classics (South German, Taiwan) | **LTFS FinHack-1 is the only real dataset**; otherwise synthesize (§7) |
| **Behavioural** | **Amex monthly statement panel**, Berka transactions, GSE/ABS-EE monthly performance panels, Bondora | No public micro; P2P monthly aggregates + CIBIL CMI risk tiers as anchors |
| **Collections / recovery** | No public *action-level* (dialler, PTP, settlement-offer) data exists anywhere. Nearest micro: **Bondora recovery stages + cashflows**, GSE post-default timelines & modification/forbearance flags, auto ABS-EE repo/liquidation, cure-vs-liquidate competing risks from GSE delinquency strings; roll-rates from master-trust buckets & NY Fed transitions | **IBBI Table 5** (corporate workouts), ARC/SR aggregates; nothing retail |
| **Early-warning (corporate EWS)** | NUS-CRI point-in-time PDs, Credit Benchmark consensus, rating-action feeds, Altman-style from EDGAR XBRL | **Good**: FSR SMA-0/1/2 distributions, NeSL incidence by ticket size, daily NSE/BSE rating feeds, Reg 57 intimations |
| **Limit management / CLIP** | CFPB CARD Act report (line-increase and utilization stats by tier), Philly Fed utilization by score band — anchors, no micro anywhere | Nothing public |
| **Pricing / risk-based pricing** | GSE note rates vs risk attributes, LendingClub grade/APR, master-trust portfolio yield | **BSR-1 interest-rate-bucket × district × occupation** — underrated |
| **Profitability / RAROC** | Component proxies only (trust yield/charge-off/payment-rate); no public cost allocations | Nothing public |
| **Reject inference** | HMDA declined applications, LendingClub rejects | Nothing public |
| **Monitoring / stability** | **Home Credit 2024** (out-of-time weekly design is a ready-made monitoring testbed); quarterly benchmark refreshes (EBA dashboards, bureau reports) for drift baselines | Bureau quarterlies as drift baselines |
| **Fraud** | Deliberately out of scope — different discipline with its own datasets (IEEE-CIS, PaySim etc.); don't conflate with credit risk | — |

### 1.2 Coverage audit — by variable type

| Variable family | Status | Where |
|---|---|---|
| Application / demographic | ✓ | Home Credit, LTFS, HMDA, GSE origination files |
| Bureau-derived | ✓ *as features*, ✗ *as raw tradelines* | Home Credit bureau tables, LTFS CIBIL fields, Amex (anonymized). **No raw tradeline archive is public anywhere**; restricted panels only (NY Fed CCP/Equifax, academic UC-CCP). India: CICRA blocks everything; AA rail is the consented future |
| Behavioural / account performance | ✓ | Amex statements, GSE/ABS-EE monthly panels, Bondora, master trusts (pool) |
| Transactional | **Thin everywhere** | Berka (1993–98) and AlfaBattle 2.0 are the only real public sets; the real-world route is consented open banking (AA in India, PSD2 in EU), which is not a research dataset |
| Collateral | ✓ | LTV fields (GSE, ABS-EE, covered-bond HTT); value indices (FHFA HPI, Manheim, **RESIDEX**) |
| Financial statements | ✓ | EDGAR XBRL, Prowess/MCA/screener (India), Orbis (paid) |
| Macro / scenario | ✓✓ | FRED, BIS, IMF, DBIE + Fed/EBA/BoE/RBI/NGFS scenario libraries |
| Market-implied | Partial | NUS-CRI PDs/DTD free; CDS (Markit) and bond spreads (TRACE) are paid/WRDS |
| Collections actions | ✗ | Nowhere public, globally |

### 1.3 The honest gaps (and the mitigation the plan assumes)

1. **EAD/CCF micro data** — anchors only (§3.2); true limit histories need GCD membership or a bank partnership.
2. **Collections action-level data** — never public; build collections prototypes on Bondora/GSE post-default skeletons + synthetic action layers.
3. **Raw bureau tradelines** — restricted panels only, every jurisdiction; India adds a statutory bar (CICRA).
4. **Modern transaction data** — Berka/Alfa are dated; consented AA/PSD2 data is operational, not researchable.
5. **India retail micro beyond LTFS** — partnership or synthesis; there is no third option today.
6. **Recoveries on restructured-but-never-insolvent exposures** — dark in every jurisdiction (§5).
7. **BNPL** — no loan-level anywhere (deals are 144A; Reg AB II asset-level rules never covered personal/marketplace/BNPL or student loans); India's closest proxy is FACE's fintech-PL delinquency series.

---

## 2. Global — loan-level / facility-level micro data (free or near-free)

### 2.1 US mortgage — the deepest well, and it goes further than most people use

**Fannie Mae Single-Family Loan Performance Data** and **Freddie Mac Single-Family Loan-Level Dataset**
are the obvious starting points, but two things are commonly missed:

- **Freddie's dataset covers ~55 million mortgages originated Jan 1999 – Sep 2025**, with monthly
  performance to Sep 2025. Access via Clarity Data Intelligence (free registration).
- **Both include actual loss/disposition data** — not just default flags. Fannie's enhanced dataset
  carries credit event dates, **credit event costs incurred, and recovery proceeds received**, through to
  property disposition. Freddie's Standard Dataset carries the equivalent expense and proceeds columns.

  → **This makes them genuinely usable LGD datasets, not just PD datasets.** You can build a full
  loss-severity model — foreclosure costs, REO timeline, net sale proceeds, MI/credit-enhancement
  recoveries — which is very hard to do anywhere else for free. They are also the canonical
  **prepayment** datasets (the competing risk you need for lifetime-PD term structures and EIR-based
  ECL), and their delinquency-string histories support **cure-rate and roll-rate (collections-adjacent)
  modelling** out of the box.

Also in this family:
- **Ginnie Mae MBS loan-level disclosure** — monthly, from 201204 onward, FHA/VA/PIH/RD loans, includes
  delinquency months (1–6+). Free, no registration. Government-guaranteed credit box — a genuinely
  different risk profile from GSE conventional.
- **Freddie Mac Multifamily Loan Performance Database (MLPD)** — loans from 1994, includes defaults,
  delinquencies, property information and **REO sale dates**. **Fannie Mae Multifamily** is the counterpart.
- **FHFA public-use datasets, NMDB aggregate statistics** (includes performance/delinquency series by
  geography), and **FHFA HPI** — free CSV/JSON, national/state/metro/ZIP, back to the mid-1970s — the
  collateral-value input for mortgage LGD stress.
- **HMDA** (FFIEC) — huge origination-side dataset with applicant characteristics **and declined
  applications**. No performance, but one of the very few public sources of *rejects* — usable for
  reject-inference methodology work.

### 2.2 SEC ABS-EE / Reg AB II — the most under-used free facility-level source (+ card master trusts)

Every *registered public* ABS deal must file **Form ABS-EE with an EX-102 asset data file (XML)** on
EDGAR — at offering and monthly with each Form 10-D. Free, no registration, machine-readable.

What you'll actually find (Reg AB II applies only to registered offerings; private-label RMBS went
entirely to Rule 144A after 2014, so registered RMBS is empty):

- **Auto loan and auto lease ABS = rich, deep, ongoing.** Monthly loan-level with obligor credit score,
  income/DTI verification, vehicle value, LTV, payment history, **charge-off amount, recovery amount,
  repossession and liquidation proceeds.** Arguably the best free **consumer LGD dataset in existence**.
  Issuers to look for: Ford Credit, GM Financial, Santander Drive, World Omni, CarMax, Toyota, Honda,
  Ally, Carvana, Westlake. Pair with the **Manheim Used Vehicle Value Index** (free monthly download)
  for the collateral-value factor.
- **CMBS = rich** (Schedule AL plus CREFC IRP-style servicer detail).
- **RMBS = effectively empty.** Don't plan around it. Partial substitute: rating-agency presale/new-issue
  reports carry pool stratifications (FICO/LTV/DTI bands) for 144A deals — Fitch/Moody's/S&P presales are
  generally free with registration, **KBRA's are now paid** (KBRA Premium).
- **Credit cards are NOT in ABS-EE** — card disclosure is pool-level only, via monthly **Form 10-D master
  trust reports** (Chase Issuance Trust — filing monthly through Jul 2026, Citibank Credit Card Issuance,
  Capital One Multi-Asset Execution, Amex Lending): receivables, gross/net charge-offs, delinquency
  buckets (30–180+), **monthly principal payment rate**, portfolio yield, excess spread. 20+ years of
  monthly series through multiple cycles → card stress curves and payment-rate (EAD-adjacent) benchmarks.
- **Practical access layer:** finsight.com is free to browse deals/filings; its cleaned ABS-EE CSV
  exports are paid — the free loan-level route is raw XML from EDGAR.
- **Scope limit worth knowing:** Reg AB II's asset-level rules never covered personal/marketplace/BNPL
  loans or student loans (and exempted cards) — so there is no ABS-EE route to those asset classes;
  their deals are 144A, visible only through presale reports and rating-surveillance commentary.

### 2.3 European securitisation — European DataWarehouse (EDW)

ESMA- and FCA-designated securitisation repository; **100m+ loans since 2012** across RMBS, auto, SME,
consumer, leasing (4bn+ data points). Loan-level under ECB/ESMA/FCA templates via EDvance. Registration
required; raw bulk data is paid, though researcher access on request exists. The **ESMA disclosure
templates themselves are free and are an excellent schema reference** — the EU's canonical definition of
a loan-level record per asset class.

### 2.4 US small business — SBA 7(a) and 504 FOIA data

`data.sba.gov/dataset/7-a-504-foia` — free CSV, quarterly refresh. ~1.79m 7(a) loans totalling $517bn,
with **gross approval, guaranteed portion, loan status, and charge-off amount**, plus NAICS, geography,
franchise code, bank name. One of very few free datasets with an actual **loss amount at individual
small-business-loan level** — 30+ years of vintages spanning three recessions. (PPP loan-level data is
also public but has little credit-outcome content.)

### 2.5 Consumer / P2P / behavioural micro data

**The two best modern sandboxes (both Kaggle, both non-commercial licenses):**

- **American Express — Default Prediction (2022)** — customer-level monthly statement panel: **458,913
  train customers, ~5.5M statement rows, 190 anonymized features** in five blocks (Delinquency, Spend,
  Payment, Balance, Risk); label = failure to pay within 120 days of latest statement. ~16 GB raw.
  Still downloadable with a Kaggle account. → The best public *behavioural card* dataset; utilization-path
  feature engineering, behavioural PD.
- **Home Credit — Credit Risk Model Stability (2024)** — relational base table (case_id, decision date,
  target) + nested internal tables (previous applications, person, deposit, tax registry) + external
  bureau tables; scored on **out-of-time weekly Gini with a drift penalty**. Differs fundamentally from
  the 2018 **Home Credit Default Risk** set (single-snapshot, 307,511 rows, no dates): the 2024 set is a
  ready-made **model-stability/monitoring testbed** (PSI/drift experiments, OOT validation design).
  The 2018 set remains the best public *application-scorecard* structure (emerging-market, bureau-linked,
  multi-table — the most India-relevant of the classics).

**The recovery-data unicorn:**

- **Bondora → "Go & Grow"** (Estonia/EU; entity renamed Apr 2026, dataset now at goandgrow.eu/public-statistics)
  — full loan book from Feb 2009 as Excel download, including **post-default fields: EAD1/EAD2,
  PrincipalRecovery, InterestRecovery, RecoveryStage (Collection/Recovery/Write-off)**. The investing API
  was shut Sept 2025 — use the XLSX plus archived snapshots (IEEE DataPort 2009–2020, Kaggle mirrors).
  → Still the only free consumer loan-level dataset with recovery cash flows: build workout-LGD and
  cure-rate models here, cross-checked against auto ABS-EE recovery fields.

**Classic and structural:**

- **LendingClub 2007–2018** — mirrored on Kaggle (`wordsforthewise/lending-club`), includes **rejected
  applications** (rare; reject-inference work). Platform no longer publishes.
- **PKDD'99 Berka (Czech bank)** — real anonymized retail bank data 1993–98: 4,500 accounts, **1.06M
  transactions, 682 loans with good/bad status**, cards, demographics — live at the CTU Prague relational
  repository (guest MariaDB) + Kaggle mirrors. → The teaching standard for *transaction-based*
  behavioural features and relational/graph pipelines.
- **South German Credit (UCI id 522, CC BY 4.0)** — Grömping's 2019 correction of the Statlog German
  Credit set (fixes severe code-table errors, e.g. reversed foreign-worker coding). Use this, not the
  classic, for methodology demos. Other classics: **Taiwan Credit Card Default**, **Give Me Some Credit**.
- **Kiva** (global microfinance loans incl. default), **Prosper** listings.
- **AlfaBattle 2.0** (Alfa-Bank, 2021) — 4.3M card-transaction records with a credit-product default
  target; GitHub mirrors (Russian-language docs).

**Dead or gated loan books (know before you plan):** Funding Circle UK stopped publishing its loanbook
in June 2018 (community GitHub snapshots only); Zopa/RateSetter books are offline (Wayback/community
snapshots); Mintos' full loan-book export is login-gated and unconfirmed; October.eu is in run-off.
**Caution:** most 2024–25 Kaggle "loan default" datasets are synthetic playground derivatives — fine for
pipeline demos, useless for calibration.

### 2.6 Corporate — free obligor-level PD, transitions and recoveries

- **The free annual default & recovery studies (new in v2 — these change the economics):**
  - **S&P "Default, Transition, and Recovery: Annual Global Corporate Default and Rating Transition
    Study"** — free on spglobal.com (regulatory-disclosure articles; 2024-data edition published
    Mar 2025: 145 defaults, 59.3% distressed exchanges, Gini 89.4%; a 2025-data edition is listed).
    Full static-pool cumulative default tables + transition matrices since 1981; companion US/EU/EM studies.
  - **Moody's "Annual default study: corporate default and recovery rates"** — default rates to 1920,
    **recovery by seniority/instrument** (bank loans vs bonds, 1st lien vs sub), transition matrices.
    No longer an open PDF on moodys.com — free via registration at ratings.moodys.com or widely mirrored.
  - **Fitch transition & default studies** (corporate + structured finance) — free with registration.
  - **Moody's US Municipal defaults study** — muni CDRs by rating/sector; average muni recovery ~67% vs
    ~47% corporate senior unsecured (mirrored freely by fund managers).
  → Together: through-the-cycle PD term structures, transition matrices, and seniority-level LGD priors
  at zero cost. The paid DRD/CreditPro become "nice to have" for prototyping.
- **NUS Credit Research Initiative (nuscri.org)** — daily point-in-time PDs for **90,000+ listed firms
  worldwide** (1M–5Y horizons), actuarial spreads, corporate default event database. Free with
  credentials, **non-commercial**. **Covers India properly.** Consistently overlooked.
- **ratingshistory.info** — free CSV conversions of SEC Rule 17g-7(b) NRSRO rating-history XBRL files
  (Moody's, Fitch, DBRS, KBRA, JCR, Egan-Jones… corporates through structured finance, from 2010,
  ~1-year lag). → Build your own transition matrices / rating-based PD term structures.
- **SEC EDGAR XBRL financial statements** + **Federal Judicial Center Integrated Database** /
  **Florida-UCLA-LoPucki BRD** (bankruptcy events) → an Altman-style corporate scorecard end-to-end, free.
- **Credit Benchmark** — consensus PDs pooled from 40+ banks' internal ratings (120k+ entities, ~90%
  otherwise unrated). **Free layer:** monthly Credit Consensus Indicators, sector/geography reports.
  Entity-level feed is paid. → Direction-of-travel monitoring for unrated wholesale segments.
- **Published Y-14 revolver research as EAD/CCF anchors** — "The Credit Line Channel" (Chodorow-Reich et
  al.), NY Fed Staff Report 942 (utilization by firm size), Boston Fed 2026 revolving-lines paper,
  Moody's "Corporate Credit Lines: Usage and Exposures at Default" — free papers carrying the utilization/
  drawdown statistics you cannot get as micro data.

### 2.7 Emerging markets — GEMs Risk Database (+ EIB sovereign)

**Global Emerging Markets Risk Database Consortium** (25 MDBs/DFIs) — publishing detailed statistics
since Oct 2024, expanded **7 Oct 2025** (`gemsriskdatabase.org/statistics`): **default rates AND recovery
rates by counterpart type, region, sector, seniority, time period, from 1994.** Anchors: private
counterparts avg default rate **3.54%** with avg recovery **72.9%**; public/sovereign-adjacent entities
default 2.61%, recovery 85.8%. Companion: **EIB default & recovery statistics for sovereign and
sovereign-guaranteed lending 1994–2024** (free PDF).
→ The only credible free EM-specific **recovery** benchmark in existence. For any India/EM prototype,
this is your LGD prior.

### 2.8 Trade finance — ICC Trade Register

$25.7tn+ of pooled transactions; **default rates AND LGD/recovery by product** (import/export LCs,
guarantees, trade loans, SCF) and region. Free summary; full tables paid. → The only public source for
product-specific PD *and* LGD in short-tenor trade products.

### 2.9 Sovereign

**BoC–BoE Sovereign Default Database** — free, annual (2025 edition Oct 2025), 1960 onward, by country
and instrument class. Pair with **Cruces–Trebesch haircuts** for sovereign LGD, and the EIB sovereign
recovery stats (§2.7).

### 2.10 Global microfinance — the MIX Market archive

**MIX Market data, now hosted on the World Bank Data Catalog (CC BY 4.0)** — MFI-level panel
**1999–2019, 100+ countries**: portfolio quality (**PAR30/PAR90, write-off ratio**), full financials,
social indicators. Frozen (last updated Dec 2020) but free and clean.
→ EM microfinance PAR→write-off roll-rate priors; the global complement to India's MFIN/CRIF trackers.

### 2.11 Niche portfolios — equipment, agriculture, project finance (added after coverage audit)

- **Equipment finance:** **ELFA MLFI-25** — monthly index from ~25 large US equipment lessors/lenders:
  new business volume, **receivables aging (31–60/61–90/90+), average charge-offs, approval rates**.
  Free monthly releases; ELFA's annual SEFA survey adds structure. **Equifax (ex-PayNet) Small Business
  Lending / Delinquency / Default Indices** — monthly US small-business term-loan-and-lease delinquency
  (31–90) and default indices, by industry and state; free summary releases. → The only public
  delinquency series for the equipment/small-ticket commercial asset class.
- **Agricultural credit:** **Kansas City Fed Ag Credit Survey + Ag Finance Databook** (quarterly farm
  loan repayment-rate indices, land values), **Farm Credit Administration/FCS quarterly information
  statements** (nonaccrual by loan type for the Farm Credit System), and ag-production-loan charge-off
  series in the Fed/FDIC data. India: agriculture GNPA runs through FSR sector tables (~5.1%, the worst
  sector), NABARD reporting, and KCC data in parliamentary answers.
- **Project finance / infrastructure:** **Moody's "Default and Recovery Rates for Project Finance Bank
  Loans"** (annual consortium study, data from 1983) — marginal default rates that decline with seasoning
  and **average ultimate recoveries around 80%**, i.e. senior-secured-like; access like the other Moody's
  studies (registration/mirrors). **GEMs** sector cuts cover EM infrastructure. → A genuinely distinct
  low-default portfolio with its own seasoning profile; relevant to Indian infra lending debates.

_(The §2.11 sources are long-stable publications known to the compiler but not re-verified in the
July 2026 pass — check current editions before load-bearing use.)_

---

## 3. Global — aggregate and benchmark data (free, and better than people assume)

These are your **calibration anchors**. For stress testing and ECL benchmarking they are the *primary*
source, not second-best.

### 3.1 EBA / ECB — the richest regulatory disclosure in the world, now machine-readable

- **EBA Pillar 3 Data Hub (P3DH) — live 26 Jan 2026.** Centralises Pillar 3 disclosures of large and
  other EU institutions in **machine-readable XBRL-CSV**, with a visualisation tool and **bulk downloads**;
  full data for Jun/Sep/Dec-2025 reference dates available by ~mid-2026, quarterly onward.
  → **Template EU CR6** (IRB: EAD-weighted avg PD, LGD, RW, EL by exposure class × PD band, per bank,
  semi-annual) from one endpoint. The cross-bank IRB parameter panel that used to require PDF-scraping
  is now a download. This is the single most important new source in v2.
- **EU-wide Stress Test 2025**: 64 banks, 17 countries, ~75% of EU bank assets; bank-by-bank baseline and
  adverse results as **three CSVs (Credit Risk IRB, STA/SEC, Other)** — exposure, PD, LGD and stage
  allocation by country/portfolio/bank. A ready-made, labelled benchmark table.
- **EU-wide Transparency Exercise** — Dec 2025 edition: **119 banks, 25 countries, four reference dates
  to Jun-2025**; capital, RWA, sovereign exposures, **asset quality incl. IFRS 9 stage allocation and
  coverage**, with new interactive tools. The workhorse bank-level dataset.
- **EBA Credit Risk Benchmarking Exercise** (2025 exercise, report June 2026) — **EAD-weighted average
  PD, LGD, CCF, RW by IRB asset class across EU banks**, quantifying dispersion for identical benchmark
  portfolios. The closest thing to a published answer to "what is a reasonable PD/LGD for portfolio X?".
  (Note: this — not the BCBS Basel III Monitoring Report — is where IRB parameter averages live.)
- **EBA Risk Dashboard** (quarterly) — NPL ratio, **Stage 2 share** (Q1 2026: corporates 12.8%,
  households 8.5%), coverage, cost of risk by country; PDF + interactive Excel + a risk-parameter annex
  with IRB PD/LGD aggregates.
- **ECB Supervisory Banking Statistics** (quarterly, CSV via ECB Data Portal) — significant institutions'
  **Stage 1/2/3 shares and coverage ratios by country and bank size class**. → IFRS 9 stage-migration
  benchmarks on a quarterly cadence.
- **EBA IFRS 9 monitoring reports** — SICR practices, ECL model design, PD definitions, backtesting:
  a free ECL methodology handbook.

### 3.2 US Federal Reserve system + agencies

- **DFAST/CCAR results** — projected losses by portfolio, per bank, per scenario (2026: ~$708bn total,
  ~$200bn card, ~$160bn C&I, ~$75bn CRE). Divide by balances → **implied stressed loss rates by portfolio**.
- **Supervisory scenarios** — annual baseline/severely-adverse macro paths (domestic + international),
  free download; ready-made stress inputs.
- **Philadelphia Fed "Large Bank Credit Card and Mortgage Data" (new in v2)** — quarterly public
  aggregates **from FR Y-14M** (banks ≥$100bn; ~4/5 of US card balances): card balances, originations and
  score mix, **utilization, share paying minimum vs full, delinquency**, mortgage origination LTV/DTI/score
  cuts and performance — **history to 2012, expanded Jul 2025 with 67 new series, CSV + FRED mirrors**.
  → The best public EAD/utilization/payment-rate anchor in existence.
- **Charge-Off and Delinquency Rates** (quarterly since 1985, by loan type and bank size; 264 FRED series)
  — the best free time series for fitting PD/LGD-to-macro satellite models.
- **FFIEC Call Reports** (RC-C, RC-N past due, RI-B charge-offs **and recoveries**) — bank-level,
  quarterly, every US bank. **NCUA call reports** — same for every credit union (quarterly bulk ZIPs,
  delinquency + charge-offs by loan type). **FDIC BankFind Suite API** — no-auth REST for bank-level
  financials; Quarterly Banking Profile for aggregates.
- **NY Fed Household Debt & Credit / Consumer Credit Panel** — quarterly transition-into-delinquency
  rates by product (aggregate free; micro restricted).
- **CFPB** — Consumer Credit Trends dashboards (originations by score tier, updated through Dec 2025 data)
  and the biennial **CARD Act / Consumer Credit Card Market report** (2025 edition, Dec 2025):
  **utilization, payment rates and credit-line-increase (CLIP) statistics by score tier** (15% of GP
  cardholders minimum-paying — highest since 2015). Public domain.
- **FR Y-14M/Q instructions** (public) — the schema for what a bank credit system must hold (§6).
- **OCC Mortgage Metrics**; **Federal Student Aid Data Center** — cohort default rates, portfolio by
  delinquency status, and (since Jul 2025) institution-level nonpayment rates.

### 3.3 Wholesale LGD/EAD — consortium and national sources

- **Global Credit Data (GCD)** — bank-owned consortium, 50+ members; **100k+ defaulted facilities,
  €200bn+, all Basel classes, from 2000**. **Membership rules (verified Jul 2026): only Basel-compliant
  financial institutions may join; strict give-to-get (you must contribute your own default data, vetted
  by a quality assessment before the board approves membership). There is no purchase option and no
  consultant tier — the raw database is unobtainable for non-lenders, full stop.** What non-members get:
  the **free library** (LGD Report: unsecured LGD ~27%, secured ~22%, senior 26% vs subordinated 38%,
  median time-to-recovery ~1.2y; downturn-LGD studies; EAD/CCF summaries; 2026 additions incl. an
  Aircraft recovery-rate report and a Funds peer-benchmarking report; platform documentation = a free
  wholesale default-data schema), plus **academic collaboration** (GCD supports vetted research and
  maintains a Scholar profile of papers built on its data — those papers publish coefficients and
  distribution fits you can mine). If you work with a bank, membership is the single highest-value
  credit-data action available — and for Indian banks facing ECL-2027, joining GCD is an obvious move.
- **Banca d'Italia bad-loan recovery rates (new in v2)** — "Notes on Financial Stability and Supervision"
  No. 48 (Dec 2025): Central-Credit-Register-based **recovery-rate time series from 2006**: 2024 average
  **41%** (secured 44%, unsecured 37%); **sale vs workout split** (NPL sale prices: sofferenze 24% of GBV
  vs 51% for other NPE); closure-time profiles; **Excel appendix**. → The only true public workout-LGD
  time series; evidence for downturn-LGD and sale-discount assumptions.
- **Japan CRD Association** — pooled SME financials + default flags (largest SME credit database in
  Japan, est. 2001); membership-gated with sample-data service; the Japanese analogue of GCD and the
  reference design for SME data pooling.
- **ECBC Covered Bond Label — Harmonised Transparency Templates** — free, no login: per-programme
  quarterly Excel with cover-pool composition, **indexed LTV distributions, arrears buckets, seasoning,
  regional splits**. → Mortgage pool stratification where no loan-level RMBS exists.

### 3.4 UK

- **BoE Bank Capital Stress Test 2025** — results published 2 Dec 2025: aggregate **and individual-bank**
  outcomes for 7 banks incl. impairment drivers; scenario paths downloadable. Now biennial (2026 expected
  desk-based/aggregate-only). → Scenario-design template + stressed impairment benchmarks.
- **FCA Product Sales Data** — loan-level mortgage sales + performance collected since 2005; public
  output is aggregate tables/dashboards; no standing external research-access program.

### 3.5 EM open-data comparators (what "good" looks like, and benchmarking material)

- **Brazil — Banco Central do Brasil. The world benchmark.** Free REST APIs, no key:
  **SGS** time series (e.g. 90-dpd delinquency: total 21082, corporate 21083, household 21084; small-firm
  26426) and **SCR.data** — **~700,000 monthly series aggregated from the loan-level SCR credit register,
  Jun 2012–present**: delinquency by product × state × borrower type × institution segment. Plus IF.data
  per-institution quarterly reports. `python-bcb` package exists.
  → Prototype full PD/roll-rate pipelines on real EM data end-to-end; the concrete exhibit for what an
  Indian public credit-register data product could be.
- **Mexico CNBV** — monthly per-bank cartera/IMOR (NPL) by product (bank-level dispersion data).
- **Peru SBS / Chile CMF / Colombia SFC** — monthly per-bank delinquency by segment (Spanish portals).
- **Turkey BDDK** — monthly bulletin in English + province-level FinTürk; **Indonesia OJK** — monthly
  banking statistics, bilingual, NPL by economic sector; **Philippines BSP** — monthly loan-quality tables.
- **South Africa** — SARB **BA900** returns publicly downloadable **per bank** monthly (balance-sheet
  granularity; BA200 credit-risk returns are aggregate-only); **NCR Consumer Credit Market Report +
  Credit Bureau Monitor** — quarterly consumer arrears by product and bucket from bureau data.
- **Kenya CBK** — annual bank supervision report (NPL by sector).

### 3.6 Cross-country benchmark layers

- **IMF Financial Soundness Indicators** — NPL, provisions/NPL, capital, sectoral loan splits, 100+
  countries (India included, quarterly); new data.imf.org portal with free SDMX APIs.
- **OECD "Financing SMEs and Entrepreneurs 2026"** (Mar 2026) — SME lending terms and **SME NPL rates
  ~50 countries** to 2024. → SME benchmark corridor for MSME work.
- **BIS Data Portal** — credit to non-financial sector, **credit-to-GDP gaps** (EWI), debt-service
  ratios; free CSV/SDMX/bulk. **World Bank GFDD** — 108 indicators to 2021 (stale but structured).
- **World Bank Doing Business "Resolving Insolvency" archive** — still downloadable: **recovery rate
  (cents on dollar), time, cost by country** through May 2019 (discontinued 2021); successor **B-READY**
  (2025: 101 economies) scores insolvency frameworks but no cents-on-dollar rate.
  → Cross-country LGD priors + regime-quality adjustment.
- **Laeven & Valencia Systemic Banking Crises Database — 2026 update (IMF WP 2026/094, through 2025)** —
  per-crisis dates, fiscal costs, output losses, **peak NPL ratios** (median ≈11% advanced, ≈30%
  low/middle-income). → The defensible tail-severity anchor for ICAAP/stress calibration.
  (**ESRB European financial crises database** for EU episode dating.)

### 3.7 Scenario libraries

- **Fed supervisory scenarios** (annual macro paths), **EBA stress-test scenarios**, **BoE key-elements
  scenario downloads**, **RBI FSR macro-scenario annex** (India — §4.4).
- **NGFS climate scenarios** — current long-term vintage **Phase V (Nov 2024)** + first **short-term
  scenarios (May 2025, 5-year horizon, country/sector-granular)**; free via the NGFS portal (IIASA/CIE
  explorers). **Phase VI lands end-2026 with overhauled physical-risk methodology** — time climate-stress
  work accordingly.

### 3.8 Commercial vendors and the academic route (know what they are, so you can decide against them)

| Vendor / route | What it uniquely gives | Note |
|---|---|---|
| **Moody's DRD** | 850k+ debts, 60k+ entities, ratings to 1919, recoveries to 1920, **ultimate recovery** | Check **university library / WRDS** access before paying (hosted for licensing institutions; not in every school's bundle) |
| **S&P CreditPro / LossStats** | Default, transition and ultimate recovery by instrument/seniority/collateral | The reference for wholesale LGD by seniority — but the free annual studies (§2.6) carry the headline tables |
| **WRDS (academic)** | CRSP+Compustat (structural PD), **Mergent FISD** (140k+ bond issues, ratings histories, defaults), sometimes CoreLogic | McDash is *not* a standard WRDS product |
| **Moody's Orbis / BvD** | Global **private company** financials + insolvency flags | The realistic route to private-company (incl. Indian) scorecards at scale |
| **Credit Benchmark** | Bank-consensus PDs for 120k+ mostly-unrated entities | Free monthly aggregate indicators; entity feed paid |
| **Refinitiv/LSEG LPC, Trepp, Intex, PitchBook LCD** | Leveraged loans, CRE, deal cashflows | LSTA/LCD publish free monthly default-rate summaries (~1.4% Mar 2026) |
| **CMIE Prowess (India)** | Indian corporate financials panel | Commonly available via Indian academic institutions |

---

## 4. India — what actually exists

India still has **no public loan-level credit data of consequence** — CRILC is supervisory-only, the
Public Credit Registry never materialised, bureau micro data is access-controlled, and RBI (verified)
runs **no external research-access program** for supervisory microdata (DRG studies are collaborations
where data stays inside RBI). **But the layer below "loan-level" is much richer than assumed — and v2
found genuinely micro-level material in five places: IBBI case-level recoveries, CIC defaulter
registries, entity-level rating/default histories, one real hackathon loan tape, and P2P disclosures.**

### 4.1 The regulatory clock (context for everything else)

- **ECL Directions (final, 27 Apr 2026 → effective 1 Apr 2027):** three-stage ECL with PD/LGD/EAD models,
  30-dpd SICR presumption, floors (~0.40% Stage 1 / ~5% Stage 2), glide path to FY2031; commercial banks
  excl. SFBs/PBs/LABs. **Basel III SA capital directions** same dates. NBFCs stay on Ind AS 109 (their
  IRACP/credit-risk directions were amended, not replaced, Apr 2026).
- **Model risk:** draft **Guidance on Model Risk Management, 24 Jun 2026** (board MRMF, inventory/tiering,
  independent validation, AI/ML in scope; comments closed Jul 2026). The Aug 2024 credit-model-risk
  circular was never finalized. No final framework in force yet — but validation-first design is where
  the puck is going.
- **Climate:** disclosure framework still draft (Feb 2024); scenario-analysis guidance still in
  development; **RB-CRIS** (climate risk information system) is the shipped artifact. NGFS scenarios are
  the de-facto standard meanwhile.
- **Account Aggregator:** ~24 crore cumulative consents, 179 FIPs / 748 FIUs, ₹1.07 lakh crore of
  AA-enabled lending in FY25 alone (consent volume roughly doubling yearly) — the future cash-flow-based
  underwriting rail, though not a research dataset.

### 4.2 Corporate default, recovery and LGD — India's strongest suit (and now genuinely micro)

**Recovery / LGD:**

- **IBBI quarterly newsletters (the standout find of v2)** — beyond the headline stats (cumulative to
  Mar 2026: realisation **30.6% of admitted claims**, **166.9% of liquidation value**, **94.6% of fair
  value**; 1,419 resolutions vs 3,003 liquidation referrals; closed liquidations averaging ~691 days;
  200 mega-cases holding ₹12.2 lakh cr of claims against ₹2.2 lakh cr realisable), **each newsletter's
  "Table 5: CIRPs Yielding Resolution Plans" lists every resolved corporate debtor BY NAME with admitted
  claims, liquidation value, fair value, realisable amount, %-realisation ratios, commencement/approval
  dates and defunct status** (plus name-wise voluntary-liquidation tables).
  → **Scrape the quarterly PDFs (pdfplumber/camelot) and you hold a ~1,400-case Indian corporate LGD
  dataset with workout durations — India's only public workout-LGD micro data.** Realisation ratios
  drift by cutoff (33.7% Jun-25 → 30.6% Mar-26): cite the quarter.
- **RBI Report on Trend & Progress of Banking (Dec 2025)** — the **recovery-by-channel table**: FY25
  IBC ~**37%** (up from 28.3%), SARFAESI **31.5%**, DRTs, Lok Adalats **2.4%** (on ₹1.98 lakh cr
  referred); IBC+SARFAESI >80% of amount recovered. → Channel-conditional LGD structure — recovery
  depends on enforcement route, which an imported LGD model would miss.
- **ARC / security receipts** — CRISIL's SR study (Jun 2025): cumulative SR recovery ~65–70% (FY25E)
  → 75–80% (FY26E); retail SR redemption ~69–71%; RBI T&P carries official ARC tables. → Secondary-market
  distressed recovery priors.
- **CGTMSE annual reports** — MSME credit-guarantee scheme: guarantees approved (₹64,142 cr FY25),
  **claims lodged/settled by year, scheme and state** (mirrored on the MSME Dashboard). → Claims-settled ÷
  guarantees ≈ realized MSME default-cost proxy by state/vintage.

**Default events / PD:**

- **The four CIC public defaulter registries** (RBI Master Direction on Wilful & Large Defaulters,
  Jul 2024, effective Nov 2024: **large defaulters ≥₹1 cr suit-filed and wilful defaulters ≥₹25 lakh**,
  reported monthly by all lenders to all four CICs, publicly disseminated):
  **CIBIL** (suit.cibil.com — search-only, bot-hostile), **Experian** (suit.experian.in — the most
  automation-tolerant: search by entity, director DIN/PAN, guarantor, state, lender), **CRIF**, Equifax.
  Borrower name, directors, bank/branch, outstanding, quarter. Search-only (no bulk), but this IS public
  borrower-level default data for Indian corporates.
- **NeSL (IBC information utility) quarterly newsletters** — **contractual default incidence by debt-size
  band and segment** from authenticated Record-of-Default data (e.g., corporate defaults ~3.75% of
  corporate debt; the highest-incidence band migrating from ₹10–100 cr in FY24 to ₹100–1,000 cr in FY25).
  → The only India-wide default-rate curve by ticket size that is independent of NPA accounting.
- **Entity-level rating/default corpus (corrected route):** CRA default studies do **not** name
  defaulters — instead use the SEBI-mandated half-yearly website disclosures on every CRA's regulatory
  page: **Annexure V (full rating history of all outstanding securities, Excel)** and **Annexure VI
  (list of defaults by rating category)**, with 10-year archives, across CRISIL/ICRA/CARE/India
  Ratings/Acuité/Brickwork/Infomerics. Since **Aug 2025, NSE and BSE auto-publish daily prescribed-format
  Excel rating-action feeds from all CRAs** (including downgrades to D) — a machine-readable daily feed.
  Add **Reg 57 LODR intimations** (listed-debt issuers must certify interest/principal payment status
  within one working day of each due date; filed as exchange announcements, scrapeable) and the **NSDL
  indiabondinfo corporate bond database** (per-ISIN terms + rating details, free) for the bond leg.
  → **An issuer-level Indian default-event and rating-migration panel is assemblable entirely from
  public sources.** Labour-intensive, unique, and increasingly automated thanks to the Aug 2025 feeds.
- **CRA default & transition studies** (annual, free PDFs, all SEBI-registered CRAs) — 1/2/3-year CDRs
  and transition matrices by rating category (CRISIL FY25: ~40pp incl. structured-finance and retail
  ABS/MBS transitions; methodologically strongest — monthly static pools). Cross-CRA comparison is
  itself informative (scale-calibration differences are large).

### 4.3 Retail and MSME portfolio benchmarks — bureau and industry publications

All free PDFs, quarterly or annual (current editions verified Jul 2026):

| Publication | Publisher | Latest verified | What you get |
|---|---|---|---|
| **Credit Market Indicator** | TransUnion CIBIL | Mar 2026 (Jun 2026 landing live) | CMI 102 (vs 97 YoY); delinquency by product and risk tier; home-loan delinquency ~0.7–0.8% |
| **MSME Pulse** | SIDBI × TU CIBIL | Jul 2026 | Commercial credit <₹50 cr (₹35.2 lakh cr); NPA/delinquency by ticket size, segment, lender type, CMR tier |
| **How India Lends** | CRIF High Mark | May 2026 (FY26 data) | Originations ₹11.8 lakh cr (+12.3%); portfolio + delinquency (PAR) by product and ticket size; **retail PAR 3.1% vs 3.6% YoY** |
| **MicroLend** (+ monthly Lite) | CRIF High Mark | May 2026 Lite | Microfinance GLP ₹3.33 lakh cr; PAR 1-30 0.6%, PAR 91-180 0.9%; state/district cuts in quarterly editions |
| **Micrometer** | MFIN | 57th ed., Q4 FY26 | GLP ₹3.25 lakh cr (+3% QoQ, first growth in ~7 quarters); **PAR 31-180 = 2.0% vs 6.3% a year earlier** |
| **Microfinance Pulse** | SIDBI × Equifax | Vol XXVII, Jun 2026 | MFI delinquency 6.64% (Mar-25) → 2.35% (Mar-26); disbursement and ticket-size trends |
| **Bharat Microfinance Report** | Sa-Dhan (+NABARD) | 2025 (FY25 data) | PAR30+ 6.2% (from 2.1%), PAR90+ 4.8%; state-wise; GLP perimeter differs from MFIN — note when mixing |
| **Fintech Personal Loans** (quarterly) | FACE (SRO-FT) | Mar 2025 data verified | Digital-lender PL delinquency: **90+ DPD 3.6%**, tier-3 4.2%, rural 4.1%, young-vintage 6.5% |
| **Status of Microfinance in India** | NABARD | FY24 (FY25 unconfirmed) | SHG-Bank-Linkage: **SHG NPA 2.12%** with state/agency tables |

→ Together: an India retail/MSME risk surface across product × ticket size × state × vintage — enough to
calibrate a synthetic retail book. **The microfinance series is a rare gift: four independent trackers
documenting a full credit cycle (benign 2023 → sharp deterioration 2024-25 → recovery by Mar 2026) at
state level** — exactly what stress testing and SICR-trigger demonstrations need.

### 4.4 System-level, stress testing and geographic data — RBI and beyond

- **Financial Stability Report (Jun 2026)** — macro stress tests: SCB GNPA **1.8% (Mar 2026,
  multi-decadal low)**, baseline ~1.9% by Mar 2028, adverse scenarios pushing GNPA toward ~4% and system
  CRAR from 17.7% to ~13.0% (severe); bank-group-wise and **sector-wise GNPA** (agriculture worst ~5.1%);
  NBFC stress section (174 NBFCs); **large-borrower (CRILC-derived) chapter: large-borrower GNPA 1.2%,
  SMA-0/1/2 distributions (PSB retail SMA share 9.4% Mar 2026), top-borrower concentration** — the
  closest public thing to stage-migration data for India; **macro-scenario annex with baseline/adverse
  GDP-inflation-rates paths** (use as stress-test validation targets: if your severe scenario doesn't
  land near RBI's adverse range, recalibrate).
- **Report on Trend & Progress of Banking** — annual: NPA movement, slippage, provision coverage,
  sector/bank-group cuts, recovery channels (GNPA 2.2% Mar-25 / 2.1% Sep-25 per Dec-2025 edition).
- **RBI DBIE/CIMS (data.rbi.org.in)** — confirmed live: quarterly **BSR-1** (credit by occupation,
  organisation, **district**, **interest-rate bucket** — the closest India has to public risk-based
  pricing data), monthly **sectoral deployment**, annual **bank-wise Statistical Tables**. No quarterly
  bank-wise asset quality (that stays in FSR/T&P aggregates). Note: rbidocs PDFs are bot-gated —
  script against data.rbi.org.in or download manually.
- **data.gov.in + parliamentary questions** — bank-wise PSB NPA recovery (2019-20—2024-25,
  machine-readable), write-off disclosures (**₹8.9 lakh cr written off over 5 years + H1 FY26**;
  ₹12.08 lakh cr FY16–FY25), wilful-defaulter aggregates (2,100+ owing ₹1.76 lakh cr, Jun 2025). PQ
  annexures on eparlib.sansad.in often carry bank-wise tables RBI doesn't publish elsewhere.
- **SLBC minutes (hidden geographic dataset)** — verified for **Kerala, Punjab, West Bengal**: agenda/
  minutes PDFs carry **district-wise and bank-wise NPA, recovery-certificate and SARFAESI-case tables**.
  → District-level NPA panels available nowhere else publicly; pair with BSR-1 district credit for
  a geographic risk surface.
- **NAFSCOB** — annual state-wise NPA and recovery ratios for StCBs/DCCBs/PACS (co-operative sector).
- **NHB** — **RESIDEX** (official housing price index, 50+ cities, quarterly — the collateral-value
  input for Indian mortgage LGD) and **Report on Trend & Progress of Housing in India** (Feb 2026
  edition: HFC GNPA 2.32% Mar-24; individual housing loans o/s ₹33.5 lakh cr).

### 4.5 The NBFC ECL panel — proven feasible (the most under-exploited India source)

NBFCs have run Ind AS 109 ECL since FY2018-19; their annual reports disclose **Stage 1/2/3 gross
exposure and ECL allowance by product, stage-movement reconciliations, SICR criteria and (variably)
PD/LGD assumptions and macro scenario weights**. Verified concrete examples:

- **Bajaj Finance** — FY25 GNPA 0.96%/NNPA 0.44%, Stage-3 PCR 54% → FY26 GNPA 1.01%, PCR 60%; disclosed
  a one-time **ECL model-update provision of ₹359 cr** (a visible model-recalibration event).
- **Cholamandalam** — Gross Stage 3 2.81% (Mar 2025) vs RBI-norm GNPA 3.97% (the Ind AS-vs-IRACP gap in
  one line); publishes a **standalone public ECL methodology document with segment-wise PD term
  structures and LGDs** — a unique calibration artifact.
- **Shriram Finance** — Gross Stage 3 4.55% / Net 2.64% (Mar 2025), down from 6.98%/4.03% in 2021 —
  a full stage-3 cycle in one lender.

→ **Scraping the ECL notes of the top 40–50 NBFCs' annual reports gives a real, India-specific,
product-level PD/LGD/stage-coverage panel across 7+ years.** Nobody has assembled this publicly. With
the Apr 2027 bank ECL deadline, its value is about to spike — it is the only India ECL calibration set
that exists.

### 4.6 Securitisation pool performance

No loan-level disclosure in India, but **CRISIL/ICRA/India Ratings/CARE surveillance rationales for PTC
transactions are free** and carry **cumulative collection efficiency, 90+/180+ dpd, credit-enhancement
utilisation and amortisation per pool** (consolidated tracker reports are paid; the rationales are not).
Securitisation volumes hit **₹2.55 lakh cr in FY26** (projected ₹2.6–2.7 lakh cr FY27), so the sample
keeps growing. → Scrape rationales into a pool-performance panel: real Indian retail vintage performance
by originator and asset class.

### 4.7 Corporate financials and scorecard inputs

- **CMIE Prowess** — the standard panel; usually accessible via Indian academic institutions.
- **MCA V3** — free company master data; financial statements (AOC-4/XBRL) at ₹100/company/year; no
  confirmed current bulk product (resellers: Probe42, Tofler, Zaubacorp). **screener.in** for listed-co
  financials (Excel export on the paid tier); exchange XBRL filings free per company.
- **NUS-CRI** daily PDs cover Indian listed firms — the fastest free India corporate PD benchmark.
- Combine **MCA/exchange financials + Annexure VI default labels + CIC registry names + IBBI outcomes**
  → an Indian corporate scorecard/LGD dataset assembled entirely from public parts (§7.3).

### 4.8 India loan-level micro data that actually exists (short list, but not empty)

- **LTFS "FinHack 1" vehicle-loan dataset (2019, Kaggle mirrors live)** — **~233k Indian vehicle loans,
  ~40 fields: demographics, disbursal/LTV/EMI, CIBIL bureau score and bureau history, first-EMI default
  label.** The reference (and essentially only) real Indian retail application-scorecard dataset.
  **FinHack 3** (2021) adds bureau behavioural tables (balances, overdues, DPD strings) under a top-up
  cross-sell label; FinHack 2 is volume forecasting, not credit. (AV login or GitHub solution repos for
  files.) Verify licensing before anything commercial.
- **NBFC-P2P mandatory monthly disclosures** — RBI Master Direction requires every NBFC-P2P to publish
  monthly portfolio performance **including NPAs by age and all lender losses**: LenDenClub factsheets
  (90+dpd NPA, monthly PDFs), Faircent registration-vintage NPA pages. No standard format, but a
  scrapeable monthly unsecured-consumer risk series across platforms.

---

## 5. Coverage map — where the real gaps are

Legend: ●●● abundant free micro data · ●● usable free aggregates/partial micro · ● thin / proxy only · ○ effectively nothing public

| Portfolio | | PD | LGD | EAD/CCF | Scorecard inputs | Stress/macro |
|---|---|---|---|---|---|---|
| **Mortgage** | Global | ●●● | ●●● | n/a | ●● | ●●● |
| | India | ●● | ● (RESIDEX helps) | n/a | ○ | ●● |
| **Auto / vehicle** | Global | ●●● | ●●● | n/a | ●●● | ●●● |
| | India | ●● | ● | n/a | ● (LTFS) | ●● |
| **Cards / revolving** | Global | ●● | ● | **●●** (Philly Fed/CFPB/trusts) | ●● (Amex panel) | ●●● |
| | India | ●● | ○ | ○ | ○ | ●● |
| **Personal / unsecured** | Global | ●●● | ●● (Bondora) | n/a | ●●● | ●●● |
| | India | ●● (+P2P monthly) | ○ | n/a | ○ | ●● |
| **Microfinance** | Global | ●● (MIX archive) | ○ | n/a | ● | ● |
| | India | ●●● (agg., 4 trackers) | ● | n/a | ○ | ●●● |
| **SME / MSME** | Global | ●● | ●● (SBA) | ● | ● | ●● |
| | India | ●● | ● (CGTMSE proxy) | ○ | ○ | ●● |
| **Corporate / wholesale** | Global | ●●● | ●● (GCD/BdI/studies) | ● (Y-14 papers) | ●● | ●●● |
| | India | ●● (labels assemblable) | **●●●** (IBBI case-level) | ○ | ● | ●● |
| **CRE** | Global | ●●● | ●● | n/a | ●● | ●●● |
| | India | ● | ● | n/a | ○ | ● |
| **Trade finance** | Global | ●● | ●● (ICC) | ● | ○ | ● |
| **Sovereign / EM** | Global | ●● | ●● (GEMs, BoC-BoE, EIB) | n/a | ●● | ●● |

**The three hardest cells, updated:**
1. **EAD/CCF micro data anywhere.** Still never published as micro data — but v2 downgrades this from
   "impossible" to "anchor-able": Philly Fed utilization-by-score-band, CFPB payment-rate tiers, master-
   trust payment rates, and published Y-14 revolver studies give calibration targets. True limit histories
   still require GCD membership or a bank partnership.
2. **India retail scorecard-level applicant attributes.** LTFS is the lone real dataset; Home Credit
   (2018/2024) remains the least-bad structural proxy. No path to more without a lender partnership.
3. **Corporate/SME LGD outside formal insolvency.** IBBI/GEMs/Banca d'Italia cover resolution and
   registered workouts; restructured-but-never-insolvent recoveries remain dark everywhere.

### 5.1 Portfolio playbooks — exactly how each book is covered

**Credit cards / revolving.** No public loan-level anywhere (cards were exempted from ABS-EE asset-level
rules). Micro proxy: the **Amex Kaggle panel** — 459k customers × monthly statements, 190 anonymized
delinquency/spend/payment/balance/risk features → behavioural PD and utilization-path models (anonymized,
so no application semantics). Pool-level: **master-trust 10-Ds** (Chase, Citi, Capital One, Amex —
monthly charge-off, 30–180+ buckets, principal payment rate, yield; 20+ years through two crises) →
vintage/stress curves. EAD/CCF: **Philly Fed Y-14M aggregates** (utilization and min-pay share by score
band since 2012) + **CFPB CARD Act** utilization/CLIP tiers. Macro satellite: Fed card charge-off series
since 1985. **India:** CMI delinquency by risk tier, RBI sectoral card outstandings, data.gov.in card
GNPA series — aggregates only. *Buildable: behavioural PD, roll-rate stress engine, ECL with
Philly-Fed-anchored CCF; not buildable: application scorecard on real card data.*

**Personal / unsecured consumer.** Micro: **LendingClub** (2.2M+ loans incl. rejects → application
scorecard + reject inference), **Bondora/Go&Grow** (recovery cashflows → workout LGD and cure models),
**Home Credit 2018/2024** (EM application + stability testbed), Berka. Anchors: NY Fed transitions,
Fed consumer charge-offs, EBA Stage-2/NPL. **India:** FACE fintech-PL 90+dpd (by tier/geography), CIBIL
CMI PL tiers, CRIF PAR by product/ticket, **NBFC-P2P monthly NPA disclosures** (only public India
unsecured performance series), LTFS FinHack-3 bureau tables. *Buildable end-to-end globally; India =
synthetic book anchored to CMI/FACE/P2P with Home Credit dependence structure.*

**Mortgage / housing.** The best-served book on earth: **Freddie SFLLD + Fannie SFLPD** (~55M loans,
monthly panels, expenses and proceeds → PD, LGD, prepayment, cure, modification outcomes), Ginnie
(government credit box), GSE multifamily, EU covered-bond HTTs (pool LTV/arrears strata), EDW (paid).
Anchors: DFAST loss rates, EBA IRB mortgage PD/LGD by country, OCC metrics; FHFA HPI to ZIP level for
collateral paths. **India:** no loan-level; NHB T&P (HFC GNPA 2.32% Mar-24, segment cuts), **RESIDEX**
(city HPI for LGD stress), CMI home-loan delinquency (~0.7–0.8%), CRIF home/LAP PAR by ticket, MBS pool
rationales (CCE, 90+dpd). *Buildable: the full reference PD/LGD/prepayment/lifetime-ECL pipeline on
Freddie; India book synthesized against NHB/CMI/CRIF with RESIDEX-driven LGD.*

**Auto / vehicle.** Micro: **auto ABS-EE** (obligor score, income/DTI verification flags, LTV, monthly
status, charge-off AND recovery amounts, repo/liquidation proceeds → full PD+LGD with recovery timing);
**India actually has micro here: LTFS FinHack-1** (233k vehicle loans, CIBIL fields, first-EMI default).
Anchors: Manheim used-vehicle index (collateral), Fed charge-offs; India: CRIF auto/2W/CV PAR by
ticket/state, **CV/car PTC pool rationales** (the deepest Indian securitisation segment), CV-heavy NBFC
ECL notes (Shriram, Chola, M&M Finance). *Buildable: everything, both geographies — the strongest
portfolio for an India-relevant end-to-end demo.*

**Corporate / wholesale.** PD & migration: rating corpora (17g-7/ratingshistory; **India: Annexure V/VI
+ daily NSE/BSE rating feeds + Reg 57 + CIC defaulter registries + NeSL incidence**), free S&P/Moody's
annual studies (TTC term structures), NUS-CRI daily PIT PDs (incl. India), EDGAR XBRL + bankruptcy DBs
for Altman/Merton scorecards, Credit Benchmark for unrated segments. LGD: **IBBI Table 5 case-level
(India)**, Moody's URD via studies (seniority), GCD summaries, Banca d'Italia series, GEMs (EM).
EAD: Y-14 revolver papers only. Portfolio structure: Pillar 3/P3DH, FSR large-borrower/SMA data.
*Buildable: transition-matrix PD, financial-ratio and structural scorecards, workout LGD (India better
than most EM), EWS; not buildable: facility-level EAD without GCD/bank access.*

**SME / MSME.** Micro: **SBA 7(a)** (1.79M loans with charge-off amounts → PD + crude LGD across three
recessions); EDW SME ABS (paid); Japan CRD (closed consortium, the model). Anchors: OECD SME Scoreboard
NPLs (~50 countries), EBA SME IRB parameters. **India:** MSME Pulse (NPA by ticket size, segment, lender
type, CMR tier), **CGTMSE claims lodged/settled** (default-cost proxy by state/vintage), NeSL default
incidence by ticket band, sectoral deployment, PQ bank-wise data. *Buildable: SBA-structured PD/LGD,
India synthetic MSME book on ticket×CMR grid anchored to Pulse+CGTMSE.*

**Microfinance.** Global: **MIX Market archive** (MFI-level PAR30/90, write-offs, 1999–2019, 100+
countries), Kiva. **India (best-covered EM market):** MFIN Micrometer, CRIF MicroLend (district-level),
Sa-Dhan, SIDBI-Equifax Pulse — four trackers spanning the full FY24–FY26 stress cycle, plus NABARD SHG
NPAs by state. *Buildable: state-level stress/SICR demonstrations and synthetic JLG books; loan-level
does not exist anywhere — the MFI/state is the unit of analysis.*

**CRE / LRD.** Global micro: CMBS ABS-EE + servicer data, GSE multifamily loan-level (with REO dates);
Trepp is the paid standard. Anchors: DFAST CRE loss rates, Fed CRE charge-offs. **India: thin** — bank
Pillar 3 CRE exposures, LRD PTC rationales, builder-loan cuts in NHB T&P. *Buildable globally; India
CRE remains a proxy-and-synthesis exercise.*

**Trade finance.** **ICC Trade Register** (PD + LGD by product: LCs, guarantees, SCF — free summary,
paid tables); GCD trade subset. **India:** nothing distinct public — bank Pillar 3 non-fund exposures;
ECGC annual reports (export-credit claims paid vs premium — a CGTMSE-style loss proxy) [not re-verified
this pass]. *Buildable: product-level PD/LGD priors for a trade-book ECL overlay.*

**Sovereign / FI counterparty.** BoC–BoE default database + Cruces–Trebesch haircuts + EIB
sovereign-lending recovery stats + GEMs public-counterpart cuts (default 2.61%, recovery 85.8%).
FI counterparty: EBA transparency bank-level fundamentals, FDIC failure data. *Buildable: sovereign
PD/LGD priors and low-default-portfolio estimation demos.*

**India-specific product notes.** Gold loans: CRIF PAR cuts + listed-lender (Muthoot/Manappuram)
disclosures; LGD structurally near zero, the risk is operational/auction-timing. Education loans:
US FSA cohort-default/nonpayment data; India via parliamentary-question NPA tables. Two-wheeler and
consumer durable: CRIF/CMI product cuts. Kisan Credit Card / agri: FSR sector GNPA (~5.1%), NABARD,
PQ answers.

---

## 6. Use the regulatory templates as your data model

Don't invent a facility schema — battle-tested public templates already define what a credit-risk record
should contain, and adopting one makes every dataset above mappable into a common model:

| Template | Best for | Why |
|---|---|---|
| **ECB AnaCredit** | The canonical facility-level model | ~100 attributes: instrument, counterparty, protection, accounting and default data. Freely documented; pair with RIAD for counterparty structure |
| **EBA NPL Transaction Templates** | Defaulted-asset / LGD work | Purpose-built for post-default: collateral, enforcement, recovery cashflows. **`open-risk/openNPL`** on GitHub is a free Django implementation |
| **FR Y-14Q Schedule H.1** | Wholesale/corporate facilities | Public instructions define facility-level fields incl. internal PD/LGD, utilisation, obligor financials |
| **ESMA / EDW disclosure templates** | Securitised retail by asset class | Per-asset-class field definitions (RMBS, auto, consumer, SME, leasing) |
| **Pillar 3 template EU CR6** (new) | IRB output/reporting layer | The disclosure shape your PD/LGD/EAD outputs should aggregate into — now machine-readable via P3DH |
| **Cholamandalam ECL methodology doc** (new) | India ECL calibration reference | A real NBFC's segment-wise PD term-structure/LGD documentation — the shape of what RBI's ECL directions will demand |

For India: **AnaCredit + EBA NPL templates map cleanly onto what the RBI ECL Directions require**, and
give a superset of RBI's returns. Build to that model and an India prototype is also an EU/US prototype
with a different data feed.

---

## 7. Concrete build plan

### 7.1 The three-layer approach

```
Layer 3  SYNTHETIC     Generate loan-level records that reproduce Layer 2 aggregates
         AUGMENTATION  and inherit Layer 1 correlation structure
                       ↑ fills: India micro data, EAD/CCF, rejects, low-default portfolios
Layer 2  CALIBRATION   Published aggregates as hard targets and validation constraints
         ANCHORS       EBA P3DH & stress CSVs · RBI FSR/SMA · DFAST · CRA matrices · NeSL
                       IBBI · GEMs · BdI recoveries · bureau PAR · NBFC ECL notes · Philly Fed
Layer 1  REAL MICRO    Actual loan-level data — genuine covariate structure, seasoning,
         DATA          macro sensitivity, recovery timing
                       Freddie/Fannie · ABS-EE auto · SBA · Bondora · Amex · Home Credit ·
                       Berka · LTFS (India) · IBBI case-level (India corporate LGD)
```

The discipline: **Layer 3 is not "make up plausible numbers".** Fit copulas/CTGAN (SDV) to Layer 1 for
dependence structure, then reweight/shift so the synthetic portfolio *provably reproduces* Layer 2's
published default rates, LGDs, stage coverage and sector mix. Marginals from real disclosures,
dependence from real micro data — defensible in a way neither pure simulation nor naive GAN output is.

### 7.2 Recommended starter stack by prototype

| Prototype | Layer 1 (micro) | Layer 2 (anchors) |
|---|---|---|
| **Mortgage PD + LGD** | Freddie SFLLD (loss columns) | DFAST loss rates; EBA IRB CSV; FHFA HPI paths |
| **Auto PD + LGD + recovery timing** | ABS-EE EX-102 (Ford/GM/Santander/World Omni) | Manheim index; CRIF auto/2W PAR (India) |
| **Behavioural card / EAD-CCF** | Amex Kaggle panel; card master-trust 10-Ds | **Philly Fed Y-14M utilization/payment-rate by score band; CFPB CARD Act tiers** |
| **Application scorecard + stability monitoring** | Home Credit 2018 + **2024 stability set**; LendingClub (rejects) | NY Fed transitions; CIBIL CMI risk tiers |
| **Unsecured consumer LGD** | **Bondora/Go&Grow recovery cashflows** | GCD unsecured LGD ~27%; P2P platform disclosures (India) |
| **SME / MSME** | SBA 7(a) (charge-off amounts) | MSME Pulse by ticket size; **CGTMSE claims**; OECD SME NPLs; EBA SME IRB |
| **Corporate PD + migration** | ratingshistory.info + EDGAR XBRL + FJC bankruptcy; **India: Annexure V/VI + daily NSE/BSE rating feeds + Reg 57 + CIC registries** | S&P/Moody's annual studies; CRISIL/ICRA matrices; NUS-CRI; NeSL incidence |
| **Corporate LGD** | **IBBI Table 5 case-level (India)** | GEMs 72.9% EM recovery; GCD seniority splits; **Banca d'Italia 41% workout series**; T&P recovery-by-channel |
| **Microfinance (India)** | — (synthesise) | MFIN + Sa-Dhan + CRIF + Equifax full-cycle state panel; MIX archive (global) |
| **IFRS 9 / RBI ECL engine** | Any above for PD term structure | **NBFC ECL panel (Bajaj/Chola/Shriram + 40 more); Chola methodology doc; ECB stage stats; EBA IFRS9 reports; RBI floors (0.40%/5%) as constraints** |
| **Stress testing / ICAAP** | — | Fed + BoE + RBI FSR scenario paths; Fed charge-off series (satellite); **Laeven–Valencia peak-NPL tail anchors**; NGFS climate overlays |
| **Wholesale IRB benchmarking** | — | **EBA P3DH bulk CR6 panel** + EBA benchmarking dispersion report |

### 7.3 The five assemblable datasets nobody has built (differentiated assets, pure effort)

1. **India NBFC ECL panel** — ~50 NBFC annual reports × 7 years: stage-wise EAD/ECL by product,
   coverage ratios, disclosed PD/LGD/scenario weights. Feasibility proven (§4.5). The only India ECL
   calibration set; value spikes as the Apr 2027 deadline approaches.
2. **India corporate default-event & rating-migration corpus** — CRA Annexure V/VI Excels + daily
   NSE/BSE rating feeds + Reg 57 intimations + CIC defaulter registries + indiabondinfo. India's
   equivalent of the 17g-7 corpus, now substantially automatable (§4.2).
3. **IBBI case-level corporate LGD dataset** — Table 5 + liquidation tables across all quarterly
   newsletters: ~1,400 named resolutions with claims, liquidation/fair values, realisations, durations (§4.2).
4. **EU cross-bank IRB parameter panel** — P3DH bulk CR6 across all large EU banks × reference dates:
   the global PD/LGD benchmark product (§3.1).
5. **India district-risk panel** — SLBC district NPA tables + BSR-1 district credit × occupation ×
   interest-rate bucket + state-level microfinance PAR: a geographic risk surface for concentration and
   climate-overlay work (§4.4).

### 7.4 Access routes beyond public data (the "possibilities" layer)

- **Bank consortium:** GCD membership (via a bank client/employer) — the only real wholesale LGD/EAD micro route.
- **Registry research programs:** Bundesbank RDSC (German AnaCredit, on-site), Banco de España BELab
  (corporate + household credit register, on-site/remote), **Banco de Portugal BPLIM (full credit
  register, remote execution — lowest friction)**. Develop LGD/EAD methodology on registry data there;
  transfer the methodology, not the data.
- **Academic:** WRDS (Mergent FISD, sometimes DRD), CMIE Prowess via Indian institutions, NUS-CRI credentials.
- **Vendor free tiers:** Credit Benchmark monthly indicators; LSTA/LCD monthly default summaries; rating-agency presales (Fitch/Moody's/S&P free with registration).
- **India partnerships:** bureau pilots (CIBIL/CRIF/Experian run research collaborations), NBFC/fintech
  data under NDA, RBI DRG collaboration (visibility, not data). The AA rail (with consent) is the
  long-term micro-data route for MSME/retail cash-flow underwriting.

### 7.5 Suggested sequence

1. **Build the facility schema first** (AnaCredit-shaped; openNPL for the defaulted-asset side).
2. **Freddie/Fannie + ABS-EE auto** — one real end-to-end PD *and* LGD pipeline on data with actual
   recovery cashflows. Validates the architecture cheaply.
3. **Scrape the India corpus** — IBBI Table 5 panel, Annexure V/VI + exchange rating feeds, NBFC ECL
   notes, bureau PAR tables, recovery-by-channel, CGTMSE, SLBC districts. The differentiated asset;
   no licensing barrier, pure effort.
4. **Synthesise the India book** against those anchors (SDV/copulas; reproduce FSR/bureau/NBFC targets).
5. **Bolt on stress testing** — Fed/EBA/BoE scenario files globally; RBI FSR paths + Laeven–Valencia
   tails for India; NGFS for climate overlays.
6. **Wrap in validation-first governance** — model inventory, independent-validation docs, stability
   monitoring (the Home Credit 2024 design) — aligned to RBI's draft MRM guidance.

### 7.6 Pipeline / scrapeability notes (learned the hard way)

- **rbidocs.rbi.org.in is bot/CAPTCHA-gated** — script against data.rbi.org.in, or download PDFs manually.
- **CIBIL portals 403 non-browser clients**; **Experian's defaulter portal is the automation-tolerant one**.
- IBBI/NeSL/CGTMSE/SLBC are **PDF-table extraction jobs** (pdfplumber/camelot work on IBBI Table 5).
- Exchange feeds: NSE/BSE corporate-announcement endpoints for Reg 57 + daily rating Excels.
- Bulk-friendly APIs to build on: **EBA P3DH**, **ECB Data Portal**, **FRED/Philly Fed CSVs**,
  **Brazil BCB SGS/SCR.data**, **IMF SDMX**, **BIS bulk**, **FDIC BankFind**, **NCUA ZIPs**.

---

## 8. Licensing — check before you build on it

| Source | Constraint |
|---|---|
| Fannie/Freddie/Ginnie | Free; **terms restrict redistribution**. Fine for internal prototypes; read before publishing derived datasets |
| Kaggle competition data (Amex, Home Credit, LTFS mirrors) | **Competition rules: non-commercial/academic** use; no redistribution. Prototype yes; product no (without permission) |
| Bondora/Go&Grow, Berka, MIX Market, South German Credit | Open/CC-BY-ish (MIX + South German are CC BY 4.0; Berka research-use) |
| NUS-CRI | Free with credentials, **non-commercial only** |
| CRIF / CIBIL / MFIN / Sa-Dhan / Equifax reports | Copyrighted PDFs. Modelling from them is fine; republishing extracted tables is not |
| CRA rationales, Annexure V/VI, default studies | Public regulatory disclosures; attribute and avoid wholesale republication |
| IBBI, RBI, NeSL, CGTMSE, SEC, SBA, Fed, FFIEC, FDIC, NCUA, data.gov.in, IMF/BIS/WB | Public domain / open government data. No practical constraint |
| EBA/ECB/EDW | EBA/ECB data free; EDW bulk is paid/registered |
| GCD, Japan CRD | Members only; published summaries free |
| Moody's DRD / S&P CreditPro / Trepp / LCD | Paid — check university/WRDS access first |
| Manheim index | Free download, no formal open license (Cox Automotive) |

---

## 9. Source index

**Global micro:** [Freddie Mac SFLLD](https://freddiemac.com/research/datasets/sf-loanlevel-dataset) ·
[Fannie Mae SF Loan Performance](https://capitalmarkets.fanniemae.com/credit-risk-transfer/single-family-credit-risk-transfer/fannie-mae-single-family-loan-performance-data) ·
[Fannie Mae Multifamily](https://capitalmarkets.fanniemae.com/credit-risk-transfer/multifamily-credit-risk-transfer/multifamily-loan-performance-data) ·
[Freddie Mac MLPD](https://mf.freddiemac.com/docs/MLPD_data_dictionary.pdf) ·
[Ginnie Mae disclosure](https://www.ginniemae.gov/investors/disclosures_and_reports/Documents/MBS_SingleFamily_Loan_DataDictionary_V1.8.pdf) ·
[FHFA datasets & HPI](https://www.fhfa.gov/data/datasets) ·
[SEC Reg AB II](https://www.sec.gov/newsroom/whats-new/regabii-asset-level-requirements-compliance) ·
[SBA 7(a)/504 FOIA](https://data.sba.gov/en/dataset/7-a-504-foia) ·
[European DataWarehouse](https://eurodw.eu/) ·
[Amex Default Prediction](https://www.kaggle.com/competitions/amex-default-prediction) ·
[Home Credit Model Stability 2024](https://www.kaggle.com/competitions/home-credit-credit-risk-model-stability) ·
[Home Credit Default Risk 2018](https://www.kaggle.com/c/home-credit-default-risk/data) ·
[Bondora/Go&Grow public data](https://goandgrow.eu/en/public-statistics/) ·
[Berka/PKDD'99 (CTU)](https://relational.fel.cvut.cz/dataset/Financial) ·
[South German Credit (UCI 522)](https://archive.ics.uci.edu/dataset/522/south+german+credit) ·
[LendingClub archive](https://www.kaggle.com/datasets/wordsforthewise/lending-club) ·
[MIX Market archive (World Bank)](https://datacatalog.worldbank.org/search/dataset/0038647/mix-market) ·
[Finsight](https://finsight.com) ·
[Manheim UVVI](https://site.manheim.com/en/services/consulting/used-vehicle-value-index.html)

**Global corporate / EM / benchmarks:** [S&P annual default & transition study](https://www.spglobal.com/ratings/en/regulatory/article/250327-default-transition-and-recovery-2024-annual-global-corporate-default-and-rating-transition-study-s13452126) ·
[Moody's ratings research](https://ratings.moodys.com) ·
[NUS-CRI](https://nuscri.org/en/datadownload/) ·
[ratingshistory.info](https://ratingshistory.info/) ·
[SEC 17g-7 histories](https://www.sec.gov/about/divisions-offices/office-credit-ratings/disclosure-of-credit-rating-histories) ·
[GEMs statistics](https://www.gemsriskdatabase.org/statistics/) ·
[EIB sovereign default & recovery](https://www.eib.org/attachments/lucalli/20250179-071025-default-and-recovery-statistics-sovereign-and-sovereign-guaranteed-lending-1994-2024-en.pdf) ·
[ICC Trade Register](https://iccwbo.org/news-publications/report/icc-trade-register-report/) ·
[Global Credit Data](https://globalcreditdata.org/) ·
[Credit Benchmark](https://www.creditbenchmark.com/data-insights/) ·
[BoC–BoE Sovereign Default DB](https://www.bankofcanada.ca/2024/07/staff-analytical-note-2024-19/) ·
[Laeven–Valencia 2026 (IMF WP 26/94)](https://www.imf.org/-/media/files/publications/wp/2026/english/wpiea2026094-source-pdf.pdf) ·
[ESRB crises DB](https://www.esrb.europa.eu/pub/pdf/occasional/esrb.op13.en.pdf) ·
[Covered Bond Label HTT](https://www.coveredbondlabel.com/htt) ·
[Japan CRD Association](https://www.crd-office.net/CRD/en/about/index.html) ·
[LSTA index analysis](https://www.lsta.org/content/morningstar-lsta-leveraged-loan-index-analysis-june-2026/) ·
[Moody's credit-line EAD insight](https://www.moodys.com/web/en/us/insights/credit-risk/usage-and-exposures-at-default-of-corporate-credit-lines.html)

**Regulatory / stress / schema:** [EBA Pillar 3 Data Hub](https://www.eba.europa.eu/publications-and-media/press-releases/eba-pillar-3-data-hub-goes-live) ·
[EBA EU-wide stress test 2025](https://www.eba.europa.eu/eu-wide-stress-test-2025) ·
[EBA Transparency Exercise](https://www.eba.europa.eu/eu-wide-transparency-exercise-0) ·
[EBA credit-risk benchmarking 2025](https://www.eba.europa.eu/sites/default/files/2026-06/addc87e5-36b9-4eb5-bba7-d5168aa19819/EBA%20Report%20results%20from%20the%202025%20credit%20risk%20benchmarking%20exercise.pdf) ·
[EBA Risk Dashboard](https://www.eba.europa.eu/risk-and-data-analysis/risk-analysis/risk-monitoring/risk-dashboard) ·
[ECB supervisory banking statistics](https://data.ecb.europa.eu/data/datasets/SUP) ·
[Banca d'Italia recovery rates No. 48](https://www.bancaditalia.it/pubblicazioni/note-stabilita/2025-0048/index.html?com.dotmarketing.htmlpage.language=1) ·
[Fed DFAST 2026](https://www.federalreserve.gov/newsevents/pressreleases/bcreg20260624a.htm) ·
[Fed charge-off rates](https://www.federalreserve.gov/releases/chargeoff/) ·
[Philadelphia Fed Y-14M data](https://www.philadelphiafed.org/surveys-and-data/large-bank-credit-card-and-mortgage-data) ·
[CFPB credit card market 2025](https://www.consumerfinance.gov/data-research/research-reports/the-consumer-credit-card-market-2025/) ·
[CFPB Consumer Credit Trends](https://www.consumerfinance.gov/data-research/consumer-credit-trends/) ·
[NCUA call reports](https://ncua.gov/analysis/credit-union-corporate-call-report-data/quarterly-data) ·
[FDIC BankFind API](https://banks.data.fdic.gov/) ·
[NY Fed HHDC](https://www.newyorkfed.org/microeconomics/hhdc) ·
[FR Y-14Q H.1 instructions](https://www.reginfo.gov/public/do/DownloadDocument?objectID=35295601) ·
[BoE 2025 stress test](https://www.bankofengland.co.uk/stress-testing/uk-banks-building-societies/bank-capital-stress-test) ·
[NGFS scenarios portal](https://www.ngfs.net/ngfs-scenarios-portal/) ·
[ECB AnaCredit](https://www.ecb.europa.eu/stats/ecb_statistics/anacredit/html/index.en.html) ·
[openNPL](https://github.com/open-risk/openNPL) ·
[FCA PSD](https://www.fca.org.uk/data/product-sales-data)

**EM / cross-country:** [Brazil BCB open data](https://opendata.bcb.gov.br/) ·
[Brazil IF.data](https://www3.bcb.gov.br/ifdata/?lang=1) ·
[Mexico CNBV](https://portafolioinfo.cnbv.gob.mx/Paginas/Inicio.aspx) ·
[Turkey BDDK monthly](https://www.bddk.org.tr/bultenaylik/en) ·
[Indonesia OJK SPI](https://ojk.go.id/en/kanal/perbankan/data-dan-statistik/statistik-perbankan-indonesia/default.aspx) ·
[Philippines BSP indicators](https://www.bsp.gov.ph/Statistics/Selected%20Performance%20Indicators/16.aspx) ·
[SARB BA900](https://www.resbank.co.za/en/home/what-we-do/statistics/releases/banking-sector-information/banks-ba900-economic-returns) ·
[South Africa NCR](https://www.ncr.org.za/) ·
[IMF FSI](https://data.imf.org/en/datasets/IMF.STA:FSIC) ·
[OECD SME Scoreboard 2026](https://www.oecd.org/en/publications/financing-smes-and-entrepreneurs-2026_075d8058-en.html) ·
[BIS data portal](https://data.bis.org/bulkdownload) ·
[Doing Business insolvency archive](https://archive.doingbusiness.org/en/data/exploretopics/resolving-insolvency) ·
[B-READY](https://www.worldbank.org/en/businessready) ·
[Bundesbank RDSC](https://www.bundesbank.de/en/bundesbank/research/rdsc) ·
[BdE BELab](https://www.bde.es/wbe/en/para-ciudadano/servicios/belab/) ·
[BdF granular data / CASD](https://www.casd.eu/en/acces-aux-donnees-de-la-banque-de-france-sur-le-casd/) ·
[Banco de Portugal BPLIM](https://bplim.bportugal.pt/)

**India:** [RBI FSR June 2026](https://rbidocs.rbi.org.in/rdocs/PublicationReport/Pdfs/0FSRJUNE2026_300626A120EF6C37694C8C933181147F1379D7.PDF) ·
[RBI Data (DBIE/CIMS)](https://data.rbi.org.in/) ·
[RBI sectoral deployment](https://rbi.org.in/Scripts/Data_Sectoral_Deployment.aspx) ·
[RBI external research schemes](https://www.rbi.org.in/Scripts/ExternalResearchSchemes.aspx) ·
[IBBI publications (quarterly newsletters)](https://ibbi.gov.in/en/publication) ·
[NeSL](https://www.nesl.co.in/welcome-to-nesl/) ·
[CIBIL suit-filed](https://suit.cibil.com/) ·
[Experian defaulter search](https://suit.experian.in/DefaultAccount/view/DASearch) ·
[CRIF defaulter lists](https://www.crifhighmark.com/list-of-suit-filed-cases) ·
[NSDL indiabondinfo](https://www.indiabondinfo.nsdl.com/) ·
[CRISIL default study FY2025](https://www.crisilratings.com/content/dam/crisil/our-analysis/publications/default-study/crisil-ratings-annual-default-and-ratings-transition-study-fy-2025.pdf) ·
[CRISIL SEBI disclosures (Annexure V/VI)](https://www.crisilratings.com/en/home/our-business/ratings/regulatory-disclosures/disclosures-as-per-sebi-s-circular-cir-mirsd-cra-6-2010.html) ·
[India Ratings default study](https://www.indiaratings.co.in/data/Uploads/TransitionandDefaultStudy.pdf) ·
[CGTMSE AR 2024-25](https://www.cgtmse.in/Default/ViewFile/CGTMSE-AR-2024-25-english.pdf) ·
[NHB RESIDEX](https://residex.nhbonline.org.in/) ·
[NHB T&P Housing 2025](https://www.nhb.org.in/wp-content/uploads/2026/02/NHB-TP-Report-2024-25-english.pdf) ·
[CRIF How India Lends May 2026](https://www.crifhighmark.com/media/6802/how-india-lends-report-may-2026.pdf) ·
[SIDBI MSME Pulse](https://www.sidbi.in/msme-pulse) ·
[TransUnion CIBIL CMI](https://www.transunioncibil.com/lp/cmi-report-june-2026) ·
[MFIN Micrometer](https://mfinindia.org/) ·
[Sa-Dhan BMR](https://www.sa-dhan.net/bharat-microfinance-report/) ·
[SIDBI-Equifax Microfinance Pulse XXVII](https://assets.equifax.com/marketing/india/assets/mfi-pulse-vol-xxvii-june-2026.pdf) ·
[FACE](https://faceofindia.org/news-room/) ·
[NABARD SoMFI FY24](https://www.nabard.org/auth/writereaddata/tender/0808244223NABARD-SOMFI%20%20%20%20%20%20%20%2020232024%20%20%20%20%20%2030072024.pdf) ·
[NAFSCOB co-op data](https://www.nafscob.org/district-central-co-operative-banks-basic-data.php) ·
[LTFS vehicle loan (Kaggle)](https://www.kaggle.com/datasets/mamtadhaker/lt-vehicle-loan-default-prediction) ·
[LenDenClub performance](https://www.lendenclub.com/portfolio-performance/) ·
[Faircent stats](https://www.faircent.com/view/stats) ·
[Chola ECL methodology](https://files.cholamandalam.com/ECL_Methodology_4d25bdd042.pdf) ·
[CRISIL securitisation FY26 PR](https://www.crisilratings.com/en/home/newsroom/press-releases/2026/04/securitisation-deal-value-peaks-to-rs-2-55-lakh-crore-in-fiscal-2026.html) ·
[CRISIL ARC/SR recovery study](https://www.crisilratings.com/content/dam/crisilrating/report/2025/06/arcs-recovery-rate-set-to-accelerate/arcs-recovery-rate-set-to-accelerate.pdf) ·
[data.gov.in PSB NPA recovery](https://www.data.gov.in/resource/bank-wise-details-recovery-non-performing-assets-npas-public-sector-banks-2019-20-2024-25) ·
[SLBC Kerala](https://slbckerala.com/) · [SLBC Punjab](https://slbcpunjab.pnb.in/slbc-agenda/) ·
[Sahamati](https://sahamati.org.in/) ·
[RBI ECL directions (KPMG note)](https://assets.kpmg.com/content/dam/kpmgsites/in/pdf/2026/05/expected-credit-loss.pdf) ·
[RBI Basel III SA (KPMG note)](https://kpmg.com/in/en/insights/2026/05/basel-III-standardised-approach-for-Indian-banks.html)

---

_Items the research pass could not confirm against a primary source are flagged in-line or omitted;
of note: Moody's 2026-edition default study, NABARD SoMFI FY25, Equifax's defaulter search portal,
Mintos' current loan-book export, and the FSR Jun-2026 adverse-GNPA print (v1 carried 3.8–4.1% from the
report itself) — verify before load-bearing use._
