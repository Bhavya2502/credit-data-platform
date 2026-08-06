"""S-057 · FDIC BankFind — fetch → bronze → silver → reconcile.

Bank-level quarterly credit performance for every US insured institution,
1992 to present. Idempotent and resumable: re-running a loaded quarter replaces
that quarter only, so a half-finished backfill is simply resumed.

Usage
-----
    python pipelines/s057_fdic.py --mode latest      # most recent quarter
    python pipelines/s057_fdic.py --mode backfill    # full history from 1992
    python pipelines/s057_fdic.py --quarters 20241231 20240930
"""

from __future__ import annotations

import argparse
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.common import catalog  # noqa: E402
from src.common.settings import Settings  # noqa: E402
from src.common.storage import BronzeStore  # noqa: E402
from src.connectors.rest_api import FdicConnector, quarter_ends  # noqa: E402
from src.quality.checks import CheckResult, run_fdic_checks  # noqa: E402

SOURCE_ID = "S-057"
CONFIG_PATH = Path(__file__).resolve().parents[1] / "config" / "sources" / "S-057_fdic_bankfind.yaml"
SILVER_TABLE = "silver.fdic_bank_financials"

# Numeric columns are stored as DOUBLE; identity columns as VARCHAR.
IDENTITY_COLS = ["CERT", "REPDTE", "NAME", "CITY", "STALP", "STNAME",
                 "BKCLASS", "SPECGRPDESC", "ACTIVE", "CB"]


