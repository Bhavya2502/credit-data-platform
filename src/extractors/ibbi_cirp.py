"""Extract case-level insolvency outcomes from IBBI quarterly newsletters (S-079).

Why this is not a normal table parse
------------------------------------
Ten years of newsletters drift in every dimension that a cell-based extractor
depends on:

  * table NUMBERING is unstable — "Table 5" is CIRPs Yielding Resolution Plans in
    2026 but Claim Distribution and Reasons for Withdrawal in 2020
  * column COUNT changes — 11 (2020) → 12 (2022) → 13 (2026)
  * column GEOMETRY breaks — pdfplumber's line detection splits "2292.53" into
    "2292." and "53 27.48" in the 2022 editions, silently corrupting values
  * pre-2019 editions carry case names with no financial columns at all

What stays constant is the ROW TEXT. Every case row reads:

    <sl> <corporate debtor name> [Yes|No|NA] <date> <date> <FC|OC|CD> <numbers…>

So we locate tables by content signature rather than by number, flatten each row
to text, and parse it with a regex anchored on the invariant tokens (dates and
the FC/OC/CD initiator). Column boundaries are never trusted.

Self-validation
---------------
Each row carries both the amounts and the percentages they imply. Recomputing
realisable/admitted × 100 and comparing to the printed percentage is an
arithmetic check the source itself supplies: if a parse is misaligned by one
column, the check fails. That is what makes this trustworthy enough to model on.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field, asdict
from typing import Any

# ── invariant tokens ─────────────────────────────────────────────────
DATE = r"\d{1,2}[-/]\d{1,2}[-/]\d{2,4}"
INITIATOR = r"(?:FC|OC|CD|CoC)"
DEFUNCT = r"(?:Yes|No|NA|N\.A\.?)"

ROW_RE = re.compile(
    rf"^\s*(?P<sl>\d{{1,4}})\s+"
    rf"(?P<rest>.+?)\s+"
    rf"(?P<d1>{DATE})\s+"
    rf"(?P<d2>{DATE})\s+"
    rf"(?P<init>{INITIATOR})\b"
    rf"(?P<nums>.*)$",
    re.I,
)

# Trailing Yes/No/NA before the first date is the "defunct" flag
DEFUNCT_TAIL_RE = re.compile(rf"\s+(?P<defunct>{DEFUNCT})\s*$", re.I)

# Numeric token: 1,234.56 / 1234.56 / -  / NA / 12.34%
NUM_TOKEN_RE = re.compile(r"-?[\d,]+\.?\d*%?|(?<![A-Za-z])-(?![A-Za-z])|NA|N\.A\.?", re.I)

TABLE_SIGNATURES = {
    # what we are looking for -> tokens that must appear on the page
    "cirp_resolution": ("Yielding Resolution Plan", "Admitted"),
    "liquidation": ("Order of Liquidation", "Sale"),
    "voluntary_liquidation": ("Dissolution", "Liquidation Expenses"),
}


@dataclass
class CirpCase:
    """One corporate debtor resolved through a resolution plan."""

    sl_no: int
    corporate_debtor: str
    defunct: str | None
    cirp_commencement_date: str | None
    resolution_approval_date: str | None
    initiated_by: str | None
    admitted_claims_cr: float | None = None
    liquidation_value_cr: float | None = None
    fair_value_cr: float | None = None
    realisable_amount_cr: float | None = None
    pct_of_claims: float | None = None
    pct_of_liquidation_value: float | None = None
    pct_of_fair_value: float | None = None
    # provenance + QA
    source_period: str = ""
    source_page: int = 0
    part: str = ""                       # "A" = prior period, "B" = this quarter
    n_numeric_tokens: int = 0
    arithmetic_ok: bool | None = None
    arithmetic_detail: str = ""
    raw_row: str = ""

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def _to_float(tok: str | None) -> float | None:
    if tok is None:
        return None
    t = tok.strip().replace(",", "").replace("%", "")
    if t in {"", "-", "NA", "N.A", "N.A.", "na"} or t.lower() == "na":
        return None
    try:
        return float(t)
    except ValueError:
        return None


def parse_row(text: str) -> dict[str, Any] | None:
    """Parse one flattened row. Returns None if it is not a case row."""
    text = re.sub(r"\s+", " ", (text or "").replace("\n", " ")).strip()
    if not text:
        return None

    m = ROW_RE.match(text)
    if not m:
        return None

    rest = m.group("rest").strip()
    defunct = None
    dm = DEFUNCT_TAIL_RE.search(rest)
    if dm:
        defunct = dm.group("defunct").upper().replace(".", "")
        defunct = {"N A": "NA", "NA": "NA", "YES": "Yes", "NO": "No"}.get(defunct, defunct)
        rest = rest[: dm.start()].strip()

    name = rest.strip(" .-")
    # A plausible corporate name: has letters and is not just an artefact
    if len(name) < 3 or not re.search(r"[A-Za-z]{3}", name):
        return None

    nums = NUM_TOKEN_RE.findall(m.group("nums") or "")
    return {
        "sl_no": int(m.group("sl")),
        "corporate_debtor": name,
        "defunct": defunct,
        "cirp_commencement_date": m.group("d1"),
        "resolution_approval_date": m.group("d2"),
        "initiated_by": m.group("init").upper(),
        "numeric_tokens": nums,
        "raw_row": text,
    }


def _merge_split_numbers(toks: list[str], expected: int) -> list[list[str]]:
    """Candidate repairs for numbers broken by a stray space.

    Observed in the 2022 editions: "3251.00" is rendered as "3 251.00" and
    "1847.39" as "1 847.39", yielding one token too many. The give-away is a
    bare integer (no decimal point) immediately followed by a value with
    decimals. We do not guess which merge is right — we generate the candidates
    and let the arithmetic check decide (see parse_row_full).
    """
    if len(toks) <= expected:
        return [toks]
    out: list[list[str]] = []
    for i in range(len(toks) - 1):
        a, b = toks[i], toks[i + 1]
        if re.fullmatch(r"\d{1,3}", a.strip()) and re.fullmatch(r"[\d,]+\.\d+%?", b.strip()):
            merged = toks[:i] + [a.strip() + b.strip()] + toks[i + 2:]
            out.append(merged)
    out.append(toks)  # keep the unmerged reading as a fallback
    return out


def map_numerics(parsed: dict[str, Any]) -> dict[str, float | None]:
    """Map the numeric tail onto named fields.

    Layouts observed:
      7 tokens (2022+): claims, liq value, fair value, realisable, %claims, %liq, %fair
      5 tokens (2020):  claims, liq value, realisable, %claims, %liq   (no fair value)
    Anything else is left unmapped rather than guessed — an unmapped row is
    recorded and surfaced, never silently dropped or coerced.
    """
    toks = [_to_float(t) for t in parsed["numeric_tokens"]]
    n = len(toks)
    out: dict[str, float | None] = {
        "admitted_claims_cr": None, "liquidation_value_cr": None,
        "fair_value_cr": None, "realisable_amount_cr": None,
        "pct_of_claims": None, "pct_of_liquidation_value": None,
        "pct_of_fair_value": None,
    }
    if n >= 7:
        (out["admitted_claims_cr"], out["liquidation_value_cr"], out["fair_value_cr"],
         out["realisable_amount_cr"], out["pct_of_claims"],
         out["pct_of_liquidation_value"], out["pct_of_fair_value"]) = toks[:7]
    elif n == 5:
        (out["admitted_claims_cr"], out["liquidation_value_cr"],
         out["realisable_amount_cr"], out["pct_of_claims"],
         out["pct_of_liquidation_value"]) = toks[:5]
    elif n == 6:
        # 2020-era with an extra realisable split; take the conservative mapping
        (out["admitted_claims_cr"], out["liquidation_value_cr"],
         out["realisable_amount_cr"], out["pct_of_claims"],
         out["pct_of_liquidation_value"], out["pct_of_fair_value"]) = toks[:6]
    return out


def validate_arithmetic(rec: CirpCase, tol: float = 2.0) -> tuple[bool | None, str]:
    """Recompute the printed percentages from the printed amounts.

    The source publishes both, so disagreement means our column mapping is
    wrong — the single most valuable check available on this document family.
    Returns (ok, detail); ok is None when there is nothing to check against.

    Tolerance must scale with the denominator. Amounts are printed to two
    decimals in Rs crore, so a case with a liquidation value of 0.01 crore
    (Rs 100,000) carries up to 50% rounding error in the implied percentage
    through no fault of the parse. Below Rs 1 crore we therefore widen the
    band by the rounding error the printed precision actually permits.
    """
    checks: list[str] = []
    ok = True
    any_checked = False

    pairs = [
        ("claims", rec.realisable_amount_cr, rec.admitted_claims_cr, rec.pct_of_claims),
        ("liq", rec.realisable_amount_cr, rec.liquidation_value_cr, rec.pct_of_liquidation_value),
        ("fair", rec.realisable_amount_cr, rec.fair_value_cr, rec.pct_of_fair_value),
    ]
    for label, num, den, stated in pairs:
        if num is None or den in (None, 0) or stated is None:
            continue
        any_checked = True
        implied = 100.0 * num / den

        # Worst-case error from +/-0.005 rounding on both numerator and denominator
        rounding_band = 100.0 * (
            abs((num + 0.005) / max(den - 0.005, 1e-9) - num / den)
            if den > 0.005 else abs(stated)
        )
        limit = max(tol, abs(stated) * 0.02, rounding_band)
        if abs(implied - stated) > limit:
            ok = False
            checks.append(f"{label}: implied {implied:.2f} vs stated {stated:.2f}")

    if not any_checked:
        return None, "no checkable pair"
    return ok, "; ".join(checks) if checks else "consistent"


def build_case(parsed: dict[str, Any], **meta: Any) -> CirpCase:
    """Build a validated CirpCase, repairing space-split numbers if needed.

    When the token count is too high, candidate merges are scored by the
    arithmetic check and the best-validating reading wins. The document's own
    published percentages therefore decide the parse rather than a heuristic.
    """
    best: CirpCase | None = None
    for toks in _merge_split_numbers(parsed["numeric_tokens"], expected=7):
        trial = dict(parsed, numeric_tokens=toks)
        rec = CirpCase(
            sl_no=trial["sl_no"],
            corporate_debtor=trial["corporate_debtor"],
            defunct=trial["defunct"],
            cirp_commencement_date=trial["cirp_commencement_date"],
            resolution_approval_date=trial["resolution_approval_date"],
            initiated_by=trial["initiated_by"],
            n_numeric_tokens=len(toks),
            raw_row=trial["raw_row"][:400],
            **map_numerics(trial),
            **meta,
        )
        rec.arithmetic_ok, rec.arithmetic_detail = validate_arithmetic(rec)
        if rec.arithmetic_ok is True:
            return rec
        if best is None or (rec.arithmetic_ok is None and best.arithmetic_ok is False):
            best = rec
    return best  # type: ignore[return-value]


# Header signatures, matched against a table's own header cells rather than the
# page text. Page-level matching fails on the 2020 editions, where the phrase
# "Yielding Resolution Plans" heads a different table on the same page and the
# resolution table itself carries no caption.
HEADER_SIGNATURES = {
    "cirp_resolution": (
        r"Name\s+of\s+(?:CD|Corporate\s+Debtor)",
        r"Admitted",
        r"Liquidation\s+Value|Realisable",
    ),
    "liquidation": (
        r"Name\s+of\s+(?:the\s+)?(?:CD|Corporate\s+Debtor)",
        r"Order\s+of\s+Liquidation",
        r"Sale\s+Proceeds",
    ),
    "voluntary_liquidation": (
        r"Name\s+of\s+Corporate",
        r"Dissolut",
        r"Liquidation\s+Expense",
    ),
}


def find_table_pages(pdf, signature: str = "cirp_resolution") -> list[int]:
    """Locate pages whose TABLE HEADERS match the signature.

    Header-based rather than page-text-based, because table captions and
    numbering are unstable across editions while the column names are not.
    """
    patterns = HEADER_SIGNATURES[signature]
    pages: list[int] = []
    for i, page in enumerate(pdf.pages):
        try:
            tables = page.extract_tables()
        except Exception:
            continue
        for table in tables or []:
            header = " ".join(
                str(c or "") for row in (table[:3] or []) for c in row
            )
            if all(re.search(p, header, re.I) for p in patterns):
                pages.append(i + 1)
                break
    return pages


def extract_cases(pdf, period: str, signature: str = "cirp_resolution") -> tuple[list[CirpCase], dict]:
    """Extract every case row for a signature from an open PDF.

    Scans the located page and the pages immediately after it, since these
    tables routinely continue across a page break without repeating a header.
    """
    start_pages = find_table_pages(pdf, signature)
    stats = {"pages_scanned": [], "rows_seen": 0, "rows_parsed": 0, "totals_rows": []}
    if not start_pages:
        return [], stats

    candidate_pages: list[int] = []
    for p in start_pages:
        for q in (p, p + 1, p + 2):
            if 1 <= q <= len(pdf.pages) and q not in candidate_pages:
                candidate_pages.append(q)

    cases: list[CirpCase] = []
    part = ""
    for pageno in sorted(candidate_pages):
        page = pdf.pages[pageno - 1]
        stats["pages_scanned"].append(pageno)

        # Try both strategies; row text is what matters, so take whichever
        # yields more parsable rows.
        candidates: list[list[list]] = []
        try:
            candidates.append(page.extract_tables())
        except Exception:
            pass
        try:
            candidates.append(page.extract_tables(
                {"vertical_strategy": "lines", "horizontal_strategy": "lines", "snap_tolerance": 4}
            ))
        except Exception:
            pass

        best_rows: list[CirpCase] = []
        for tables in candidates:
            got: list[CirpCase] = []
            local_part = part
            for table in tables or []:
                for row in table:
                    if not row:
                        continue
                    flat = " ".join(str(c or "") for c in row)
                    if re.search(r"Part\s+A\b", flat, re.I):
                        local_part = "A"
                    elif re.search(r"Part\s+B\b", flat, re.I):
                        local_part = "B"
                    if re.search(r"^\s*Total\b|\bTotal\s*\(", flat, re.I):
                        stats["totals_rows"].append(re.sub(r"\s+", " ", flat).strip()[:220])
                        continue
                    parsed = parse_row(flat)
                    if not parsed:
                        continue
                    got.append(build_case(
                        parsed,
                        source_period=period,
                        source_page=pageno,
                        part=local_part,
                    ))
            # prefer the strategy with more arithmetically valid rows
            score = (sum(1 for r in got if r.arithmetic_ok), len(got))
            best_score = (sum(1 for r in best_rows if r.arithmetic_ok), len(best_rows))
            if score > best_score:
                best_rows, part = got, local_part

        cases.extend(best_rows)
        stats["rows_seen"] += len(best_rows)

    # Deduplicate: the same case can appear on both a page and its continuation
    seen: set[tuple] = set()
    unique: list[CirpCase] = []
    for c in cases:
        key = (c.corporate_debtor.lower()[:60], c.cirp_commencement_date, c.resolution_approval_date)
        if key in seen:
            continue
        seen.add(key)
        unique.append(c)

    stats["rows_parsed"] = len(unique)
    return unique, stats
