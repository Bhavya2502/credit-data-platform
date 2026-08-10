"""Gold — European consumer credit panel (from S-014 Bondora).

Turns 789k raw loan records into a modelling-ready panel carrying both sides of
credit risk: a Basel-shaped 12-month PD target and a principal-recovery-derived
LGD, plus affordability and vintage dimensions.

Four decisions, each of which would distort a model if made otherwise:

1. **NULL default outcomes are excluded from PD analysis, not filled.**
   ~23% of loans are too young for a 12-month outcome. They are retained in the
   panel (they carry valid LGD and feature data) but flagged, and every PD
   aggregate restricts to measurable loans. Filling NULL with False would
   understate the default rate by roughly a quarter.

2. **LGD is recovery-to-date, not final, for loans still in default.**
   This file is a snapshot of current state, not a closed-workout register. A
   loan defaulted last month has barely begun recovering. Treating its
   recovery-to-date as final LGD overstates loss badly, so `recovery_complete`
   separates settled outcomes from in-progress ones and the headline LGD
   restricts to the former.

3. **LGD is measured on principal, not total cash.** `repaid_amount_total`
   includes interest, so a fully-performing loan repays MORE than it borrowed
   and would show negative loss. Principal recovery is the economically
   meaningful quantity and is what LGD conventionally measures.

4. **No discounting.** Economic LGD discounts recovery cashflows to the default
   date; this file gives cumulative amounts, not dated cashflows, so only
   nominal LGD is derivable. `months_in_default` is carried so a user can apply
   their own discount rate.
"""

from __future__ import annotations

SILVER = "silver.bondora_loans"
GOLD_PANEL = "gold.consumer_credit_panel"
GOLD_SUMMARY = "gold.consumer_credit_summary"


PANEL_SQL = f"""
CREATE OR REPLACE TABLE {GOLD_PANEL} AS
SELECT
    loan_id,
    country,
    customer_risk_rating,

    -- Vintage: default rates by origination cohort are the standard way to see
    -- underwriting quality drift over time.
    loan_issued_at::DATE                                   AS issued_date,
    year(loan_issued_at)                                   AS vintage_year,
    quarter(loan_issued_at)                                AS vintage_quarter,

    -- Exposure and terms
    issued_amount                                          AS exposure_eur,
    initial_interest_rate,
    round(100.0 * initial_interest_rate, 2)                AS interest_rate_pct,
    initial_loan_duration                                  AS term_months,
    nr_of_payments,
    months_on_book,

    -- Affordability. Loan-to-income is the single most predictive scorecard
    -- feature in unsecured lending and is not published directly.
    combined_income                                        AS income_eur,
    CASE WHEN combined_income > 0
         THEN round(issued_amount / combined_income, 4) END AS loan_to_income,
    CASE
        WHEN combined_income IS NULL OR combined_income <= 0 THEN 'unknown'
        WHEN issued_amount / combined_income < 0.10 THEN '1. under 0.1x'
        WHEN issued_amount / combined_income < 0.25 THEN '2. 0.1-0.25x'
        WHEN issued_amount / combined_income < 0.50 THEN '3. 0.25-0.5x'
        WHEN issued_amount / combined_income < 1.00 THEN '4. 0.5-1x'
        ELSE                                                  '5. over 1x'
    END                                                    AS loan_to_income_band,

    -- ── PD side ──────────────────────────────────────────────────────
    -- NULL means "not yet observable", never "no default".
    has_default_within_12_months                           AS default_12m,
    (has_default_within_12_months IS NOT NULL)             AS default_12m_measurable,
    is_default                                             AS in_default_now,
    days_past_due_principal,
    loan_status,
    loan_status_risk,

    -- ── LGD side ─────────────────────────────────────────────────────
    principal_paid_total,
    principal_debt,
    principal_balance,
    repaid_amount_total,
    interest_paid_total,

    -- Principal recovery, capped at 100%: a borrower cannot repay more
    -- principal than was advanced, so anything above is a data artefact.
    CASE WHEN issued_amount > 0
         THEN round(least(100.0 * principal_paid_total / issued_amount, 100.0), 4) END
                                                           AS principal_recovery_pct,
    CASE WHEN issued_amount > 0
         THEN round(greatest(100.0 - least(100.0 * principal_paid_total / issued_amount, 100.0), 0.0), 4) END
                                                           AS lgd_principal_pct,

    -- Has the outcome settled? A loan still in default is still recovering, so
    -- its recovery-to-date is a lower bound on final recovery, not an estimate
    -- of it.
    (loan_status IN ('Repaid', 'Returned'))                AS recovery_complete,
    months_in_default,

    projected_npv_return,
    'S-014'                                                AS _source_id,
    now()                                                  AS _built_at
FROM {SILVER}
WHERE issued_amount IS NOT NULL AND issued_amount > 0
"""


