"""Run a read-only SQL query against MotherDuck and print the result.

Driven by the "Query warehouse" workflow. Read-only by construction: anything
that is not a SELECT or WITH is refused, so an ad-hoc query cannot mutate a
loaded dataset.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import duckdb
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

FORBIDDEN = (
    "insert", "update", "delete", "drop", "create", "alter",
    "truncate", "attach", "copy", "replace", "grant", "revoke",
)


def main() -> int:
    sql = os.environ.get("QUERY_SQL", "").strip().rstrip(";")
    if not sql:
        print("No SQL provided.")
        return 1

    lowered = sql.lower()
    if not (lowered.startswith("select") or lowered.startswith("with")):
        print("Refused: only SELECT / WITH queries are allowed.")
        return 1
    for word in FORBIDDEN:
        # Word-boundary check so column names like "created_at" are not rejected.
        if f" {word} " in f" {lowered} " or lowered.startswith(f"{word} "):
            print(f"Refused: statement contains '{word}'.")
            return 1

    limit = int(os.environ.get("QUERY_LIMIT", "60") or 60)
    token = os.environ.get("MOTHERDUCK_TOKEN", "")
    if not token:
        print("MOTHERDUCK_TOKEN is not set.")
        return 1

    con = duckdb.connect(f"md:?motherduck_token={token}")
    try:
        con.execute("USE credit_data")
        df = con.execute(sql).fetch_df()
    finally:
        con.close()

    pd.set_option("display.max_columns", 50)
    pd.set_option("display.width", 200)
    pd.set_option("display.max_colwidth", 40)

    print(f"\n{len(df):,} row(s) x {len(df.columns)} column(s)\n")
    print(df.head(limit).to_string(index=False))
    if len(df) > limit:
        print(f"\n… {len(df) - limit:,} more row(s) not shown")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
