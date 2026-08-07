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
from src.extractors.ibbi_liquidation import extract_cases as extract_liquidation  # noqa: E402
from src.extractors.vision import (  # noqa: E402
    DEFAULT_MODEL, extract_page, render_page_png, to_cirp_cases,
)

SOURCE_ID = "S-079"
CONFIG_PATH = Path(__file__).resolve().parents[1] / "config" / "sources" / "S-079_ibbi_newsletters.yaml"
SILVER_TABLE = "silver.ibbi_cirp_cases"
LIQ_TABLE = "silver.ibbi_liquidation_cases"

# Claims basis changed with the 2022 editions — see config schema_eras.
FC_ONLY_MAX_YEAR = 2021


def load_config() -> dict:
    with CONFIG_PATH.open(encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def claims_basis(year: int | None) -> str:
    if year is None:
        return "unknown"
    return "financial_creditors_only" if year <= FC_ONLY_MAX_YEAR else "all_creditors"


def vision_extract(payload: bytes, nl: Newsletter, cfg: dict) -> list:
    """Read an image-only edition with a vision model (archetype H).

    Scans a bounded page window rather than the whole document: the resolution
    table has sat in the Corporate Processes section of every edition, so
    scanning ~12 pages instead of 30 halves the cost with no loss of coverage.
    Pages that do not contain the table return no rows and cost a few hundred
    tokens each.
    """
    import fitz

    vcfg = (cfg.get("extraction") or {}).get("vision") or {}
    first = int(vcfg.get("page_from", 10))
    last = int(vcfg.get("page_to", 26))
    dpi = int(vcfg.get("dpi", 200))
    model = vcfg.get("model", DEFAULT_MODEL)

    doc = fitz.open(stream=payload, filetype="pdf")
    found: list = []
    tokens_in = tokens_out = 0
    cost = 0.0
    scanned = 0

    try:
        for idx in range(first - 1, min(last, len(doc))):
            png = render_page_png(doc, idx, dpi=dpi)
            result = extract_page(png, page_number=idx + 1, model=model)
            scanned += 1
            if result.error:
                print(f"     p{idx+1}: vision error — {result.error[:110]}")
                continue
            tokens_in += result.prompt_tokens
            tokens_out += result.completion_tokens
            if result.cost_usd:
                cost += float(result.cost_usd)
            if result.rows:
                cases = to_cirp_cases(result, nl.period, idx + 1)
                if cases:
                    found.extend(cases)
                    print(f"     p{idx+1}: {len(cases)} case rows")
    finally:
        doc.close()

    ok = sum(1 for c in found if c.arithmetic_ok is True)
    bad = sum(1 for c in found if c.arithmetic_ok is False)
    print(f"   vision    {scanned} pages scanned · {len(found)} rows "
          f"(arithmetic ok {ok}, failed {bad}) · tokens {tokens_in:,}/{tokens_out:,}"
          + (f" · ${cost:.4f}" if cost else ""))
    return found


def load_liquidation(con, liq_cases, nl: Newsletter, bronze_key: str, run_id: str) -> int:
    """Load liquidation outcomes into their own silver table.

    Validation here is structural only — this table prints no percentages to
    reconcile against (see the extractor docstring), so validation_basis is
    carried on every row to keep the weaker evidential standard visible.
    """
    rows = []
    for c in liq_cases:
        d = c.as_dict()
        d["source_id"] = SOURCE_ID
        d["source_year"] = nl.year
        d["source_quarter"] = nl.quarter
        d["source_url"] = nl.url
        d["bronze_key"] = bronze_key
        d["_fetched_at"] = datetime.now(timezone.utc)
        rows.append(d)
    df = pd.DataFrame(rows)

    con.execute("CREATE SCHEMA IF NOT EXISTS silver")
    con.register("incoming_liq", df)
    exists = con.execute(
        "SELECT count(*) FROM information_schema.tables "
        "WHERE table_schema='silver' AND table_name='ibbi_liquidation_cases'"
    ).fetchone()[0]
    if not exists:
        con.execute(f"CREATE TABLE {LIQ_TABLE} AS SELECT * FROM incoming_liq")
    else:
        con.execute(f"DELETE FROM {LIQ_TABLE} WHERE source_period = ?", [nl.period])
        con.execute(f"INSERT INTO {LIQ_TABLE} BY NAME SELECT * FROM incoming_liq")
    con.unregister("incoming_liq")

    ok = int((df["structural_ok"] == True).sum())   # noqa: E712
    bad = int((df["structural_ok"] == False).sum()) # noqa: E712
    print(f"   liq       {len(df)} liquidation rows -> {LIQ_TABLE} (structural ok {ok}, failed {bad})")
    catalog.record_qa(
        con, run_id=run_id, source_id=SOURCE_ID, check_name="liquidation_structural",
        observed=float(ok), expected=float(len(df)), tolerance=None,
        passed=bad == 0, detail=f"{nl.slug}: {ok} ok / {bad} failed of {len(df)}",
    )
    return len(df)


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
        text_chars = sum(
            len(pdf.pages[i].extract_text() or "")
            for i in range(0, len(pdf.pages), max(1, len(pdf.pages) // 5))
        )

    extraction_method = "deterministic"

    # Escalate to vision only when the document has no text layer at all
    # (ADR-005: deterministic first, vision last). Seven IBBI editions are
    # page scans; a parser cannot read what has no characters.
    if not cases and text_chars < 200:
        print(f"   note      no text layer ({text_chars} chars) — escalating to vision")
        cases = vision_extract(payload, nl, cfg)
        extraction_method = "vision"
        stats = {"pages_scanned": ["vision"], "rows_parsed": len(cases), "totals_rows": []}

    # Liquidation outcomes — gone-concern recovery, a separate table with its
    # own grain. Extracted from the same bronze object, loaded independently so
    # a failure in one table never blocks the other.
    try:
        with pdfplumber.open(io.BytesIO(payload)) as pdf:
            liq_cases, liq_stats = extract_liquidation(pdf, nl.period)
        if liq_cases:
            load_liquidation(con, liq_cases, nl, bronze.key, run_id)
    except Exception as exc:
        print(f"   liq       FAILED {type(exc).__name__}: {exc}")

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
        d["extraction_method"] = extraction_method
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

    exists = con.execute(
        "SELECT count(*) FROM information_schema.tables "
        "WHERE table_schema='silver' AND table_name='ibbi_cirp_cases'"
    ).fetchone()[0]
    if not exists:
        # Nothing loaded yet (e.g. a filtered run that matched no editions).
        # Report it rather than raising a catalog error from a downstream query.
        return [("table_exists", False, f"{SILVER_TABLE} does not exist — no editions loaded")]

    total, distinct = con.execute(
        f"SELECT count(*), count(DISTINCT lower(corporate_debtor)) FROM {SILVER_TABLE}"
    ).fetchone()
    results.append((
        "case_count", True,
        f"{total:,} rows, {distinct:,} distinct corporate debtors "
        f"(IBBI reports 1,419 resolution plans to Mar-2026)",
    ))

    # Thresholds are method-aware. Deterministic parsing is reproducible and
    # held to 90%; vision transcription of page scans is inherently noisier and
    # held to 80%. In both cases rows that fail are quarantined rather than
    # dropped, and the gold panel consumes only arithmetic_ok rows — so the
    # threshold governs whether an extraction run is trustworthy overall, not
    # whether any individual bad row can leak downstream.
    thresholds = {"deterministic": 0.90, "vision": 0.80}
    for method, floor in thresholds.items():
        row = con.execute(
            f"SELECT sum(CASE WHEN arithmetic_ok THEN 1 ELSE 0 END), "
            f"       sum(CASE WHEN arithmetic_ok = FALSE THEN 1 ELSE 0 END) "
            f"FROM {SILVER_TABLE} WHERE extraction_method = ?", [method]
        ).fetchone()
        ok, failed = row[0] or 0, row[1] or 0
        if ok + failed == 0:
            continue
        rate = ok / (ok + failed)
        results.append((
            f"arithmetic_self_consistency[{method}]", rate >= floor,
            f"{rate:.1%} of checkable rows reconcile ({ok:,} ok / {failed:,} failed), "
            f"floor {floor:.0%}",
        ))

    quarantined = con.execute(
        f"SELECT count(*) FROM {SILVER_TABLE} WHERE arithmetic_ok = FALSE"
    ).fetchone()[0]
    results.append((
        "quarantine_recorded", True,
        f"{quarantined:,} rows failed self-check — retained with reason, excluded from gold",
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
