"""Build gold-layer tables from loaded silver data.

Run after silver loads. Idempotent: gold tables are rebuilt in full each time,
so they always reflect the current state of silver.

    python pipelines/build_gold.py
"""

from __future__ import annotations

import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.common import catalog  # noqa: E402
from src.common.settings import Settings  # noqa: E402
from src.transforms import (  # noqa: E402
    gold_consumer_credit, gold_india_corporate_lgd, gold_india_retail_pd,
    gold_us_bank_credit,
)

BUILDERS = {
    "us_bank_credit": gold_us_bank_credit,
    "india_corporate_lgd": gold_india_corporate_lgd,
    "consumer_credit": gold_consumer_credit,
    "india_retail_pd": gold_india_retail_pd,
}


def main() -> int:
    settings = Settings.from_env()
    run_id = uuid.uuid4().hex[:12]

    print("=" * 68)
    print(f"GOLD BUILD   run {run_id}")
    print("=" * 68)

    failed_any = False
    with catalog.connect(settings) as con:
        catalog.ensure_schemas(con)

        for name, module in BUILDERS.items():
            started = datetime.now(timezone.utc)
            print(f"\n── {name} " + "─" * (52 - len(name)))
            try:
                counts = module.build(con)
                for table, rows in counts.items():
                    print(f"   built     {table:<40} {rows:>8,} rows")

                print("   checks:")
                results = module.check(con)
                for check_name, passed, detail in results:
                    print(f"     [{'PASS' if passed else 'FAIL'}] {check_name}: {detail}")
                    catalog.record_qa(
                        con, run_id=run_id, source_id="GOLD", check_name=f"{name}.{check_name}",
                        observed=1.0 if passed else 0.0, expected=1.0, tolerance=None,
                        passed=passed, detail=detail,
                    )

                gold_failed = [r for r in results if not r[1]]
                failed_any = failed_any or bool(gold_failed)

                catalog.log_run(
                    con, run_id=run_id, source_id="GOLD", started_at=started,
                    status="failed" if gold_failed else "success",
                    rows_loaded=sum(counts.values()),
                    target_table=", ".join(counts),
                    message=f"{len(results)} checks, {len(gold_failed)} failed",
                )
            except Exception as exc:
                failed_any = True
                print(f"   ✗ FAILED  {type(exc).__name__}: {exc}")
                catalog.log_run(
                    con, run_id=run_id, source_id="GOLD", started_at=started,
                    status="failed", message=f"{type(exc).__name__}: {exc}",
                )

    print("\n" + "=" * 68)
    print("Gold build failed — see checks above.\n" if failed_any else "Gold build complete.\n")
    return 1 if failed_any else 0


if __name__ == "__main__":
    raise SystemExit(main())
