"""Gold — India retail vehicle-loan PD panel (from S-103 LTFS).

233k Indian vehicle loans with bureau depth, collateral terms and a first-EMI
default flag: the only borrower-level Indian credit dataset available publicly.

The single most important thing this transform does is handle the bureau score
correctly. `PERFORM_CNS.SCORE` mixes real CIBIL scores (300-890) with at least
SEVEN sentinel values that are not scores at all:

    0   No Bureau History Available          116,950 loans (50% of the book)
    11  More than 50 active accounts found
    14  Only a Guarantor
    15  Sufficient History Not Available
    16  No Activity seen (Inactive)
    17  Not Enough Info available
    18  No Updates in last 36 months

Treated as a number, half the portfolio lands *below* the worst-rated borrower
(M = 300), when its realised default rate (23.1%) is mid-pack. Any model fed the
raw column learns a severe, false monotonic relationship. The panel therefore
splits the column into a clean numeric score (NULL when unscored) and an
explicit reason code, so "no bureau history" is modelled as a category rather
than as a very low score.

A second finding is preserved rather than smoothed: the scored bands are NOT
monotonic in the prime range. A (806-890) defaults at 16.6% while B (761-805)
defaults at 13.1% and C (736-760) at 17.3%. Only from E downward does the
ordering hold. This is a real property of a subprime vehicle-loan book — a
genuinely prime borrower rarely takes this product, so high-CIBIL applicants
here are adversely selected. The panel records observed ordering; it does not
re-rank bands to look tidy.
"""

from __future__ import annotations

SILVER = "silver.kaggle_ltfs_vehicle_train"
GOLD_PANEL = "gold.india_retail_pd_panel"
GOLD_SUMMARY = "gold.india_retail_pd_summary"

# Real CIBIL scores start at 300; anything below is a status code.
MIN_REAL_SCORE = 300


