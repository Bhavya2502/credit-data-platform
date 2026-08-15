"""Kaggle ingestion — fetch → bronze → silver, one target at a time.

Generic across the five borrower-level datasets: the download and unpack
mechanics are identical, only the contents differ. Each archive member becomes
its own silver table, and the pipeline reports the schema it discovered rather
than assuming one — these are third-party datasets whose structure we have not
verified in advance, and guessing is how the Bondora schema bug happened.

Size discipline
---------------
Amex is ~16 GB uncompressed against a 10 GB R2 free tier, so the big archives
cannot all be stored raw. `--max-bronze-mb` caps what is written to bronze and
`--sample-rows` caps what is parsed into silver. Both are recorded on every row
so a sampled table can never be mistaken for a complete one.

This is a deliberate, documented departure from ADR-003 (immutable full bronze)
for oversized third-party archives only. Our own primary sources are stored whole.

Usage
-----
    python pipelines/kaggle_ingest.py --target ltfs_vehicle
    python pipelines/kaggle_ingest.py --target amex_default --sample-rows 2000000
    python pipelines/kaggle_ingest.py --list
"""

from __future__ import annotations

import argparse
import io
import sys
import tempfile
import uuid
import zipfile
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.common import catalog  # noqa: E402
from src.common.settings import Settings  # noqa: E402
from src.common.storage import BronzeStore  # noqa: E402
from src.connectors.kaggle_api import TARGETS, download, probe  # noqa: E402

SOURCE_IDS = {
    "amex_default": "S-019",
    "home_credit_stability": "S-018",
    "home_credit_default": "S-017",
    "lending_club": "S-013",
    "ltfs_vehicle": "S-103",
}

READABLE = (".csv", ".parquet", ".txt", ".tsv")


def find_target(key: str):
    for t in TARGETS:
        if t.key == key:
            return t
    raise SystemExit(f"Unknown target '{key}'. Options: {', '.join(t.key for t in TARGETS)}")


def read_member(zf: zipfile.ZipFile, name: str, sample_rows: int | None) -> pd.DataFrame | None:
    """Read one archive member, sampling from the top if capped."""
    lower = name.lower()
    try:
        if lower.endswith(".parquet"):
            with zf.open(name) as fh:
                data = io.BytesIO(fh.read())
            df = pd.read_parquet(data)
            if sample_rows and len(df) > sample_rows:
                df = df.head(sample_rows)
            return df
        if lower.endswith((".csv", ".txt", ".tsv")):
            sep = "\t" if lower.endswith(".tsv") else ","
            # Encoding is not guaranteed. Home Credit's column-description file
            # is cp1252 and failed outright on a UTF-8-only read, silently
            # costing us the data dictionary for 128 columns — and dictionaries
            # have been the most valuable part of every dataset so far (LTFS's
            # revealed seven sentinel values masquerading as bureau scores).
            # Try the common encodings before giving up.
            last_error: Exception | None = None
            for encoding in ("utf-8", "utf-8-sig", "cp1252", "latin-1"):
                try:
                    with zf.open(name) as fh:
                        df = pd.read_csv(
                            fh, sep=sep, nrows=sample_rows or None,
                            low_memory=False, on_bad_lines="skip",
                            encoding=encoding,
                        )
                    if encoding != "utf-8":
                        print(f"     (read {Path(name).name} as {encoding})")
                    return df
                except UnicodeDecodeError as exc:
                    last_error = exc
                    continue
            if last_error:
                raise last_error
    except Exception as exc:
        print(f"     ! could not read {name}: {type(exc).__name__}: {exc}")
    return None


# Entity keys used by the panel datasets. When a row cap truncates a file, the
# final entity is almost always cut mid-history.
ENTITY_KEYS = ("customer_ID", "customer_id", "SK_ID_CURR", "case_id", "SK_ID_PREV")


def trim_partial_entity(df: pd.DataFrame, capped: bool) -> tuple[pd.DataFrame, str]:
    """Drop the last entity's rows when a row cap has truncated the file.

    Amex and Home Credit Stability are monthly PANELS: many rows per customer.
    Reading the first N rows cuts the final customer mid-history, producing a
    borrower whose statement sequence just stops — which looks like a real
    observation and silently corrupts any behavioural feature built from it
    (recency, trend, months-on-book).

    Cutting at the entity boundary costs one customer and preserves the
    integrity of every remaining history.
    """
    if not capped:
        return df, ""
    for col in ENTITY_KEYS:
        if col in df.columns and len(df) > 1:
            last = df[col].iloc[-1]
            keep = df[df[col] != last]
            if len(keep) and len(keep) < len(df):
                return keep, (
                    f"trimmed {len(df) - len(keep):,} rows of the final (truncated) "
                    f"{col} to keep every retained history complete"
                )
            break
    return df, ""


def safe_table_name(key: str, member: str) -> str:
    stem = Path(member).stem.lower()
    stem = "".join(c if c.isalnum() else "_" for c in stem).strip("_")
    return f"silver.kaggle_{key}_{stem}"[:120]


