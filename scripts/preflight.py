"""Preflight check — run before building pipelines.

Verifies three things from inside the GitHub Actions runner:
  1. Cloudflare R2 credentials work and the bucket is writable
  2. MotherDuck credentials work and schemas can be created
  3. Which fetch route reaches data.sba.gov (see S-012 config: the dev sandbox
     received HTTP 404 for every programmatic request, consistent with
     bot-blocking or geo-blocking of non-US egress)

Prints a readable report and exits non-zero if a credential check fails.
Source-reachability results are informational — they decide connector design,
they don't fail the run.
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.common import catalog  # noqa: E402
from src.common.settings import Settings  # noqa: E402
from src.common.storage import BronzeStore  # noqa: E402

BROWSER_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}

POLITE_HEADERS = {
    "User-Agent": "credit-data-platform/0.1 (internal research; contact via repo owner)",
    "Accept": "*/*",
}

SBA_TARGETS = [
    ("landing page (browser UA)", "https://data.sba.gov/en/dataset/7-a-504-foia", BROWSER_HEADERS),
    ("landing page (polite UA)", "https://data.sba.gov/en/dataset/7-a-504-foia", POLITE_HEADERS),
    (
        "direct CSV (browser UA)",
        "https://data.sba.gov/dataset/0ff8e8e9-b967-4f4e-987c-6ac78c575087/resource/"
        "d67d3ccb-2002-4134-a288-481b51cd3479/download/foia-7a-fy2020-present-asof-250331.csv",
        BROWSER_HEADERS,
    ),
    ("data.gov mirror", "https://catalog.data.gov/dataset/sba-7a-and-504-loan-data-reports", BROWSER_HEADERS),
]

# Indian sources. S-079 hit httpx.ConnectTimeout against ibbi.gov.in from a
# US-east runner while the same host downloads normally from a dev machine —
# testing whether Indian government hosts are reachable from US datacentres,
# and how slow they are when they do respond.
INDIA_TARGETS = [
    ("IBBI publications listing", "https://ibbi.gov.in/publication", BROWSER_HEADERS),
    ("IBBI home", "https://ibbi.gov.in/", BROWSER_HEADERS),
    ("IBBI newsletter PDF (range req)", "https://ibbi.gov.in/uploads/publication/62bde7e8797a6a91abc577742098b840.pdf", BROWSER_HEADERS),
    ("RBI main site", "https://www.rbi.org.in/", BROWSER_HEADERS),
    ("NSE India", "https://www.nseindia.com/", BROWSER_HEADERS),
]

PASS, FAIL, INFO = "  [PASS]", "  [FAIL]", "  [ ?? ]"


def section(title: str) -> None:
    print(f"\n{title}\n{'-' * len(title)}")


def check_r2(settings: Settings) -> bool:
    section("1. Cloudflare R2")
    store = BronzeStore(settings)
    ok, detail = store.check_access()
    print(f"{PASS if ok else FAIL} credentials / bucket: {detail}")
    if not ok:
        return False

    try:
        record = store.put_bytes(
            source_id="S-000",
            filename="preflight.txt",
            payload=b"preflight write check",
            source_url="internal://preflight",
            content_type="text/plain",
            notes="written by scripts/preflight.py",
        )
        print(f"{PASS} write:  {record.key}")
        echoed = store.get_bytes(record.key)
        print(f"{PASS} read:   {len(echoed)} bytes, sha256 {record.sha256[:12]}…")
        return True
    except Exception as exc:
        print(f"{FAIL} write/read: {type(exc).__name__}: {exc}")
        return False


def check_motherduck(settings: Settings) -> bool:
    section("2. MotherDuck")
    ok, detail = catalog.check_access(settings)
    print(f"{PASS if ok else FAIL} credentials: {detail}")
    if not ok:
        return False

    try:
        with catalog.connect(settings) as con:
            catalog.ensure_schemas(con)
            rows = con.execute(
                "SELECT schema_name FROM information_schema.schemata "
                "WHERE schema_name IN ('catalog','silver','gold') ORDER BY 1"
            ).fetchall()
            print(f"{PASS} schemas: {', '.join(r[0] for r in rows)}")
            tables = con.execute(
                "SELECT table_schema || '.' || table_name FROM information_schema.tables "
                "WHERE table_schema = 'catalog' ORDER BY 1"
            ).fetchall()
            print(f"{PASS} catalog tables: {', '.join(t[0] for t in tables) or 'none'}")
        return True
    except Exception as exc:
        print(f"{FAIL} schema setup: {type(exc).__name__}: {exc}")
        return False


def probe(targets, timeout: float = 60.0) -> None:
    """Time each target and report status, so slowness is distinguishable from blocking."""
    for label, url, headers in targets:
        started = time.monotonic()
        try:
            with httpx.Client(follow_redirects=True, timeout=timeout) as client:
                # Range-limit so we never pull a large file during preflight.
                resp = client.get(url, headers={**headers, "Range": "bytes=0-2047"})
            elapsed = time.monotonic() - started
            body = resp.text[:200].replace("\n", " ") if resp.content else ""
            verdict = PASS if resp.status_code in (200, 206) else INFO
            print(f"{verdict} {label}  [{elapsed:.1f}s]")
            print(f"         HTTP {resp.status_code} · {resp.headers.get('content-type', '?')}")
            if body:
                print(f"         {body[:110]}…")
        except Exception as exc:
            elapsed = time.monotonic() - started
            print(f"{INFO} {label}  [{elapsed:.1f}s]")
            print(f"         {type(exc).__name__}: {exc}")


def check_sba() -> None:
    section("3. data.sba.gov reachability (informational)")
    print("  Dev sandbox saw HTTP 404 on all routes. Testing from this runner:\n")
    probe(SBA_TARGETS)


def check_india() -> None:
    section("4. Indian government hosts (informational)")
    print("  S-079 hit ConnectTimeout on ibbi.gov.in from a US-east runner,")
    print("  while the same host downloads normally from the dev machine.\n")
    probe(INDIA_TARGETS, timeout=90.0)


def main() -> int:
    print("=" * 68)
    print("CREDIT DATA PLATFORM — PREFLIGHT")
    print("=" * 68)

    try:
        settings = Settings.from_env()
    except Exception as exc:
        print(f"\n{FAIL} {exc}")
        return 1

    print(f"\n  R2 endpoint: {settings.r2_endpoint}")
    print(f"  Bucket:      {settings.bronze_bucket}")
    print(f"  Database:    {settings.md_database}")

    r2_ok = check_r2(settings)
    md_ok = check_motherduck(settings)
    check_sba()
    check_india()

    section("Summary")
    print(f"  Cloudflare R2 : {'OK' if r2_ok else 'FAILED'}")
    print(f"  MotherDuck    : {'OK' if md_ok else 'FAILED'}")
    print("  SBA route     : see section 3 — determines connector design")
    print("  India hosts   : see section 4 — determines S-079 execution location")

    if r2_ok and md_ok:
        print("\n  Platform foundations are working.\n")
        return 0
    print("\n  Fix the failures above before building pipelines.\n")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
