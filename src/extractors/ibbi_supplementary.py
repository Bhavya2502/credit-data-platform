"""Remaining IBBI case-level tables (S-079): section 53 waterfall and voluntary liquidations.

Two tables that complete the source:

**Section 53 waterfall** — how liquidation proceeds are distributed across
statutory claim classes under the IBC. Aggregate across all closed liquidations
rather than case-level, but it is the only public quantification of
seniority-conditional recovery in India:

    s.52       secured creditors enforcing security outside liquidation
    s.53(1)(a) resolution and liquidation process costs
    s.53(1)(b) workmen dues (24 months) + secured creditors who relinquished
    s.53(1)(c) employee wages (12 months)
    s.53(1)(d) unsecured financial creditors
    s.53(1)(e) government dues + secured creditor shortfall
    s.53(1)(f) remaining debts
    s.53(1)(g) preference shareholders
    s.53(1)(h) equity

This is what lets an LGD model differentiate by claim rank instead of treating
all creditors alike — the single largest driver of wholesale LGD in every
jurisdiction that publishes it.

**Voluntary liquidations** — solvent companies winding themselves up. Creditors
are typically paid in full, so these are NOT credit-loss events and must not be
pooled with insolvency recoveries; they are captured for completeness and to
keep the source fully covered.
"""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass
from typing import Any

DATE = r"\d{1,2}[-/]\d{1,2}[-/]\d{2,4}"
NUM = re.compile(r"-?[\d,]+\.?\d*|NA|N\.A\.?|-", re.I)

WATERFALL_SIGNATURE = (r"Stakeholders?\s*(?:\n|\s)*under\s+Section", r"Claimants")
VOLUNTARY_SIGNATURE = (r"Name\s+of\s+Corporate\s+Person", r"Dissolut", r"Liquidation\s*(?:\n|\s)*Expense")

# Human-readable meaning of each statutory rank, carried with the data so the
# waterfall is interpretable without an IBC reference to hand.
SECTION_MEANING = {
    "52": "Secured creditors enforcing security outside liquidation",
    "53(1)(a)": "Resolution process and liquidation costs",
    "53(1)(b)": "Workmen dues (24 months) + secured creditors who relinquished security",
    "53(1)(c)": "Employee wages (12 months)",
    "53(1)(d)": "Unsecured financial creditors",
    "53(1)(e)": "Government dues + secured creditor shortfall",
    "53(1)(f)": "Remaining debts and dues",
    "53(1)(g)": "Preference shareholders",
    "53(1)(h)": "Equity shareholders / partners",
}


def _f(tok: str | None) -> float | None:
    if tok is None:
        return None
    t = str(tok).strip().replace(",", "")
    if t in {"", "-", "NA", "N.A", "N.A."} or t.lower() == "na":
        return None
    try:
        return float(t)
    except ValueError:
        return None


def _norm_section(raw: str) -> str | None:
    """'53 (1) (b)' -> '53(1)(b)'; '52' -> '52'."""
    s = re.sub(r"\s+", "", str(raw or ""))
    if re.fullmatch(r"52", s):
        return "52"
    m = re.fullmatch(r"53\(?1\)?\(?([a-h])\)?", s, re.I)
    if m:
        return f"53(1)({m.group(1).lower()})"
    m = re.fullmatch(r"53\((1)\)\(([a-h])\)", s, re.I)
    if m:
        return f"53(1)({m.group(2).lower()})"
    return None


