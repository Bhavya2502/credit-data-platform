"""Gold — US bank credit performance panel (from S-057).

Turns the raw FDIC institution panel into analysis-ready aggregates.

Two methodological corrections applied here, both material:

1. **Exclude non-lenders.** Rate fields (NTLNLSR, NCLNLSR, and every by-category
   rate) are charge-offs divided by loans. Trust companies and special-purpose
   charters hold assets but originate no loans, so the denominator is ~0 and the
   ratio explodes — one institution reached -57,200%. These are not bad data;
   the ratio is simply undefined for them. Filtered on LNLSNET > 0.

2. **Weight by loans, not by institution.** A simple mean across institutions
   treats a $200m community bank and a $3tn money-centre bank identically, which
   is not a meaningful system rate. The headline series is therefore computed as
   sum(charge-offs) / sum(loans) — the same construction the FDIC uses in its
   Quarterly Banking Profile. The unweighted median is retained alongside it as
   "the typical bank", which is a genuinely different and also useful quantity.

Where the two diverge, that divergence is itself the signal: it says losses were
concentrated in large institutions (weighted > median) or widely spread across
small ones (median > weighted).
"""

from __future__ import annotations

SILVER = "silver.fdic_bank_financials"
GOLD_SYSTEM = "gold.us_bank_credit_quarterly"
GOLD_BY_SIZE = "gold.us_bank_credit_by_size"

# Minimum loan book to be counted as a lender. $1m (values are $000s) removes
# trust/special-purpose charters without excluding genuine small banks.
MIN_LOANS_THOUSANDS = 1_000


SYSTEM_SQL = f"""
CREATE OR REPLACE TABLE {GOLD_SYSTEM} AS
WITH lenders AS (
    SELECT *
    FROM {SILVER}
    WHERE LNLSNET > {MIN_LOANS_THOUSANDS}
      AND ASSET > 0
)
SELECT
    report_date,
    report_year,
    report_quarter,
    count(DISTINCT CERT)                                          AS institutions,
    sum(ASSET)                                                    AS total_assets_thousands,
    sum(LNLSNET)                                                  AS total_loans_thousands,

    -- Headline: loan-weighted, the true system rate
    round(100.0 * sum(NTLNLS) / nullif(sum(LNLSNET), 0), 4)        AS nco_rate_weighted_pct,
    -- The typical institution, robust to outliers
    round(median(NTLNLSR), 4)                                      AS nco_rate_median_pct,
    round(median(NCLNLSR), 4)                                      AS noncurrent_rate_median_pct,

    -- Provisioning and reserve adequacy
    round(median(LNATRESR), 4)                                     AS allowance_to_loans_median_pct,
    sum(ELNATR)                                                    AS provisions_thousands,

    -- By-category net charge-off rates, loan-weighted.
    -- Category denominators are not published, so total loans is used as the
    -- weight: an approximation, and a far better one than an equal-weighted mean.
    round(sum(NTRERESR * LNLSNET) / nullif(sum(CASE WHEN NTRERESR IS NOT NULL THEN LNLSNET END), 0), 4) AS nco_residential_pct,
    round(sum(NTREMULR * LNLSNET) / nullif(sum(CASE WHEN NTREMULR IS NOT NULL THEN LNLSNET END), 0), 4) AS nco_multifamily_pct,
    round(sum(NTRENRSR * LNLSNET) / nullif(sum(CASE WHEN NTRENRSR IS NOT NULL THEN LNLSNET END), 0), 4) AS nco_cre_nonresi_pct,
    round(sum(NTRECOSR * LNLSNET) / nullif(sum(CASE WHEN NTRECOSR IS NOT NULL THEN LNLSNET END), 0), 4) AS nco_construction_pct,
    round(sum(IDNTCIR   * LNLSNET) / nullif(sum(CASE WHEN IDNTCIR   IS NOT NULL THEN LNLSNET END), 0), 4) AS nco_ci_pct,
    round(sum(IDNTCONR  * LNLSNET) / nullif(sum(CASE WHEN IDNTCONR  IS NOT NULL THEN LNLSNET END), 0), 4) AS nco_consumer_pct,

    -- Noncurrent (90+ dpd or nonaccrual) by category — a PD-side view
    round(sum(NCRERESR * LNLSNET) / nullif(sum(CASE WHEN NCRERESR IS NOT NULL THEN LNLSNET END), 0), 4) AS noncurrent_residential_pct,
    round(sum(NCRENRER * LNLSNET) / nullif(sum(CASE WHEN NCRENRER IS NOT NULL THEN LNLSNET END), 0), 4) AS noncurrent_cre_nonresi_pct,
    round(sum(NCRECONR * LNLSNET) / nullif(sum(CASE WHEN NCRECONR IS NOT NULL THEN LNLSNET END), 0), 4) AS noncurrent_construction_pct,
    round(sum(IDNCCIR  * LNLSNET) / nullif(sum(CASE WHEN IDNCCIR  IS NOT NULL THEN LNLSNET END), 0), 4) AS noncurrent_ci_pct,
    round(sum(IDNCCONR * LNLSNET) / nullif(sum(CASE WHEN IDNCCONR IS NOT NULL THEN LNLSNET END), 0), 4) AS noncurrent_consumer_pct,

    'S-057'                                                        AS _source_id,
    now()                                                          AS _built_at
FROM lenders
GROUP BY report_date, report_year, report_quarter
ORDER BY report_date
"""