SUMMARY_SQL = f"""
CREATE OR REPLACE TABLE {GOLD_SUMMARY} AS
WITH cuts AS (
    SELECT 'all'           AS dimension, 'all loans'    AS segment, * FROM {GOLD_PANEL}
    UNION ALL SELECT 'risk_rating',  coalesce(customer_risk_rating, 'unrated'), * FROM {GOLD_PANEL}
    UNION ALL SELECT 'country',      country,                                   * FROM {GOLD_PANEL}
    UNION ALL SELECT 'vintage_year', CAST(vintage_year AS VARCHAR),             * FROM {GOLD_PANEL}
    UNION ALL SELECT 'loan_to_income', loan_to_income_band,                     * FROM {GOLD_PANEL}
)
SELECT
    dimension,
    segment,
    count(*)                                                       AS loans,
    round(sum(exposure_eur), 2)                                    AS exposure_eur,
    round(avg(exposure_eur), 2)                                    AS avg_loan_eur,
    round(avg(interest_rate_pct), 2)                               AS avg_rate_pct,

    -- PD: measurable loans only
    count(*) FILTER (WHERE default_12m_measurable)                 AS pd_measurable,
    round(100.0 * avg(CASE WHEN default_12m THEN 1.0 ELSE 0.0 END)
          FILTER (WHERE default_12m_measurable), 3)                AS default_rate_12m_pct,

    -- LGD: settled outcomes only, otherwise recovery is still in progress
    count(*) FILTER (WHERE recovery_complete)                      AS lgd_observable,
    round(median(lgd_principal_pct) FILTER (WHERE recovery_complete), 3)
                                                                   AS lgd_median_pct,
    round(avg(lgd_principal_pct) FILTER (WHERE recovery_complete), 3)
                                                                   AS lgd_mean_pct,

    -- Loss rate on defaulted-and-settled loans: the quantity ECL actually needs
    round(avg(lgd_principal_pct) FILTER (WHERE recovery_complete AND default_12m), 3)
                                                                   AS lgd_given_default_pct,
    round(median(months_in_default) FILTER (WHERE months_in_default IS NOT NULL), 1)
                                                                   AS months_in_default_median,

    'S-014'                                                        AS _source_id,
    now()                                                          AS _built_at
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
    "lgd_in_range",
    "rating_discriminates",
    "pd_censoring_preserved",
    "vintage_coverage",
]


def check(con) -> list[tuple[str, bool, str]]:
    from src.quality.checks import enforce_declared

    results: list[tuple[str, bool, str]] = []

    bad = con.execute(
        f"SELECT count(*) FROM {GOLD_PANEL} "
        f"WHERE lgd_principal_pct IS NOT NULL AND (lgd_principal_pct < 0 OR lgd_principal_pct > 100)"
    ).fetchone()[0]
    results.append((
        "lgd_in_range", bad == 0,
        f"{bad} loan(s) with LGD outside [0%, 100%]",
    ))

    # The lender's grade must still order defaults after the gold transform.
    grades = con.execute(
        f"""
        SELECT segment, default_rate_12m_pct
        FROM {GOLD_SUMMARY}
        WHERE dimension = 'risk_rating' AND segment <> 'unrated'
          AND pd_measurable >= 100 AND default_rate_12m_pct IS NOT NULL
        ORDER BY default_rate_12m_pct
        """
    ).fetchall()
    if len(grades) >= 3:
        rates = [g[1] for g in grades]
        rising = all(rates[i] <= rates[i + 1] for i in range(len(rates) - 1))
        span = (max(rates) / min(rates)) if min(rates) > 0 else 0
        results.append((
            "rating_discriminates", rising and span >= 2,
            f"{len(grades)} grades span {min(rates):.1f}%-{max(rates):.1f}% ({span:.1f}x)",
        ))

    # Censoring must survive into gold: if every loan became measurable, the
    # NULL semantics were lost somewhere in the transform.
    row = con.execute(
        f"SELECT count(*), count(*) FILTER (WHERE default_12m_measurable) FROM {GOLD_PANEL}"
    ).fetchone()
    total, measurable = row[0], row[1]
    share = measurable / total if total else 0
    results.append((
        "pd_censoring_preserved", 0.5 <= share <= 0.95,
        f"{measurable:,}/{total:,} ({share:.1%}) measurable for 12-month default; "
        f"the rest are too young and must stay excluded from PD work",
    ))

    cov = con.execute(
        f"SELECT min(vintage_year), max(vintage_year), count(DISTINCT vintage_year) FROM {GOLD_PANEL}"
    ).fetchone()
    results.append((
        "vintage_coverage", (cov[2] or 0) >= 10,
        f"vintages {cov[0]}-{cov[1]} ({cov[2]} years)",
    ))

    return enforce_declared(DECLARED_CHECKS, results)
