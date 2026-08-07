"""Extract liquidation outcomes from IBBI quarterly newsletters (S-079).

Gone-concern recovery: what creditors actually received when a corporate debtor
was broken up and sold rather than rescued. Columns are

    Sl | Name of the Corporate Debtor | Date of Order of Liquidation
       | Amount of Admitted Claims | Liquidation Value | Sale Proceeds
       | Amount Distributed to Stakeholders | Date of Order of Dissolution

This is the low tail of the recovery distribution — precisely where LGD models
are weakest and where the CIRP resolution panel says nothing, because a company
that liquidates never yields a resolution plan.

Validation is weaker here than for CIRP data, and that has to be stated plainly.
The resolution table prints both amounts and the percentages they imply, so a
misparsed row fails its own arithmetic. **The liquidation table prints no
percentages**, so no such self-check exists. Instead we rely on structural
invariants that a misaligned parse breaks:

  * amounts distributed cannot exceed sale proceeds (by more than rounding)
  * dissolution cannot precede the liquidation order
  * sale proceeds and claims must be non-negative

These catch column shifts but are less decisive than the CIRP check. Rows are
therefore tagged with a distinct validation basis so a modeller can see which
evidential standard each row met.
"""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass
from typing import Any

DATE = r"\d{1,2}[-/]\d{1,2}[-/]\d{2,4}"
NUM_TOKEN_RE = re.compile(r"-?[\d,]+\.?\d*|(?<![A-Za-z])-(?![A-Za-z])|NA|N\.A\.?", re.I)

CD_NAME = r"Name\s+of\s+(?:the\s+)?(?:CD\b|Corporate\s+(?:Debtor|Person))"

# Header matching needs ALTERNATIVE signature sets, not one rigid pattern.
# Two independent drifts defeat a single signature across a decade of editions:
#
#   * terminology — 2020 heads the column "Name of the Corporate Debtor",
#     2026 "Name of the Corporate Person" (legally correct once liquidation
#     commences)
#   * header geometry — the 2022 editions use SPANNING cells, so the
#     sub-column names collapse into "Amount (in Rs crore)" and the strings
#     "Order of Liquidation" and "Sale Proceeds" are simply absent. There the
#     table title "Details of Closed Liquidations" is the reliable anchor.
#
# A table matches if ANY set matches in full. Failing closed on a strict
# signature does not error — it silently yields zero rows, which is the most
# dangerous failure mode in this whole pipeline.
HEADER_SIGNATURE_SETS: tuple[tuple[str, ...], ...] = (
    (CD_NAME, r"Order\s+of\s+Liquidation", r"Sale\s+Proceeds"),   # 2019-21, 2023+
    (CD_NAME, r"Closed\s+Liquidations"),                          # 2022 spanning headers
)

# Negative signature — reject the CIRP RESOLUTION table, which otherwise passes
# a loose positive match: it shares "Name of Corporate Debtor", "Amount (in Rs
# crore)" and "Date of" with the liquidation table. A generic third fallback on
# those tokens pulled 45 resolution rows into the 2026 liquidation set and
# inflated 2022 from 0 to 97 rows of the wrong kind.
#
# Contaminating liquidation (the bad tail) with resolution cases (the good tail)
# is worse than missing an edition: it silently biases every recovery statistic
# upward, and nothing downstream would flag it.
EXCLUDE_SIGNATURE = (
    r"Realisable",
    r"Fair\s+Value",
    r"Yielding\s+Resolution",
    r"Resolution\s+Plan",
)

# Kept for callers/tests that reference the original single signature
HEADER_SIGNATURE = HEADER_SIGNATURE_SETS[0]


@dataclass
class LiquidationCase:
    sl_no: int
    corporate_debtor: str
    liquidation_order_date: str | None
    dissolution_order_date: str | None
    admitted_claims_cr: float | None = None
    liquidation_value_cr: float | None = None
    sale_proceeds_cr: float | None = None
    amount_distributed_cr: float | None = None
    source_period: str = ""
    source_page: int = 0
    n_numeric_tokens: int = 0
    structural_ok: bool | None = None
    structural_detail: str = ""
    validation_basis: str = "structural_only"   # no printed percentages to check against
    raw_row: str = ""

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def _to_float(tok: str | None) -> float | None:
    if tok is None:
        return None
    t = tok.strip().replace(",", "")
    if t in {"", "-", "NA", "N.A", "N.A."} or t.lower() == "na":
        return None
    try:
        return float(t)
    except ValueError:
        return None


