"""MotherDuck connection and the catalog tables.

The catalog is what makes the platform auditable: which source produced which
table, when it was fetched, how many rows survived parsing, and whether it
reconciled against a published control total (ADR-006).
"""

from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Any, Iterator

import duckdb

from .settings import Settings

SCHEMAS = ("catalog", "silver", "gold")

DDL = {
    "catalog.load_log": """
        CREATE TABLE IF NOT EXISTS catalog.load_log (
            run_id            VARCHAR,
            source_id         VARCHAR,
            started_at        TIMESTAMP,
            finished_at       TIMESTAMP,
            status            VARCHAR,      -- running | success | failed
            bronze_key        VARCHAR,
            source_url        VARCHAR,
            rows_fetched      BIGINT,
            rows_loaded       BIGINT,
            rows_rejected     BIGINT,
            target_table      VARCHAR,
            message           VARCHAR
        )
    """,
    "catalog.qa_results": """
        CREATE TABLE IF NOT EXISTS catalog.qa_results (
            run_id            VARCHAR,
            source_id         VARCHAR,
            checked_at        TIMESTAMP,
            check_name        VARCHAR,
            observed          DOUBLE,
            expected          DOUBLE,
            tolerance         DOUBLE,
            passed            BOOLEAN,
            detail            VARCHAR
        )
    """,
    "catalog.source_registry": """
        CREATE TABLE IF NOT EXISTS catalog.source_registry (
            source_id         VARCHAR,
            name              VARCHAR,
            publisher         VARCHAR,
            tier              INTEGER,
            archetype         VARCHAR,
            geography         VARCHAR,
            portfolios        VARCHAR,
            parameters        VARCHAR,
            schedule          VARCHAR,
            landing_page      VARCHAR,
            target_silver     VARCHAR,
            registered_at     TIMESTAMP,
            last_success_at   TIMESTAMP
        )
    """,
}


@contextmanager
def connect(settings: Settings) -> Iterator[duckdb.DuckDBPyConnection]:
    """Open a MotherDuck connection with our database selected."""
    con = duckdb.connect(f"md:?motherduck_token={settings.motherduck_token}")
    try:
        con.execute(f"CREATE DATABASE IF NOT EXISTS {settings.md_database}")
        con.execute(f"USE {settings.md_database}")
        yield con
    finally:
        con.close()


def check_access(settings: Settings) -> tuple[bool, str]:
    """Verify the MotherDuck token works. Returns (ok, detail)."""
    try:
        with connect(settings) as con:
            version = con.execute("SELECT version()").fetchone()
            return True, f"connected, DuckDB {version[0] if version else 'unknown'}"
    except Exception as exc:
        detail = str(exc).splitlines()[0] if str(exc) else type(exc).__name__
        hint = ""
        if "token" in detail.lower() or "auth" in detail.lower():
            hint = " — re-copy MOTHERDUCK_TOKEN (it should start 'eyJ')"
        return False, f"{type(exc).__name__}: {detail}{hint}"


def ensure_schemas(con: duckdb.DuckDBPyConnection) -> None:
    for schema in SCHEMAS:
        con.execute(f"CREATE SCHEMA IF NOT EXISTS {schema}")
    for ddl in DDL.values():
        con.execute(ddl)


def log_run(
    con: duckdb.DuckDBPyConnection,
    *,
    run_id: str,
    source_id: str,
    started_at: datetime,
    status: str,
    bronze_key: str = "",
    source_url: str = "",
    rows_fetched: int = 0,
    rows_loaded: int = 0,
    rows_rejected: int = 0,
    target_table: str = "",
    message: str = "",
) -> None:
    con.execute(
        """
        INSERT INTO catalog.load_log
        (run_id, source_id, started_at, finished_at, status, bronze_key, source_url,
         rows_fetched, rows_loaded, rows_rejected, target_table, message)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        [
            run_id, source_id, started_at, datetime.now(timezone.utc), status,
            bronze_key, source_url, rows_fetched, rows_loaded, rows_rejected,
            target_table, message,
        ],
    )


def record_qa(
    con: duckdb.DuckDBPyConnection,
    *,
    run_id: str,
    source_id: str,
    check_name: str,
    observed: float,
    expected: float | None,
    tolerance: float | None,
    passed: bool,
    detail: str = "",
) -> None:
    con.execute(
        """
        INSERT INTO catalog.qa_results
        (run_id, source_id, checked_at, check_name, observed, expected, tolerance, passed, detail)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        [
            run_id, source_id, datetime.now(timezone.utc), check_name,
            observed, expected, tolerance, passed, detail,
        ],
    )


def register_source(con: duckdb.DuckDBPyConnection, cfg: dict[str, Any]) -> None:
    """Upsert a source's metadata from its YAML config into the registry."""
    con.execute("DELETE FROM catalog.source_registry WHERE source_id = ?", [cfg["id"]])
    con.execute(
        """
        INSERT INTO catalog.source_registry
        (source_id, name, publisher, tier, archetype, geography, portfolios,
         parameters, schedule, landing_page, target_silver, registered_at, last_success_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, NULL)
        """,
        [
            cfg["id"], cfg.get("name"), cfg.get("publisher"), cfg.get("tier"),
            cfg.get("archetype"), cfg.get("geography"),
            ",".join(cfg.get("portfolios", []) or []),
            ",".join(cfg.get("parameters", []) or []),
            cfg.get("schedule"), cfg.get("landing_page"),
            (cfg.get("targets") or {}).get("silver"),
            datetime.now(timezone.utc),
        ],
    )
