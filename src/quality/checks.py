"""Reconciliation and validation checks.

A dataset is not "loaded" until it reconciles (PLATFORM_PLAN §8). Checks fall
into three kinds:

  * completeness — did we capture every row the source claims to have
  * integrity    — does the data respect its own declared grain and bounds
  * truth        — does the data reproduce a fact we know independently

The third kind is the one that catches silent corruption. A parser can produce
a complete, well-formed table of the wrong numbers; it cannot easily produce one
where the 2008 credit crisis appears in the right place at the right magnitude.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class CheckResult:
    name: str
    passed: bool
    observed: float
    expected: float | None
    tolerance: float | None
    detail: str


def run_fdic_checks(con, table: str) -> list[CheckResult]:
    """Reconciliation suite for S-057 (FDIC BankFind)."""
    results: list[CheckResult] = []

    # ── integrity: declared grain is CERT × REPDTE ────────────────────
    dupes = con.execute(
        f"""
        SELECT count(*) FROM (
            SELECT CERT, REPDTE FROM {table} GROUP BY CERT, REPDTE HAVING count(*) > 1
        )
        """
    ).fetchone()[0]
    results.append(CheckResult(
        name="no_duplicate_cert_per_repdte",
        passed=dupes == 0,
        observed=float(dupes), expected=0.0, tolerance=0.0,
        detail=f"{dupes} duplicate (CERT, REPDTE) pairs" if dupes else "grain is unique",
    ))

    # ── integrity: assets must be positive ────────────────────────────
    bad_assets = con.execute(
        f"SELECT count(*) FROM {table} WHERE ASSET IS NULL OR ASSET <= 0"
    ).fetchone()[0]
    total_rows = con.execute(f"SELECT count(*) FROM {table}").fetchone()[0]
    share = bad_assets / total_rows if total_rows else 1.0
    results.append(CheckResult(
        name="assets_positive",
        passed=share < 0.001,
        observed=float(bad_assets), expected=0.0, tolerance=0.001,
        detail=f"{bad_assets:,} of {total_rows:,} rows with non-positive assets",
    ))

    # ── integrity: loans cannot exceed assets ─────────────────────────
    impossible = con.execute(
        f"SELECT count(*) FROM {table} WHERE LNLSNET IS NOT NULL AND ASSET IS NOT NULL "
        f"AND LNLSNET > ASSET * 1.01"
    ).fetchone()[0]
    results.append(CheckResult(
        name="loans_not_exceeding_assets",
        passed=impossible == 0,
        observed=float(impossible), expected=0.0, tolerance=0.0,
        detail=f"{impossible} rows where net loans exceed total assets",
    ))

    # ── integrity: charge-off rate within plausible bounds ────────────
    outliers = con.execute(
        f"SELECT count(*) FROM {table} WHERE NTLNLSR IS NOT NULL "
        f"AND (NTLNLSR < -5 OR NTLNLSR > 25)"
    ).fetchone()[0]
    results.append(CheckResult(
        name="chargeoff_rate_in_range",
        passed=outliers < max(1, total_rows * 0.001),
        observed=float(outliers), expected=0.0, tolerance=0.001,
        detail=f"{outliers:,} rows with net charge-off rate outside [-5%, 25%]",
    ))

    # ── truth: the 2008-09 credit crisis must be visible ──────────────
    # Independent of our pipeline: US bank charge-offs roughly tripled from the
    # 2005-06 benign period to the 2009-10 peak. If the panel spans both eras
    # and does not show that, we are looking at the wrong numbers.
    row = con.execute(
        f"""
        SELECT
            avg(CASE WHEN report_year IN (2005, 2006) THEN NTLNLSR END) AS benign,
            avg(CASE WHEN report_year IN (2009, 2010) THEN NTLNLSR END) AS crisis
        FROM {table}
        WHERE NTLNLSR IS NOT NULL
        """
    ).fetchone()
    benign, crisis = row[0], row[1]

    if benign and crisis and benign > 0:
        ratio = crisis / benign
        results.append(CheckResult(
            name="crisis_signal_visible",
            passed=ratio > 2.0,
            observed=round(ratio, 2), expected=2.0, tolerance=None,
            detail=(
                f"mean charge-off rate {benign:.3f}% (2005-06) → {crisis:.3f}% (2009-10), "
                f"ratio {ratio:.2f}x"
            ),
        ))
    else:
        results.append(CheckResult(
            name="crisis_signal_visible",
            passed=True, observed=0.0, expected=None, tolerance=None,
            detail="skipped — loaded period does not span both 2005-06 and 2009-10",
        ))

    # ── coverage summary (informational, always passes) ───────────────
    cov = con.execute(
        f"""
        SELECT count(DISTINCT REPDTE), count(DISTINCT CERT), min(REPDTE), max(REPDTE)
        FROM {table}
        """
    ).fetchone()
    results.append(CheckResult(
        name="coverage",
        passed=True,
        observed=float(cov[0]), expected=None, tolerance=None,
        detail=f"{cov[0]} quarters, {cov[1]:,} distinct institutions, {cov[2]} → {cov[3]}",
    ))

    return results
