"""Export a complete picture of the warehouse to CSV.

Produces an inventory of what has been fetched, the full audit trail, the
complete gold tables, and representative samples of the silver panel — enough
to inspect the platform's state without a database client.

Written to ./exports/, collected as a workflow artifact.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.common import catalog  # noqa: E402
from src.common.settings import Settings  # noqa: E402
from src.common.storage import BronzeStore  # noqa: E402

OUT = Path("exports")
SAMPLE_ROWS = 5_000


def write(df: pd.DataFrame, name: str, description: str, manifest: list) -> None:
    path = OUT / name
    df.to_csv(path, index=False)
    size_kb = path.stat().st_size / 1024
    manifest.append({
        "file": name,
        "rows": len(df),
        "columns": len(df.columns),
        "size_kb": round(size_kb, 1),
        "description": description,
    })
    print(f"  {name:<44} {len(df):>8,} rows  {size_kb:>9,.0f} KB")


def main() -> int:
    OUT.mkdir(exist_ok=True)
    settings = Settings.from_env()
    manifest: list[dict] = []

    print("Exporting warehouse contents\n" + "-" * 68)

    with catalog.connect(settings) as con:
        # ── 1. Inventory: every table, its size and coverage ──────────
        tables = con.execute(
            """
            SELECT table_schema AS schema_name, table_name
            FROM information_schema.tables
            WHERE table_schema IN ('catalog','silver','gold')
            ORDER BY table_schema, table_name
            """
        ).fetchall()

        rows = []
        for schema, table in tables:
            fq = f"{schema}.{table}"
            n = con.execute(f"SELECT count(*) FROM {fq}").fetchone()[0]
            cols = con.execute(
                "SELECT count(*) FROM information_schema.columns "
                "WHERE table_schema = ? AND table_name = ?", [schema, table]
            ).fetchone()[0]
            period_min = period_max = None
            colnames = [
                c[0] for c in con.execute(
                    "SELECT column_name FROM information_schema.columns "
                    "WHERE table_schema = ? AND table_name = ?", [schema, table]
                ).fetchall()
            ]
            for candidate in ("report_date", "REPDTE", "checked_at", "started_at", "registered_at"):
                if candidate in colnames:
                    period_min, period_max = con.execute(
                        f'SELECT min("{candidate}"), max("{candidate}") FROM {fq}'
                    ).fetchone()
                    break
            rows.append({
                "layer": schema, "table": fq, "rows": n, "columns": cols,
                "coverage_from": str(period_min) if period_min is not None else "",
                "coverage_to": str(period_max) if period_max is not None else "",
            })
        write(pd.DataFrame(rows), "01_warehouse_inventory.csv",
              "Every table in the warehouse with row counts and coverage range", manifest)

        # ── 2. Source registry ────────────────────────────────────────
        write(con.execute("SELECT * FROM catalog.source_registry").fetch_df(),
              "02_source_registry.csv",
              "Sources registered on the platform and their metadata", manifest)

        # ── 3. Load log — the full audit trail ────────────────────────
        write(con.execute(
                "SELECT * FROM catalog.load_log ORDER BY started_at"
              ).fetch_df(),
              "03_load_log.csv",
              "Every fetch: when, from where, rows in, target table, outcome", manifest)

        # ── 4. QA results ─────────────────────────────────────────────
        write(con.execute(
                "SELECT * FROM catalog.qa_results ORDER BY checked_at, check_name"
              ).fetch_df(),
              "04_qa_results.csv",
              "Every quality check run, with observed vs expected values", manifest)

        # ── 5+6. Gold tables, complete ────────────────────────────────
        write(con.execute(
                "SELECT * FROM gold.us_bank_credit_quarterly ORDER BY report_date"
              ).fetch_df(),
              "05_gold_us_bank_credit_quarterly.csv",
              "COMPLETE: US bank credit performance by quarter, 1992-2026 "
              "(loan-weighted, non-lenders excluded)", manifest)

        write(con.execute(
                "SELECT * FROM gold.us_bank_credit_by_size ORDER BY report_date, size_class"
              ).fetch_df(),
              "06_gold_us_bank_credit_by_size.csv",
              "COMPLETE: the same series split by institution size class", manifest)

        # ── 7. Silver: full history for the largest institutions ──────
        # Recognisable names make the panel easy to sanity-check by eye.
        major = con.execute(
            """
            WITH biggest AS (
                SELECT CERT
                FROM silver.fdic_bank_financials
                WHERE REPDTE = (SELECT max(REPDTE) FROM silver.fdic_bank_financials)
                ORDER BY ASSET DESC NULLS LAST
                LIMIT 15
            )
            SELECT * FROM silver.fdic_bank_financials
            WHERE CERT IN (SELECT CERT FROM biggest)
            ORDER BY CERT, REPDTE
            """
        ).fetch_df()
        write(major, "07_silver_sample_major_banks.csv",
              "SAMPLE: complete quarterly history for the 15 largest US banks "
              "(all 63 columns) — the panel structure end to end", manifest)

        # ── 8. Silver: random cross-section ───────────────────────────
        rand = con.execute(
            f"""
            SELECT * FROM silver.fdic_bank_financials
            USING SAMPLE {SAMPLE_ROWS} ROWS
            """
        ).fetch_df()
        write(rand, "08_silver_sample_random.csv",
              f"SAMPLE: {SAMPLE_ROWS:,} random rows across all banks and quarters "
              "— representative of the full 1.09m-row panel", manifest)

        # ── 8b. IBBI case-level insolvency outcomes (the flagship set) ─
        if con.execute(
            "SELECT count(*) FROM information_schema.tables "
            "WHERE table_schema='silver' AND table_name='ibbi_cirp_cases'"
        ).fetchone()[0]:
            ibbi = con.execute(
                "SELECT * FROM silver.ibbi_cirp_cases "
                "ORDER BY source_year, source_quarter, sl_no"
            ).fetch_df()
            write(ibbi, "11_ibbi_cirp_cases_FULL.csv",
                  "COMPLETE: case-level Indian insolvency outcomes — every corporate debtor "
                  "with admitted claims, liquidation/fair value, realised amount and dates. "
                  "India's only public workout-LGD micro dataset.", manifest)

            validated = con.execute(
                "SELECT * FROM silver.ibbi_cirp_cases WHERE arithmetic_ok "
                "ORDER BY admitted_claims_cr DESC NULLS LAST"
            ).fetch_df()
            write(validated, "12_ibbi_cirp_validated_only.csv",
                  "MODELLING SET: only rows that reconcile against their own printed "
                  "percentages — use this one for LGD work", manifest)

            quarantine = con.execute(
                "SELECT source_period, corporate_debtor, extraction_method, arithmetic_detail, "
                "admitted_claims_cr, realisable_amount_cr, pct_of_claims, raw_row "
                "FROM silver.ibbi_cirp_cases WHERE arithmetic_ok = FALSE"
            ).fetch_df()
            write(quarantine, "13_ibbi_quarantined_rows.csv",
                  "Rows that failed the arithmetic self-check, with the reason — "
                  "excluded from modelling, retained for inspection", manifest)

        # ── 8c. India corporate LGD gold panel ────────────────────────
        if con.execute(
            "SELECT count(*) FROM information_schema.tables "
            "WHERE table_schema='gold' AND table_name='india_corporate_lgd_panel'"
        ).fetchone()[0]:
            write(con.execute(
                    "SELECT * FROM gold.india_corporate_lgd_panel ORDER BY admitted_claims_cr DESC"
                  ).fetch_df(),
                  "14_gold_india_corporate_lgd_panel.csv",
                  "COMPLETE: modelling-ready India corporate LGD panel — recovery rate, LGD, "
                  "workout duration, going-concern premium, size band and vintage per case",
                  manifest)
            write(con.execute(
                    "SELECT * FROM gold.india_corporate_lgd_summary ORDER BY dimension, segment"
                  ).fetch_df(),
                  "15_gold_india_lgd_summary.csv",
                  "COMPLETE: recovery and LGD curves by size band, initiator, year and "
                  "claims basis — weighted and median side by side", manifest)

        # ── 9. Column dictionary for the silver panel ─────────────────
        cols = con.execute(
            """
            SELECT column_name, data_type
            FROM information_schema.columns
            WHERE table_schema='silver' AND table_name='fdic_bank_financials'
            ORDER BY ordinal_position
            """
        ).fetch_df()
        meanings = {
            "CERT": "FDIC certificate number — the bank's unique id",
            "REPDTE": "Report date (YYYYMMDD), quarter end",
            "NAME": "Institution name", "CITY": "City", "STALP": "State code",
            "STNAME": "State name", "BKCLASS": "Charter/regulator class",
            "SPECGRPDESC": "Specialisation group", "ACTIVE": "1 = currently operating",
            "CB": "1 = community bank",
            "ASSET": "Total assets ($000s)", "DEP": "Total deposits ($000s)",
            "EQTOT": "Total equity capital ($000s)",
            "LNLSNET": "Net loans and leases ($000s) — the denominator for rate fields",
            "LNATRESR": "Allowance for loan losses / loans (%)",
            "ELNATR": "Provision for credit losses ($000s)",
            "NTLNLS": "Net charge-offs ($000s)",
            "NTLNLSR": "Net charge-off rate (%) — negative means net recoveries",
            "NAASSET": "Nonaccrual assets ($000s)", "NALTOT": "Total nonaccrual loans ($000s)",
            "P3ASSET": "Assets 30-89 days past due ($000s)",
            "P9ASSET": "Assets 90+ days past due ($000s)",
            "NCLNLSR": "Noncurrent loans / loans (%)",
            "NPERFV": "Nonperforming assets ratio (%)",
            "ORE": "Other real estate owned ($000s)",
            "NTRER": "Net charge-off rate, all real estate (%)",
            "NTRERESR": "Net charge-off rate, 1-4 family residential (%)",
            "NTREMULR": "Net charge-off rate, multifamily (%)",
            "NTRENRSR": "Net charge-off rate, non-residential CRE (%)",
            "NTRECOSR": "Net charge-off rate, construction & development (%)",
            "NTCOMRER": "Net charge-off rate, commercial real estate (%)",
            "IDNTCIR": "Net charge-off rate, commercial & industrial (%)",
            "IDNTCONR": "Net charge-off rate, consumer loans (%)",
            "NTALLOTHR": "Net charge-off rate, all other loans (%)",
            "NCRER": "Noncurrent rate, all real estate (%)",
            "NCRERESR": "Noncurrent rate, 1-4 family residential (%)",
            "NCREMULR": "Noncurrent rate, multifamily (%)",
            "NCRENRER": "Noncurrent rate, non-residential CRE (%)",
            "NCRECONR": "Noncurrent rate, construction & development (%)",
            "NCCOMRER": "Noncurrent rate, commercial real estate (%)",
            "IDNCCIR": "Noncurrent rate, commercial & industrial (%)",
            "IDNCCONR": "Noncurrent rate, consumer (%)",
            "IDNCOTHR": "Noncurrent rate, other loans (%)",
            "SZLNRES": "Residential loans ($000s)", "SZLNCI": "C&I loans ($000s)",
            "SZLNCON": "Consumer loans ($000s)", "SZLNCRCD": "Credit card loans ($000s)",
            "SZLAUTO": "Auto loans ($000s)", "SZLNHEL": "Home equity loans ($000s)",
            "SZLNOTH": "Other loans ($000s)",
            "RBC1AAJ": "Tier 1 leverage ratio (%)", "RBCRWAJ": "Total risk-based capital ratio (%)",
            "IDT1RWAJR": "Tier 1 risk-based capital ratio (%)", "IDT1CER": "CET1 ratio (%)",
            "ROA": "Return on assets (%)", "ROE": "Return on equity (%)",
            "NIMY": "Net interest margin (%)",
            "report_date": "REPDTE parsed to a date", "report_year": "Calendar year",
            "report_quarter": "Calendar quarter",
            "_source_id": "Provenance: source registry id",
            "_fetched_at": "Provenance: when this row was fetched",
            "_source_url": "Provenance: exact API URL it came from",
        }
        cols["meaning"] = cols["column_name"].map(meanings).fillna("")
        cols["units"] = cols["column_name"].apply(
            lambda c: "percent" if c.endswith("R") or c in ("ROA", "ROE", "NIMY", "NPERFV")
            else ("$ thousands" if c.startswith(("ASSET", "DEP", "EQ", "LNLS", "SZL", "NT", "NA", "P3", "P9", "ORE", "ELNATR")) and not c.endswith("R")
                  else "")
        )
        write(cols, "09_silver_column_dictionary.csv",
              "What every column in the silver panel means, and its units", manifest)

    # ── 10. Bronze inventory from R2 ──────────────────────────────────
    store = BronzeStore(settings)
    bronze_rows = [
        {"object_key": key, "source_id": key.split("/")[1] if "/" in key else ""}
        for key in store.list_keys("bronze/")
    ]
    write(pd.DataFrame(bronze_rows), "10_bronze_inventory.csv",
          "Every raw file held in object storage (immutable originals)", manifest)

    # ── Manifest ──────────────────────────────────────────────────────
    write(pd.DataFrame(manifest), "00_MANIFEST.csv",
          "Index of these export files", manifest[:0] or [])

    print("-" * 68)
    print(f"Wrote {len(list(OUT.glob('*.csv')))} files to {OUT.resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
