"""Probe Kaggle access before committing to multi-gigabyte downloads.

Reports, per target, whether the credentials can reach it — and when they
cannot, why. The common cause is a competition whose rules have not been
accepted in a browser, which the API reports only as a bare 403.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.connectors.kaggle_api import TARGETS, probe  # noqa: E402


def main() -> int:
    username = os.environ.get("KAGGLE_USERNAME", "")
    key = os.environ.get("KAGGLE_KEY", "")

    print("=" * 74)
    print("KAGGLE ACCESS PROBE")
    print("=" * 74)
    if not username or not key:
        print("\n  [FAIL] KAGGLE_USERNAME / KAGGLE_KEY not set in the environment.")
        return 1
    print(f"\n  authenticating as: {username}\n")

    results = [probe(t, username=username, key=key) for t in TARGETS]

    for r in results:
        mark = "[ OK ]" if r.accessible else "[FAIL]"
        size = f"{r.size_bytes/1_048_576:.0f} MB" if r.size_bytes else "size unknown"
        print(f"  {mark} {r.target.key:<24} {r.target.kind:<12} HTTP {r.status_code}  {size}")
        print(f"         {r.target.note}")
        if not r.accessible:
            print(f"         → {r.reason}")
        print()

    ok = [r for r in results if r.accessible]
    blocked = [r for r in results if not r.accessible]

    print("-" * 74)
    print(f"  accessible: {len(ok)}/{len(results)}")
    if blocked:
        print("\n  Blocked targets need action before the pipeline can fetch them:")
        for r in blocked:
            if r.target.kind == "competition":
                print(f"    · https://www.kaggle.com/competitions/{r.target.ref}/rules")
            else:
                print(f"    · https://www.kaggle.com/datasets/{r.target.ref}")
        print("\n  Accepting rules takes a click each; re-run this probe afterwards.")
    else:
        print("\n  All targets reachable — safe to run the full pipeline.\n")

    # Blocked targets are informational, not a build failure: the point of the
    # probe is to report clearly, and partial access is still worth proceeding
    # with. The pipeline itself skips what it cannot reach.
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