# ─────────────────────────────── waterfall ────────────────────────────────
@dataclass
class WaterfallRow:
    section: str
    section_meaning: str
    block: str          # "closed" = final report submitted · "ongoing" = no distribution yet
    claimants: float | None
    claims_admitted_cr: float | None
    amount_realised_cr: float | None
    amount_distributed_cr: float | None
    recovery_pct: float | None
    source_period: str = ""
    source_page: int = 0
    raw_row: str = ""

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def extract_waterfall(pdf, period: str) -> tuple[list[WaterfallRow], dict]:
    out: list[WaterfallRow] = []
    stats: dict[str, Any] = {"pages_scanned": []}

    for i, page in enumerate(pdf.pages):
        try:
            tables = page.extract_tables()
        except Exception:
            continue
        for table in tables or []:
            header = " ".join(str(c or "") for row in (table[:3] or []) for c in row)
            if not all(re.search(p, header, re.I) for p in WATERFALL_SIGNATURE):
                continue
            stats["pages_scanned"].append(i + 1)

            # The table carries TWO blocks under one header:
            #   A) "N Liquidations where Final Report Submitted" — CLOSED cases,
            #      with an actual Amount Distributed
            #   B) "Ongoing N Liquidations" — claims admitted, nothing
            #      distributed yet; the distribution columns are empty
            #
            # Recovery may only be computed for block A. Treating block B's
            # admitted amount as distributed manufactures a flat 100% recovery
            # for every claim class — which is exactly what a "last populated
            # cell" heuristic produced before this was caught.
            block = ""
            for row in table:
                if not row or not row[0]:
                    continue
                first = re.sub(r"\s+", " ", str(row[0])).strip()

                if re.search(r"Final\s+Report\s+Submitted", first, re.I):
                    block = "closed"
                    continue
                if re.search(r"^Ongoing\b", first, re.I):
                    block = "ongoing"
                    continue

                section = _norm_section(row[0])
                if not section:
                    continue

                # Strict positional mapping against the published header:
                # claimants | claims admitted | liquidation value | realised | distributed
                # Cells can carry stacked values ("668.74\n21120.91"); take the
                # first number, which is the row's own figure.
                vals: list[float | None] = []
                for cell in row[1:6]:
                    tok = NUM.search(str(cell or "").split("\n")[0])
                    vals.append(_f(tok.group(0)) if tok else None)
                while len(vals) < 5:
                    vals.append(None)
                claimants, admitted, _liq_value, realised, distributed = vals[:5]

                # Ongoing liquidations have no distribution — never impute one.
                rec = None
                if block == "closed" and admitted and admitted > 0 and distributed is not None:
                    rec = round(100.0 * distributed / admitted, 4)

                out.append(WaterfallRow(
                    section=section,
                    section_meaning=SECTION_MEANING.get(section, ""),
                    block=block or "unknown",
                    claimants=claimants,
                    claims_admitted_cr=admitted,
                    amount_realised_cr=realised,
                    amount_distributed_cr=distributed if block == "closed" else None,
                    recovery_pct=rec,
                    source_period=period,
                    source_page=i + 1,
                    raw_row=re.sub(r"\s+", " ", " ".join(str(c or "") for c in row))[:300],
                ))
            break
    return out, stats


# ────────────────────────── voluntary liquidation ─────────────────────────
@dataclass
class VoluntaryLiquidationCase:
    sl_no: int
    corporate_person: str
    commencement_date: str | None
    dissolution_date: str | None
    realisation_of_assets_cr: float | None
    amount_due_to_creditors_cr: float | None
    amount_paid_to_creditors_cr: float | None
    liquidation_expenses_cr: float | None
    surplus_cr: float | None
    creditors_paid_in_full: bool | None
    source_period: str = ""
    source_page: int = 0
    structural_ok: bool | None = None
    structural_detail: str = ""
    raw_row: str = ""

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def extract_voluntary(pdf, period: str) -> tuple[list[VoluntaryLiquidationCase], dict]:
    out: list[VoluntaryLiquidationCase] = []
    stats: dict[str, Any] = {"pages_scanned": []}

    for i, page in enumerate(pdf.pages):
        try:
            tables = page.extract_tables()
        except Exception:
            continue
        for table in tables or []:
            header = " ".join(str(c or "") for row in (table[:3] or []) for c in row)
            if not all(re.search(p, header, re.I) for p in VOLUNTARY_SIGNATURE):
                continue
            stats["pages_scanned"].append(i + 1)

            for row in table:
                if not row or not row[0] or not str(row[0]).strip().isdigit():
                    continue
                flat = " ".join(str(c or "") for c in row)
                flat = re.sub(r"\s+", " ", flat).strip()

                dates = list(re.finditer(DATE, flat))
                if len(dates) < 1:
                    continue
                sl = int(str(row[0]).strip())
                name = flat[len(str(sl)):dates[0].start()].strip(" .-")
                if len(name) < 3:
                    continue

                tail = flat[dates[-1].end():]
                money = [_f(t) for t in NUM.findall(tail)]
                while len(money) < 5:
                    money.append(None)
                realisation, due, paid, expenses, surplus = money[:5]

                paid_full = None
                if due is not None and paid is not None:
                    paid_full = paid >= due - 0.005

                problems = []
                if paid is not None and due is not None and paid > due + 0.05:
                    problems.append(f"paid {paid} > due {due}")
                for label, v in (("realisation", realisation), ("paid", paid), ("surplus", surplus)):
                    if v is not None and v < 0:
                        problems.append(f"{label} negative")

                out.append(VoluntaryLiquidationCase(
                    sl_no=sl,
                    corporate_person=name,
                    commencement_date=dates[0].group(0),
                    dissolution_date=dates[-1].group(0) if len(dates) > 1 else None,
                    realisation_of_assets_cr=realisation,
                    amount_due_to_creditors_cr=due,
                    amount_paid_to_creditors_cr=paid,
                    liquidation_expenses_cr=expenses,
                    surplus_cr=surplus,
                    creditors_paid_in_full=paid_full,
                    source_period=period,
                    source_page=i + 1,
                    structural_ok=(not problems) if (due is not None or paid is not None) else None,
                    structural_detail="; ".join(problems) if problems else "consistent",
                    raw_row=flat[:300],
                ))
            break

    seen: set[tuple] = set()
    unique = []
    for c in out:
        key = (c.corporate_person.lower()[:60], c.commencement_date)
        if key in seen:
            continue
        seen.add(key)
        unique.append(c)
    return unique, stats