PANEL_SQL = f"""
CREATE OR REPLACE TABLE {GOLD_PANEL} AS
WITH base AS (
    SELECT
        "UniqueID"                                    AS loan_id,
        disbursed_amount,
        asset_cost,
        ltv,
        branch_id, supplier_id, manufacturer_id, "State_ID",
        "Employment.Type"                             AS employment_type,
        try_strptime("Date.of.Birth", ['%d-%m-%y', '%d-%m-%Y'])      AS dob_ts,
        try_strptime("DisbursalDate", ['%d-%m-%y', '%d-%m-%Y'])      AS disbursal_ts,
        "PERFORM_CNS.SCORE"                           AS cns_score_raw,
        "PERFORM_CNS.SCORE.DESCRIPTION"               AS cns_description,
        "PRI.NO.OF.ACCTS"        AS pri_accts,
        "PRI.ACTIVE.ACCTS"       AS pri_active,
        "PRI.OVERDUE.ACCTS"      AS pri_overdue,
        "PRI.CURRENT.BALANCE"    AS pri_balance,
        "PRI.SANCTIONED.AMOUNT"  AS pri_sanctioned,
        "PRI.DISBURSED.AMOUNT"   AS pri_disbursed,
        "SEC.NO.OF.ACCTS"        AS sec_accts,
        "SEC.ACTIVE.ACCTS"       AS sec_active,
        "SEC.OVERDUE.ACCTS"      AS sec_overdue,
        "SEC.CURRENT.BALANCE"    AS sec_balance,
        "PRIMARY.INSTAL.AMT"     AS primary_instal_amt,
        "NEW.ACCTS.IN.LAST.SIX.MONTHS"        AS new_accts_6m,
        "DELINQUENT.ACCTS.IN.LAST.SIX.MONTHS" AS delinquent_accts_6m,
        "AVERAGE.ACCT.AGE"       AS avg_acct_age_raw,
        "CREDIT.HISTORY.LENGTH"  AS credit_history_raw,
        "NO.OF_INQUIRIES"        AS inquiries,
        "Aadhar_flag", "PAN_flag", "VoterID_flag", "Driving_flag", "Passport_flag",
        loan_default
    FROM {SILVER}
)
SELECT
    loan_id,

    -- ── Bureau score, split into signal and reason ───────────────────
    -- Real score only when >= 300; otherwise NULL and the reason is carried
    -- separately. Never impute, never treat a status code as a low score.
    CASE WHEN cns_score_raw >= {MIN_REAL_SCORE} THEN cns_score_raw END
                                                      AS cibil_score,
    (cns_score_raw >= {MIN_REAL_SCORE})               AS has_bureau_score,
    CASE
        WHEN cns_score_raw >= {MIN_REAL_SCORE} THEN 'scored'
        WHEN cns_score_raw = 0  THEN 'no_bureau_history'
        WHEN cns_score_raw = 11 THEN 'over_50_active_accounts'
        WHEN cns_score_raw = 14 THEN 'only_guarantor'
        WHEN cns_score_raw = 15 THEN 'insufficient_history'
        WHEN cns_score_raw = 16 THEN 'inactive_no_activity'
        WHEN cns_score_raw = 17 THEN 'not_enough_info'
        WHEN cns_score_raw = 18 THEN 'no_updates_36m'
        ELSE 'unscored_other'
    END                                               AS bureau_status,
    cns_description                                   AS cibil_band_raw,
    -- Letter grade only where genuinely scored (A-M prefix in the description)
    CASE WHEN cns_score_raw >= {MIN_REAL_SCORE}
         THEN substr(trim(cns_description), 1, 1) END AS cibil_grade,
    CASE
        WHEN cns_score_raw <  {MIN_REAL_SCORE} THEN 'not_scored'
        WHEN cns_score_raw >= 706 THEN '1. very low risk'
        WHEN cns_score_raw >= 631 THEN '2. low risk'
        WHEN cns_score_raw >= 571 THEN '3. medium risk'
        WHEN cns_score_raw >= 351 THEN '4. high risk'
        ELSE                           '5. very high risk'
    END                                               AS cibil_risk_tier,

    -- ── Applicant ────────────────────────────────────────────────────
    -- Two-digit years in the source parse into the 2060s for older borrowers;
    -- shift any implausible future date back a century.
    CASE
        WHEN dob_ts IS NULL OR disbursal_ts IS NULL THEN NULL
        WHEN date_diff('year', dob_ts, disbursal_ts) < 0
            THEN date_diff('year', dob_ts - INTERVAL 100 YEAR, disbursal_ts)
        ELSE date_diff('year', dob_ts, disbursal_ts)
    END                                               AS age_at_disbursal,
    employment_type,
    "State_ID"                                        AS state_id,
    disbursal_ts::DATE                                AS disbursal_date,

    -- Indian identity infrastructure — no Western analogue, and predictive
    (COALESCE("Aadhar_flag",0) + COALESCE("PAN_flag",0) + COALESCE("VoterID_flag",0)
     + COALESCE("Driving_flag",0) + COALESCE("Passport_flag",0))
                                                      AS id_documents_count,
    "Aadhar_flag" AS has_aadhaar, "PAN_flag" AS has_pan,

    -- ── Loan and collateral ──────────────────────────────────────────
    disbursed_amount, asset_cost, ltv,
    CASE
        WHEN ltv IS NULL      THEN 'unknown'
        WHEN ltv <  60 THEN '1. under 60'
        WHEN ltv <  70 THEN '2. 60-70'
        WHEN ltv <  80 THEN '3. 70-80'
        WHEN ltv <  90 THEN '4. 80-90'
        ELSE                '5. over 90'
    END                                               AS ltv_band,
    primary_instal_amt,
    CASE WHEN disbursed_amount > 0
         THEN round(primary_instal_amt / disbursed_amount, 5) END
                                                      AS instal_to_disbursed,

    -- ── Bureau depth ─────────────────────────────────────────────────
    pri_accts, pri_active, pri_overdue, pri_balance, pri_sanctioned,
    sec_accts, sec_active, sec_overdue,
    (COALESCE(pri_accts,0) + COALESCE(sec_accts,0))   AS total_accts,
    (COALESCE(pri_overdue,0) + COALESCE(sec_overdue,0)) AS total_overdue_accts,
    CASE WHEN (COALESCE(pri_accts,0) + COALESCE(sec_accts,0)) > 0
         THEN round(1.0 * (COALESCE(pri_overdue,0) + COALESCE(sec_overdue,0))
                    / (COALESCE(pri_accts,0) + COALESCE(sec_accts,0)), 4) END
                                                      AS overdue_acct_ratio,
    -- Utilisation: drawn against sanctioned on primary accounts
    CASE WHEN pri_sanctioned > 0
         THEN round(pri_balance / pri_sanctioned, 4) END
                                                      AS pri_utilisation,
    new_accts_6m, delinquent_accts_6m, inquiries,

    -- "1yrs 11mon" -> months
    CASE WHEN avg_acct_age_raw IS NOT NULL THEN
        COALESCE(TRY_CAST(regexp_extract(avg_acct_age_raw, '(\\d+)yrs', 1) AS INTEGER), 0) * 12
      + COALESCE(TRY_CAST(regexp_extract(avg_acct_age_raw, '(\\d+)mon', 1) AS INTEGER), 0)
    END                                               AS avg_acct_age_months,
    CASE WHEN credit_history_raw IS NOT NULL THEN
        COALESCE(TRY_CAST(regexp_extract(credit_history_raw, '(\\d+)yrs', 1) AS INTEGER), 0) * 12
      + COALESCE(TRY_CAST(regexp_extract(credit_history_raw, '(\\d+)mon', 1) AS INTEGER), 0)
    END                                               AS credit_history_months,

    -- ── Target ───────────────────────────────────────────────────────
    loan_default                                      AS default_first_emi,

    'S-103'                                           AS _source_id,
    now()                                             AS _built_at
FROM base
"""