def load_config() -> dict:
    with CONFIG_PATH.open(encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def curated_columns(cfg: dict) -> list[str]:
    cols: list[str] = []
    for group in cfg["fields"].values():
        cols.extend(group)
    # dict.fromkeys preserves order while removing any duplicates across groups
    return list(dict.fromkeys(cols))


def to_frame(
    records: list[dict], columns: list[str], repdte: str
) -> tuple[pd.DataFrame, list[str]]:
    """Project the API response onto curated columns, typed and provenanced.

    Fields absent in a given era (e.g. CET1 before Basel III) become NULL
    rather than being dropped — an era gap is information, not an error.
    """
    df = pd.DataFrame.from_records(records)

    missing = [c for c in columns if c not in df.columns]
    for col in missing:
        df[col] = None
    df = df[columns].copy()

    for col in columns:
        if col not in IDENTITY_COLS:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    df["CERT"] = df["CERT"].astype(str)
    df["REPDTE"] = df["REPDTE"].astype(str)
    df["report_date"] = pd.to_datetime(df["REPDTE"], format="%Y%m%d", errors="coerce")
    df["report_year"] = df["report_date"].dt.year
    df["report_quarter"] = df["report_date"].dt.quarter

    # Provenance on every row (ADR-006)
    df["_source_id"] = SOURCE_ID
    df["_fetched_at"] = datetime.now(timezone.utc)
    df["_source_url"] = f"https://api.fdic.gov/banks/financials?filters=REPDTE:{repdte}"

    return df, missing


def write_silver(con, df: pd.DataFrame, repdte: str) -> int:
    """Replace one quarter's rows. Idempotent by construction."""
    con.execute("CREATE SCHEMA IF NOT EXISTS silver")
    con.register("incoming_df", df)

    exists = con.execute(
        "SELECT count(*) FROM information_schema.tables "
        "WHERE table_schema='silver' AND table_name='fdic_bank_financials'"
    ).fetchone()[0]

    if not exists:
        con.execute(f"CREATE TABLE {SILVER_TABLE} AS SELECT * FROM incoming_df")
    else:
        con.execute(f"DELETE FROM {SILVER_TABLE} WHERE REPDTE = ?", [repdte])
        con.execute(f"INSERT INTO {SILVER_TABLE} SELECT * FROM incoming_df")

    con.unregister("incoming_df")
    return len(df)


def process_quarter(
    *, repdte: str, connector: FdicConnector, store: BronzeStore, con,
    columns: list[str], run_id: str,
) -> dict:
    started = datetime.now(timezone.utc)
    print(f"\n── {repdte} " + "─" * 46)

    records, response, api_total = connector.fetch_quarter(repdte)
    print(f"   fetched   {len(records):,} records (API total {api_total:,}) in {response.fetched_seconds}s")

    if not records:
        catalog.log_run(
            con, run_id=run_id, source_id=SOURCE_ID, started_at=started,
            status="success", source_url=response.url, rows_fetched=0, rows_loaded=0,
            target_table=SILVER_TABLE, message="no records for this report date",
        )
        print("   skipped   no records")
        return {"repdte": repdte, "rows": 0, "skipped": True}

    bronze = store.put_bytes(
        source_id=SOURCE_ID,
        filename=f"fdic_financials_{repdte}.json.gz",
        payload=response.gzipped(),
        source_url=response.url,
        http_status=response.status_code,
        content_type="application/gzip",
        notes=f"{len(records)} records; api_total={api_total}",
    )
    print(f"   bronze    {bronze.key}  ({bronze.size_bytes/1_048_576:.1f} MB gz)")

    df, missing = to_frame(records, columns, repdte)
    if missing:
        print(f"   note      {len(missing)} field(s) absent this era → NULL: {', '.join(missing[:6])}"
              + ("…" if len(missing) > 6 else ""))

    rows = write_silver(con, df, repdte)
    print(f"   silver    {rows:,} rows → {SILVER_TABLE}")

    completeness_ok = rows == api_total
    catalog.record_qa(
        con, run_id=run_id, source_id=SOURCE_ID,
        check_name="row_count_matches_api_total",
        observed=float(rows), expected=float(api_total), tolerance=0.0,
        passed=completeness_ok,
        detail=f"REPDTE {repdte}",
    )
    if not completeness_ok:
        print(f"   ⚠ WARN    row count {rows:,} != API total {api_total:,}")

    catalog.log_run(
        con, run_id=run_id, source_id=SOURCE_ID, started_at=started,
        status="success", bronze_key=bronze.key, source_url=response.url,
        rows_fetched=len(records), rows_loaded=rows, rows_rejected=0,
        target_table=SILVER_TABLE,
        message=f"api_total={api_total}; missing_fields={len(missing)}",
    )
    return {"repdte": repdte, "rows": rows, "skipped": False}


def main() -> int:
    parser = argparse.ArgumentParser(description="FDIC BankFind pipeline (S-057)")
    parser.add_argument("--mode", choices=["latest", "backfill", "quarters"], default="latest")
    parser.add_argument("--quarters", nargs="*", default=[])
    parser.add_argument("--start-year", type=int, default=1992)
    parser.add_argument("--limit", type=int, default=0, help="cap quarters processed (0 = no cap)")
    args = parser.parse_args()

    cfg = load_config()
    columns = curated_columns(cfg)
    settings = Settings.from_env()
    run_id = uuid.uuid4().hex[:12]

    print("=" * 68)
    print(f"S-057 · FDIC BankFind   run {run_id}   mode={args.mode}")
    print("=" * 68)

    connector = FdicConnector(
        headers=cfg["fetch"]["headers"],
        rate_limit_seconds=cfg["fetch"]["rate_limit_seconds"],
        timeout_seconds=cfg["fetch"]["timeout_seconds"],
        max_retries=cfg["fetch"]["retries"],
    )
    store = BronzeStore(settings)

    # Latest published quarter trails "today" by roughly two months.
    today = datetime.now(timezone.utc)
    latest_candidates = quarter_ends(today.year - 1, 1, today.strftime("%Y%m%d"))

    if args.mode == "quarters":
        targets = args.quarters
    elif args.mode == "backfill":
        targets = quarter_ends(args.start_year, 4, today.strftime("%Y%m%d"))
    else:
        targets = latest_candidates[-2:]  # last two, so a late publication is caught

    if args.limit:
        targets = targets[: args.limit]
    print(f"\nQuarters to process: {len(targets)}  ({targets[0]} … {targets[-1]})")

    processed: list[dict] = []
    with catalog.connect(settings) as con:
        catalog.ensure_schemas(con)
        catalog.register_source(con, cfg)

        for repdte in targets:
            try:
                processed.append(
                    process_quarter(
                        repdte=repdte, connector=connector, store=store, con=con,
                        columns=columns, run_id=run_id,
                    )
                )
            except Exception as exc:
                print(f"   ✗ FAILED  {type(exc).__name__}: {exc}")
                catalog.log_run(
                    con, run_id=run_id, source_id=SOURCE_ID,
                    started_at=datetime.now(timezone.utc), status="failed",
                    target_table=SILVER_TABLE, message=f"{type(exc).__name__}: {exc}",
                )
                # Continue: one bad quarter must not abandon a long backfill.

        loaded = sum(p["rows"] for p in processed)
        print("\n" + "=" * 68)
        print(f"Loaded {loaded:,} rows across {len([p for p in processed if not p['skipped']])} quarters")

        print("\nReconciliation")
        print("-" * 68)
        results: list[CheckResult] = run_fdic_checks(con, SILVER_TABLE)
        for r in results:
            print(f"  [{'PASS' if r.passed else 'FAIL'}] {r.name}: {r.detail}")
            catalog.record_qa(
                con, run_id=run_id, source_id=SOURCE_ID, check_name=r.name,
                observed=r.observed, expected=r.expected, tolerance=r.tolerance,
                passed=r.passed, detail=r.detail,
            )

        failed = [r for r in results if not r.passed]
        if failed:
            print(f"\n  {len(failed)} check(s) failed — dataset is NOT considered loaded.")
            return 1

        con.execute(
            "UPDATE catalog.source_registry SET last_success_at = ? WHERE source_id = ?",
            [datetime.now(timezone.utc), SOURCE_ID],
        )
        print("\n  All checks passed — dataset validated.\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