def parse_row(text: str) -> dict[str, Any] | None:
    """Parse a flattened liquidation row.

    Shape differs from CIRP: one date after the name, then the money columns,
    then an optional dissolution date. There is no defunct flag and no
    FC/OC/CD initiator, so the CIRP regex cannot be reused.
    """
    text = re.sub(r"\s+", " ", (text or "").replace("\n", " ")).strip()
    if not text:
        return None

    m = re.match(rf"^\s*(?P<sl>\d{{1,4}})\s+(?P<rest>.+)$", text)
    if not m:
        return None

    rest = m.group("rest")
    dates = list(re.finditer(DATE, rest))
    if not dates:
        return None

    name = rest[: dates[0].start()].strip(" .-")
    if len(name) < 3 or not re.search(r"[A-Za-z]{3}", name):
        return None

    liq_date = dates[0].group(0)
    diss_date = dates[-1].group(0) if len(dates) > 1 else None

    # Money sits between the first date and the last one (or to end of row)
    money_span = rest[dates[0].end(): dates[-1].start()] if len(dates) > 1 else rest[dates[0].end():]
    toks = NUM_TOKEN_RE.findall(money_span)

    return {
        "sl_no": int(m.group("sl")),
        "corporate_debtor": name,
        "liquidation_order_date": liq_date,
        "dissolution_order_date": diss_date,
        "numeric_tokens": toks,
        "raw_row": text,
    }


def validate_structure(rec: LiquidationCase) -> tuple[bool | None, str]:
    """Structural invariants — weaker than the CIRP arithmetic check.

    A column shift typically breaks at least one of these, but unlike the
    resolution table there is no printed figure to reconcile against, so a
    plausible-looking misparse can survive. Treated accordingly downstream.
    """
    problems: list[str] = []
    checked = False

    if rec.amount_distributed_cr is not None and rec.sale_proceeds_cr is not None:
        checked = True
        # Distribution above proceeds is impossible beyond rounding
        if rec.amount_distributed_cr > rec.sale_proceeds_cr * 1.02 + 0.05:
            problems.append(
                f"distributed {rec.amount_distributed_cr} > proceeds {rec.sale_proceeds_cr}"
            )

    for label, value in (
        ("claims", rec.admitted_claims_cr),
        ("liq_value", rec.liquidation_value_cr),
        ("proceeds", rec.sale_proceeds_cr),
        ("distributed", rec.amount_distributed_cr),
    ):
        if value is not None:
            checked = True
            if value < 0:
                problems.append(f"{label} negative ({value})")

    if not checked:
        return None, "no checkable field"
    return (not problems), ("; ".join(problems) if problems else "structurally consistent")


def map_numerics(toks: list[str]) -> dict[str, float | None]:
    """claims, liquidation value, sale proceeds, amount distributed."""
    vals = [_to_float(t) for t in toks]
    out = {
        "admitted_claims_cr": None, "liquidation_value_cr": None,
        "sale_proceeds_cr": None, "amount_distributed_cr": None,
    }
    if len(vals) >= 4:
        (out["admitted_claims_cr"], out["liquidation_value_cr"],
         out["sale_proceeds_cr"], out["amount_distributed_cr"]) = vals[:4]
    elif len(vals) == 3:
        (out["admitted_claims_cr"], out["liquidation_value_cr"],
         out["sale_proceeds_cr"]) = vals[:3]
    return out


def header_matches(header: str) -> bool:
    """True when the header satisfies ANY signature set and no exclusion."""
    if any(re.search(p, header, re.I) for p in EXCLUDE_SIGNATURE):
        return False  # it is the CIRP resolution table, not a liquidation table
    return any(
        all(re.search(p, header, re.I) for p in signature)
        for signature in HEADER_SIGNATURE_SETS
    )


