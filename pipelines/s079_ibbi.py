"""S-079 · IBBI newsletters — fetch → bronze → extract → silver → reconcile.

Builds India's only public workout-LGD micro dataset: case-level insolvency
outcomes with admitted claims, liquidation and fair value, realised amounts and
process durations, for every corporate debtor resolved under the IBC.

Usage
-----
    python pipelines/s079_ibbi.py --mode latest        # most recent 2 editions
    python pipelines/s079_ibbi.py --mode backfill      # all 37 editions
    python pipelines/s079_ibbi.py --periods 2026Q1 2025Q4
"""

from __future__ import annotations

import argparse
import io
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import pdfplumber
import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.common import catalog  # noqa: E402
from src.common.settings import Settings  # noqa: E402
from src.common.storage import BronzeStore  # noqa: E402
from src.connectors.ibbi_listing import Newsletter, discover, fetch_pdf  # noqa: E402
from src.extractors.ibbi_cirp import extract_cases  # noqa: E402

SOURCE_ID = "S-079"
CONFIG_PATH = Path(__file__).resolve().parents[1] / "config" / "sources" / "S-079_ibbi_newsletters.yaml"
SILVER_TABLE = "silver.ibbi_cirp_cases"

# Claims basis changed with the 2022 editions — see config schema_eras.
FC_ONLY_MAX_YEAR = 2021