def main() -> int:
    parser = argparse.ArgumentParser(description="Kaggle dataset ingestion")
    parser.add_argument("--target", help="target key, e.g. ltfs_vehicle")
    parser.add_argument("--list", action="store_true", help="list available targets")
    parser.add_argument("--sample-rows", type=int, default=0,
                        help="cap rows parsed per file (0 = all)")
    parser.add_argument("--max-bronze-mb", type=int, default=2048,
                        help="skip raw bronze upload above this size")
    args = parser.parse_args()

    if args.list or not args.target:
        print("Available targets:")
        for t in TARGETS:
            print(f"  {t.key:<24} {SOURCE_IDS.get(t.key,'?'):<7} {t.kind:<12} {t.note}")
        return 0

    target = find_target(args.target)
    source_id = SOURCE_IDS.get(target.key, "S-000")
    sample = args.sample_rows or None

    import os
    username = os.environ.get("KAGGLE_USERNAME", "")
    key = os.environ.get("KAGGLE_KEY", "")

    settings = Settings.from_env()
    run_id = uuid.uuid4().hex[:12]
    started = datetime.now(timezone.utc)

    print("=" * 74)
    print(f"{source_id} · Kaggle {target.key}   run {run_id}")
    print("=" * 74)
    print(f"\n  {target.note}\n")

    pr = probe(target, username=username, key=key)
    if not pr.accessible:
        print(f"  ✗ not accessible (HTTP {pr.status_code}) — {pr.reason}")
        return 1
    print(f"  access    HTTP {pr.status_code} — reachable")

    tmp = Path(tempfile.mkdtemp(prefix="kaggle_"))
    archive = download(target, username=username, key=key, dest_dir=tmp)
    size_mb = archive.stat().st_size / 1_048_576
    print(f"  archive   {archive.name}  {size_mb:.1f} MB")

    store = BronzeStore(settings)
    bronze_key = ""
    if size_mb <= args.max_bronze_mb:
        rec = store.put_bytes(
            source_id=source_id,
            filename=f"{target.key}.zip",
            payload=archive.read_bytes(),
            source_url=target.download_url,
            content_type="application/zip",
            notes=f"kaggle {target.kind} {target.ref}",
        )
        bronze_key = rec.key
        print(f"  bronze    {rec.key}")
    else:
        print(f"  bronze    SKIPPED — {size_mb:.0f} MB exceeds the {args.max_bronze_mb} MB cap; "
              f"silver rows record this so the gap is visible")

    loaded: list[tuple[str, int, int]] = []
    with zipfile.ZipFile(archive) as zf:
        members = [m for m in zf.namelist()
                   if m.lower().endswith(READABLE) and not m.endswith("/")]
        print(f"  contents  {len(zf.namelist())} entries, {len(members)} readable\n")

        with catalog.connect(settings) as con:
            catalog.ensure_schemas(con)
            con.execute("CREATE SCHEMA IF NOT EXISTS silver")

            for member in sorted(members):
                info = zf.getinfo(member)
                df = read_member(zf, member, sample)
                if df is None or df.empty:
                    continue

                was_capped = bool(sample and len(df) >= sample)
                df, trim_note = trim_partial_entity(df, was_capped)
                if trim_note:
                    print(f"     {trim_note}")

                df["_source_id"] = source_id
                df["_kaggle_ref"] = target.ref
                df["_archive_member"] = member
                df["_is_sampled"] = was_capped
                df["_bronze_key"] = bronze_key
                df["_fetched_at"] = datetime.now(timezone.utc)

                table = safe_table_name(target.key, member)
                con.register("incoming_kaggle", df)
                con.execute(f"CREATE OR REPLACE TABLE {table} AS SELECT * FROM incoming_kaggle")
                con.unregister("incoming_kaggle")

                flag = " [SAMPLED]" if df["_is_sampled"].iloc[0] else ""
                print(f"  {member[:44]:<46} {len(df):>9,} x {len(df.columns):>3}"
                      f"  ({info.file_size/1_048_576:.0f} MB){flag}")
                print(f"     -> {table}")
                loaded.append((table, len(df), len(df.columns)))

            total_rows = sum(r for _, r, _ in loaded)
            catalog.log_run(
                con, run_id=run_id, source_id=source_id, started_at=started,
                status="success" if loaded else "failed",
                bronze_key=bronze_key, source_url=target.download_url,
                rows_fetched=total_rows, rows_loaded=total_rows,
                target_table=", ".join(t for t, _, _ in loaded)[:400],
                message=f"{len(loaded)} tables; sampled={bool(sample)}",
            )
            catalog.record_qa(
                con, run_id=run_id, source_id=source_id, check_name="tables_loaded",
                observed=float(len(loaded)), expected=1.0, tolerance=None,
                passed=bool(loaded),
                detail=f"{len(loaded)} tables, {total_rows:,} rows from {target.ref}",
            )

    print("\n" + "=" * 74)
    print(f"Loaded {len(loaded)} table(s), {sum(r for _, r, _ in loaded):,} rows total")
    if sample:
        print(f"NOTE: capped at {sample:,} rows per file — _is_sampled marks affected rows")
    return 0 if loaded else 1


if __name__ == "__main__":
    raise SystemExit(main())