SUMMARY_SQL = f"""
CREATE OR REPLACE TABLE {GOLD_SUMMARY} AS
WITH cuts AS (
    SELECT 'all'            AS dimension, 'all loans'    AS segment, * FROM {GOLD_PANEL}
    UNION ALL SELECT 'bureau_status',  bureau_status,                * FROM {GOLD_PANEL}
    UNION ALL SELECT 'cibil_tier',     cibil_risk_tier,               * FROM {GOLD_PANEL}
    UNION ALL SELECT 'cibil_grade',    COALESCE(cibil_grade,'none'),  * FROM {GOLD_PANEL}
    UNION ALL SELECT 'ltv_band',       ltv_band,                      * FROM {GOLD_PANEL}
    UNION ALL SELECT 'employment',     COALESCE(employment_type,'unknown'), * FROM {GOLD_PANEL}
    UNION ALL SELECT 'id_documents',   CAST(id_documents_count AS VARCHAR), * FROM {GOLD_PANEL}
)
SELECT
    dimension,
    segment,
    count(*)                                            AS loans,
    round(100.0 * avg(default_first_emi), 3)            AS default_rate_pct,
    round(avg(disbursed_amount))                        AS avg_disbursed,
    round(avg(ltv), 2)                                  AS avg_ltv,
    round(avg(cibil_score))                             AS avg_cibil_score,
    count(*) FILTER (WHERE has_bureau_score)            AS with_bureau_score,
    round(avg(age_at_disbursal), 1)                     AS avg_age,
    round(avg(total_accts), 2)                          AS avg_accts,
    round(avg(overdue_acct_ratio), 4)                   AS avg_overdue_ratio,
    round(avg(credit_history_months), 1)                AS avg_credit_hist_months,
    'S-103'                                             AS _source_id,
    now()                                               AS _built_at
FROM cuts
WHERE segment IS NOT NULL
GROUP BY dimension, segment
ORDER BY dimension, segment
"""