def load_config() -> dict:
    with CONFIG_PATH.open(encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def claims_basis(year: int | None) -> str:
    if year is None:
        return "unknown"
    return "financial_creditors_only" if year <= FC_ONLY_MAX_YEAR else "all_creditors"


def process_edition(
    *, nl: Newsletter, store: BronzeStore, con, run_id: str, cfg: dict
) -> dict:
    started = datetime.now(timezone.utc)
    print(f"\n── {nl.slug}  ({nl.period})  {nl.size}")

    payload = fetch_pdf(nl.url, timeout=cfg["fetch"]["timeout_seconds"])
    bronze = store.put_bytes(
        source_id=SOURCE_ID,
        filename=f"ibbi_newsletter_{nl.slug}.pdf",
        payload=payload,
        source_url=nl.url,
        content_type="application/pdf",
        notes=f"period={nl.period}; title={nl.title[:80]}",
    )
    print(f"   bronze    {bronze.key}  ({bronze.size_bytes/1_048_576:.1f} MB)")

    with pdfplumber.open(io.BytesIO(payload)) as pdf:
        cases, stats = extract_cases(pdf, nl.period)

    if not cases:
        print("   extract   no case rows found (expected for pre-2019 editions)")
        catalog.log_run(
            con, run_id=run_id, source_id=SOURCE_ID, started_at=started, status="success",
            bronze_key=bronze.key, source_url=nl.url, rows_fetched=0, rows_loaded=0,
            target_table=SILVER_TABLE, message="no case rows",
        )
        return {"slug": nl.slug, "rows": 0, "ok": 0, "failed": 0}

    rows = []
    for c in cases:
        d = c.as_dict()
        d["source_id"] = SOURCE_ID
        d["source_year"] = nl.year
        d["source_quarter"] = nl.quarter
        d["source_url"] = nl.url
        d["bronze_key"] = bronze.key
        d["claims_basis"] = claims_basis(nl.year)
        d["_fetched_at"] = datetime.now(timezone.utc)
        rows.append(d)
    df = pd.DataFrame(rows)

    ok = int((df["arithmetic_ok"] == True).sum())      # noqa: E712
    failed = int((df["arithmetic_ok"] == False).sum())  # noqa: E712
    checkable = ok + failed
    rate = ok / checkable if checkable else 1.0
    print(f"   extract   {len(df)} cases · arithmetic OK {ok}, failed {failed} "
          f"({rate:.0%} of checkable)  pages {stats['pages_scanned']}")

    con.execute("CREATE SCHEMA IF NOT EXISTS silver")
    con.register("incoming_ibbi", df)
    exists = con.execute(
        "SELECT count(*) FROM information_schema.tables "
        "WHERE table_schema='silver' AND table_name='ibbi_cirp_cases'"
    ).fetchone()[0]
    if not exists:
        con.execute(f"CREATE TABLE {SILVER_TABLE} AS SELECT * FROM incoming_ibbi")
    else:
        # Idempotent per edition
        con.execute(f"DELETE FROM {SILVER_TABLE} WHERE source_period = ?", [nl.period])
        con.execute(f"INSERT INTO {SILVER_TABLE} BY NAME SELECT * FROM incoming_ibbi")
    con.unregister("incoming_ibbi")
    print(f"   silver    {len(df)} rows → {SILVER_TABLE}")

    catalog.record_qa(
        con, run_id=run_id, source_id=SOURCE_ID,
        check_name="arithmetic_self_consistency",
        observed=round(rate, 4), expected=0.90, tolerance=None,
        passed=rate >= 0.90 or checkable == 0,
        detail=f"{nl.slug}: {ok} ok / {failed} failed of {len(df)} cases",
    )
    catalog.log_run(
        con, run_id=run_id, source_id=SOURCE_ID, started_at=started, status="success",
        bronze_key=bronze.key, source_url=nl.url,
        rows_fetched=len(cases), rows_loaded=len(df), rows_rejected=failed,
        target_table=SILVER_TABLE,
        message=f"period={nl.period}; arithmetic_ok_rate={rate:.3f}",
    )
    return {"slug": nl.slug, "rows": len(df), "ok": ok, "failed": failed}


def reconcile(con, run_id: str) -> list[tuple[str, bool, str]]:
    """Check the assembled panel against IBBI's own published cumulative totals."""
    results: list[tuple[str, bool, str]] = []

    total, distinct = con.execute(
        f"SELECT count(*), count(DISTINCT lower(corporate_debtor)) FROM {SILVER_TABLE}"
    ).fetchone()
    results.append((
        "case_count", True,
        f"{total:,} rows, {distinct:,} distinct corporate debtors "
        f"(IBBI reports 1,419 resolution plans to Mar-2026)",
    ))

    ok, failed = con.execute(
        f"SELECT sum(CASE WHEN arithmetic_ok THEN 1 ELSE 0 END), "
        f"       sum(CASE WHEN arithmetic_ok = FALSE THEN 1 ELSE 0 END) FROM {SILVER_TABLE}"
    ).fetchone()
    ok, failed = ok or 0, failed or 0
    rate = ok / (ok + failed) if (ok + failed) else 1.0
    results.append((
        "arithmetic_self_consistency", rate >= 0.90,
        f"{rate:.1%} of checkable rows reconcile ({ok:,} ok / {failed:,} failed)",
    ))

    # Aggregate realisation, restricted to validated all-creditor rows so the
    # FC-only era cannot contaminate the comparison with published figures.
    row = con.execute(
        f"""
        SELECT sum(admitted_claims_cr), sum(realisable_amount_cr), count(*)
        FROM {SILVER_TABLE}
        WHERE arithmetic_ok AND claims_basis = 'all_creditors'
          AND admitted_claims_cr IS NOT NULL AND realisable_amount_cr IS NOT NULL
        """
    ).fetchone()
    claims, realised, n = row[0] or 0, row[1] or 0, row[2] or 0
    if claims:
        pct = 100.0 * realised / claims
        # IBBI cumulative to Mar-2026: 30.56% of admitted claims
        plausible = 15.0 <= pct <= 50.0
        results.append((
            "aggregate_realisation_plausible", plausible,
            f"{pct:.2f}% realisation across {n:,} validated cases "
            f"(IBBI cumulative published: 30.56%)",
        ))

    return results


def main() -> int:
    parser = argparse.ArgumentParser(description="IBBI newsletter pipeline (S-079)")
    parser.add_argument("--mode", choices=["latest", "backfill", "periods"], default="latest")
    parser.add_argument("--periods", nargs="*", default=[])
    parser.add_argument("--limit", type=int, default=0)
    args = parser.parse_args()

    cfg = load_config()
    settings = Settings.from_env()
    run_id = uuid.uuid4().hex[:12]

    print("=" * 70)
    print(f"S-079 · IBBI newsletters   run {run_id}   mode={args.mode}")
    print("=" * 70)

    editions = discover(rate_limit=cfg["fetch"]["rate_limit_seconds"])
    print(f"\nDiscovered {len(editions)} English editions "
          f"({editions[-1].period} … {editions[0].period})")

    if args.mode == "latest":
        targets = editions[:2]
    elif args.mode == "periods":
        targets = [e for e in editions if e.slug in args.periods]
    else:
        targets = editions
    if args.limit:
        targets = targets[: args.limit]
    print(f"Processing {len(targets)} edition(s)")

    store = BronzeStore(settings)
    processed: list[dict] = []

    with catalog.connect(settings) as con:
        catalog.ensure_schemas(con)
        catalog.register_source(con, cfg)

        for nl in targets:
            try:
                processed.append(process_edition(
                    nl=nl, store=store, con=con, run_id=run_id, cfg=cfg
                ))
            except Exception as exc:
                print(f"   ✗ FAILED  {type(exc).__name__}: {exc}")
                catalog.log_run(
                    con, run_id=run_id, source_id=SOURCE_ID,
                    started_at=datetime.now(timezone.utc), status="failed",
                    source_url=nl.url, target_table=SILVER_TABLE,
                    message=f"{nl.slug}: {type(exc).__name__}: {exc}",
                )

        loaded = sum(p["rows"] for p in processed)
        print("\n" + "=" * 70)
        print(f"Loaded {loaded:,} case rows from {len(processed)} edition(s)")

        print("\nReconciliation")
        print("-" * 70)
        results = reconcile(con, run_id)
        for name, passed, detail in results:
            print(f"  [{'PASS' if passed else 'FAIL'}] {name}: {detail}")
            catalog.record_qa(
                con, run_id=run_id, source_id=SOURCE_ID, check_name=name,
                observed=1.0 if passed else 0.0, expected=1.0, tolerance=None,
                passed=passed, detail=detail,
            )

        failed_checks = [r for r in results if not r[1]]
        if failed_checks:
            print(f"\n  {len(failed_checks)} check(s) failed.\n")
            return 1

        con.execute(
            "UPDATE catalog.source_registry SET last_success_at = ? WHERE source_id = ?",
            [datetime.now(timezone.utc), SOURCE_ID],
        )
        print("\n  All checks passed.\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