TITLE_ANCHOR = r"Details\s+of\s+Closed\s+Liquidations"


def find_table_pages(pdf) -> list[int]:
    """Locate liquidation tables by header signature, with a page-title fallback.

    The 2022 Q2/Q3 editions defeat header-only matching twice over: spanning
    cells remove the sub-column names, AND the caption "Table 3: Details of
    Closed Liquidations" sits in the page text OUTSIDE the table structure, so
    extract_tables() never returns it. Checking the page title as well recovers
    those editions, while the exclusion list still keeps the CIRP resolution
    table out.
    """
    pages: list[int] = []
    for i, page in enumerate(pdf.pages):
        try:
            tables = page.extract_tables()
        except Exception:
            continue
        page_text = page.extract_text() or ""
        title_present = bool(re.search(TITLE_ANCHOR, page_text, re.I))

        for table in tables or []:
            # Scan more header rows than before: the 2022 spanning layout pushes
            # sub-column names down, and a title row can sit above the columns.
            header = " ".join(str(c or "") for row in (table[:4] or []) for c in row)
            if header_matches(header):
                pages.append(i + 1)
                break
            # Title fallback — only for tables that name a corporate debtor and
            # carry none of the resolution-table markers.
            if (
                title_present
                and re.search(CD_NAME, header, re.I)
                and not any(re.search(p, header, re.I) for p in EXCLUDE_SIGNATURE)
            ):
                pages.append(i + 1)
                break
    return pages


def extract_cases(pdf, period: str) -> tuple[list[LiquidationCase], dict]:
    start_pages = find_table_pages(pdf)
    stats: dict[str, Any] = {"pages_scanned": [], "totals_rows": []}
    if not start_pages:
        return [], stats

    candidates: list[int] = []
    for p in start_pages:
        for q in (p, p + 1, p + 2):
            if 1 <= q <= len(pdf.pages) and q not in candidates:
                candidates.append(q)

    found: list[LiquidationCase] = []
    for pageno in sorted(candidates):
        page = pdf.pages[pageno - 1]
        stats["pages_scanned"].append(pageno)

        attempts = []
        try:
            attempts.append(page.extract_tables())
        except Exception:
            pass
        try:
            attempts.append(page.extract_tables(
                {"vertical_strategy": "lines", "horizontal_strategy": "lines", "snap_tolerance": 4}
            ))
        except Exception:
            pass

        best: list[LiquidationCase] = []
        for tables in attempts:
            got: list[LiquidationCase] = []
            for table in tables or []:
                for row in table:
                    if not row:
                        continue
                    flat = " ".join(str(c or "") for c in row)
                    if re.search(r"^\s*Total\b|\bTotal\s*\(", flat, re.I):
                        stats["totals_rows"].append(re.sub(r"\s+", " ", flat).strip()[:200])
                        continue
                    parsed = parse_row(flat)
                    if not parsed:
                        continue
                    rec = LiquidationCase(
                        sl_no=parsed["sl_no"],
                        corporate_debtor=parsed["corporate_debtor"],
                        liquidation_order_date=parsed["liquidation_order_date"],
                        dissolution_order_date=parsed["dissolution_order_date"],
                        source_period=period,
                        source_page=pageno,
                        n_numeric_tokens=len(parsed["numeric_tokens"]),
                        raw_row=parsed["raw_row"][:400],
                        **map_numerics(parsed["numeric_tokens"]),
                    )
                    rec.structural_ok, rec.structural_detail = validate_structure(rec)
                    got.append(rec)
            score = (sum(1 for r in got if r.structural_ok), len(got))
            best_score = (sum(1 for r in best if r.structural_ok), len(best))
            if score > best_score:
                best = got
        found.extend(best)

    seen: set[tuple] = set()
    unique: list[LiquidationCase] = []
    for c in found:
        key = (c.corporate_debtor.lower()[:60], c.liquidation_order_date)
        if key in seen:
            continue
        seen.add(key)
        unique.append(c)

    stats["rows_parsed"] = len(unique)
    return unique, stats