def build(con) -> dict[str, int]:
    con.execute("CREATE SCHEMA IF NOT EXISTS gold")
    con.execute(PANEL_SQL)
    con.execute(SUMMARY_SQL)
    return {
        GOLD_PANEL: con.execute(f"SELECT count(*) FROM {GOLD_PANEL}").fetchone()[0],
        GOLD_SUMMARY: con.execute(f"SELECT count(*) FROM {GOLD_SUMMARY}").fetchone()[0],
    }


DECLARED_CHECKS = [
    "sentinel_scores_excluded",
    "bureau_coverage",
    "default_rate_plausible",
    "age_plausible",
    "tier_discriminates",
]


def check(con) -> list[tuple[str, bool, str]]:
    from src.quality.checks import enforce_declared

    results: list[tuple[str, bool, str]] = []

    # No status code may survive as a "score". If any value between 1 and 299
    # appears, the sentinel split has failed and models will learn nonsense.
    leak = con.execute(
        f"SELECT count(*) FROM {GOLD_PANEL} WHERE cibil_score IS NOT NULL AND cibil_score < {MIN_REAL_SCORE}"
    ).fetchone()[0]
    results.append((
        "sentinel_scores_excluded", leak == 0,
        f"{leak} row(s) with a cibil_score below {MIN_REAL_SCORE} — sentinels must be NULL",
    ))

    row = con.execute(
        f"SELECT count(*), count(*) FILTER (WHERE has_bureau_score) FROM {GOLD_PANEL}"
    ).fetchone()
    total, scored = row[0], row[1]
    share = scored / total if total else 0
    results.append((
        "bureau_coverage", 0.3 <= share <= 0.8,
        f"{scored:,}/{total:,} ({share:.1%}) carry a real bureau score; "
        f"the remainder are status codes modelled as categories",
    ))

    rate = con.execute(
        f"SELECT avg(default_first_emi) FROM {GOLD_PANEL}"
    ).fetchone()[0]
    results.append((
        "default_rate_plausible", rate is not None and 0.05 <= rate <= 0.40,
        f"first-EMI default rate {100*rate:.2f}% (subprime vehicle book)",
    ))

    ages = con.execute(
        f"SELECT min(age_at_disbursal), max(age_at_disbursal), avg(age_at_disbursal) "
        f"FROM {GOLD_PANEL} WHERE age_at_disbursal IS NOT NULL"
    ).fetchone()
    ok_age = ages[0] is not None and 17 <= ages[0] and ages[1] <= 90
    results.append((
        "age_plausible", ok_age,
        f"age {ages[0]}-{ages[1]}, mean {ages[2]:.1f}" if ages[0] is not None else "no ages parsed",
    ))

    # Does the CIBIL tier discriminate? Recorded honestly: the prime bands are
    # known NOT to be monotonic in this book, so the test is on the broad tiers
    # (very low vs very high), not on every adjacent pair.
    tiers = con.execute(
        f"""
        SELECT segment, default_rate_pct FROM {GOLD_SUMMARY}
        WHERE dimension = 'cibil_tier' AND segment <> 'not_scored'
        ORDER BY segment
        """
    ).fetchall()
    if len(tiers) >= 3:
        lo = next((t[1] for t in tiers if t[0].startswith('1.')), None)
        hi = next((t[1] for t in tiers if t[0].startswith('5.')), None)
        spread = (hi / lo) if (lo and hi and lo > 0) else 0
        detail = " · ".join(f"{t[0][3:]}:{t[1]:.1f}%" for t in tiers)
        results.append((
            "tier_discriminates", spread >= 1.5,
            f"very-low {lo:.1f}% → very-high {hi:.1f}% ({spread:.2f}x) — {detail}"
            if lo and hi else detail,
        ))

    return enforce_declared(DECLARED_CHECKS, results)