BY_SIZE_SQL = f"""
CREATE OR REPLACE TABLE {GOLD_BY_SIZE} AS
WITH lenders AS (
    SELECT *,
        CASE
            WHEN ASSET <   300_000     THEN '1. under $300m'
            WHEN ASSET < 1_000_000     THEN '2. $300m-$1bn'
            WHEN ASSET < 10_000_000    THEN '3. $1bn-$10bn'
            WHEN ASSET < 250_000_000   THEN '4. $10bn-$250bn'
            ELSE                            '5. over $250bn'
        END AS size_class
    FROM {SILVER}
    WHERE LNLSNET > {MIN_LOANS_THOUSANDS} AND ASSET > 0
)
SELECT
    report_date,
    report_year,
    size_class,
    count(DISTINCT CERT)                                    AS institutions,
    sum(LNLSNET)                                            AS total_loans_thousands,
    round(100.0 * sum(NTLNLS) / nullif(sum(LNLSNET), 0), 4) AS nco_rate_weighted_pct,
    round(median(NTLNLSR), 4)                               AS nco_rate_median_pct,
    round(median(NCLNLSR), 4)                               AS noncurrent_rate_median_pct,
    'S-057'                                                 AS _source_id,
    now()                                                   AS _built_at
FROM lenders
GROUP BY report_date, report_year, size_class
ORDER BY report_date, size_class
"""


def build(con) -> dict[str, int]:
    """Build the gold tables. Returns row counts."""
    con.execute("CREATE SCHEMA IF NOT EXISTS gold")
    con.execute(SYSTEM_SQL)
    con.execute(BY_SIZE_SQL)
    return {
        GOLD_SYSTEM: con.execute(f"SELECT count(*) FROM {GOLD_SYSTEM}").fetchone()[0],
        GOLD_BY_SIZE: con.execute(f"SELECT count(*) FROM {GOLD_BY_SIZE}").fetchone()[0],
    }


def check(con) -> list[tuple[str, bool, str]]:
    """Validate the gold aggregates. Returns (name, passed, detail)."""
    results: list[tuple[str, bool, str]] = []

    # Outliers must be gone: no system rate outside a defensible band.
    bad = con.execute(
        f"SELECT count(*) FROM {GOLD_SYSTEM} "
        f"WHERE nco_rate_weighted_pct < -0.5 OR nco_rate_weighted_pct > 5"
    ).fetchone()[0]
    results.append((
        "system_rate_plausible", bad == 0,
        f"{bad} quarter(s) with weighted charge-off rate outside [-0.5%, 5%]",
    ))

    # The crisis must still be visible after cleaning — cleaning that erases the
    # signal has removed real data, not noise.
    row = con.execute(
        f"""
        SELECT
            avg(CASE WHEN report_year IN (2005,2006) THEN nco_rate_weighted_pct END),
            avg(CASE WHEN report_year IN (2009,2010) THEN nco_rate_weighted_pct END)
        FROM {GOLD_SYSTEM}
        """
    ).fetchone()
    benign, crisis = row[0], row[1]
    if benign and crisis:
        ratio = crisis / benign
        results.append((
            "crisis_signal_preserved", ratio > 2.0,
            f"{benign:.3f}% (2005-06) → {crisis:.3f}% (2009-10), ratio {ratio:.2f}x",
        ))

    # Quarterly continuity — no missing periods inside the covered range.
    gaps = con.execute(
        f"""
        WITH q AS (
            SELECT report_date,
                   lag(report_date) OVER (ORDER BY report_date) AS prev
            FROM {GOLD_SYSTEM}
        )
        SELECT count(*) FROM q
        WHERE prev IS NOT NULL AND date_diff('day', prev, report_date) > 100
        """
    ).fetchone()[0]
    results.append((
        "no_quarter_gaps", gaps == 0,
        f"{gaps} gap(s) longer than one quarter",
    ))

    return results
