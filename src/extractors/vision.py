"""Archetype H — LLM vision extraction for image-only documents.

Last resort in the extraction ladder (ADR-005). Seven IBBI editions
(2022 Q1, 2023 Q1-Q4, 2024 Q1-Q2) are page scans with no text layer at all —
pdfplumber and PyMuPDF both return zero characters, so no amount of parser
work can read them. These are also the editions covering IBC's heaviest
resolution years, so skipping them would bias the recovery panel.

Non-negotiable rule: vision output is a *hypothesis*, not data. Every row must
pass the same arithmetic self-check as the deterministic path — recomputing
realisable/admitted x 100 against the row's own printed percentage — before it
is allowed into the panel. Rows that cannot self-verify are quarantined with
their extraction method recorded, so a reader can always tell how a number
was obtained.
"""

from __future__ import annotations

import base64
import json
import os
import re
from dataclasses import dataclass
from typing import Any

import httpx

OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"

# Cheap, strong at table reading. Overridable per call.
DEFAULT_MODEL = "google/gemini-2.5-flash"

SYSTEM_PROMPT = """You extract tabular data from scanned Indian insolvency \
(IBBI) newsletter pages. You transcribe only what is visibly printed. \
You never estimate, infer, or fill in missing values."""

USER_PROMPT = """This page may contain the table "CIRPs Yielding Resolution Plans" \
listing corporate debtors resolved under India's Insolvency and Bankruptcy Code.

If the page does NOT contain that table, return exactly: {"rows": []}

If it DOES, return one JSON object per data row with these keys:
  sl_no                      integer, the serial number
  corporate_debtor           string, company name exactly as printed
  defunct                    "Yes", "No", "NA", or null
  cirp_commencement_date     string as printed (e.g. "07-08-2019")
  resolution_approval_date   string as printed
  initiated_by               "FC", "OC", or "CD"
  admitted_claims_cr         number, Total Admitted Claims (Rs crore)
  liquidation_value_cr       number, Liquidation Value (Rs crore)
  fair_value_cr              number or null, Fair Value (Rs crore)
  realisable_amount_cr       number, Total Realisable Amount by Claimants
  pct_of_claims              number, realisable as % of admitted claims
  pct_of_liquidation_value   number, realisable as % of liquidation value
  pct_of_fair_value          number or null, realisable as % of fair value

Rules:
- Use null for any cell printed as "-", "NA", or blank. Never guess a value.
- Transcribe numbers exactly, including decimals. Do not round or recompute.
- Do not include total/subtotal rows, headers, or "Part A"/"Part B" markers.
- Return ONLY JSON: {"rows": [ ... ]}"""


@dataclass
class VisionResult:
    rows: list[dict[str, Any]]
    model: str
    page: int
    prompt_tokens: int = 0
    completion_tokens: int = 0
    cost_usd: float | None = None
    error: str = ""


def render_page_png(pdf_path_or_doc, page_index: int, dpi: int = 200) -> bytes:
    """Render one page to PNG. 200 dpi is legible for these scans without bloat."""
    import fitz

    doc = fitz.open(pdf_path_or_doc) if isinstance(pdf_path_or_doc, (str, bytes)) else pdf_path_or_doc
    page = doc[page_index]
    pix = page.get_pixmap(dpi=dpi)
    return pix.tobytes("png")


def _extract_json(text: str) -> dict:
    """Pull the JSON object out of a model response tolerant of code fences."""
    text = text.strip()
    fenced = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.S)
    if fenced:
        text = fenced.group(1)
    else:
        brace = re.search(r"\{.*\}", text, re.S)
        if brace:
            text = brace.group(0)
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return {"rows": []}


def extract_page(
    png_bytes: bytes,
    *,
    page_number: int,
    api_key: str | None = None,
    model: str = DEFAULT_MODEL,
    timeout: float = 180.0,
) -> VisionResult:
    """Send one rendered page to a vision model and return candidate rows."""
    key = api_key or os.environ.get("OPENROUTER_API_KEY", "")
    if not key:
        return VisionResult([], model, page_number, error="OPENROUTER_API_KEY not set")

    b64 = base64.b64encode(png_bytes).decode()
    payload = {
        "model": model,
        "temperature": 0,          # transcription, not generation
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": USER_PROMPT},
                    {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{b64}"}},
                ],
            },
        ],
    }
    headers = {
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://github.com/Bhavya2502/credit-data-platform",
        "X-Title": "credit-data-platform",
    }

    try:
        with httpx.Client(timeout=timeout) as client:
            resp = client.post(OPENROUTER_URL, json=payload, headers=headers)
        if resp.status_code >= 400:
            return VisionResult([], model, page_number, error=f"HTTP {resp.status_code}: {resp.text[:200]}")
        body = resp.json()
    except Exception as exc:
        return VisionResult([], model, page_number, error=f"{type(exc).__name__}: {exc}")

    content = (body.get("choices") or [{}])[0].get("message", {}).get("content", "")
    usage = body.get("usage") or {}
    parsed = _extract_json(content if isinstance(content, str) else str(content))
    rows = parsed.get("rows") or []
    if not isinstance(rows, list):
        rows = []

    return VisionResult(
        rows=[r for r in rows if isinstance(r, dict)],
        model=model,
        page=page_number,
        prompt_tokens=usage.get("prompt_tokens", 0),
        completion_tokens=usage.get("completion_tokens", 0),
        cost_usd=usage.get("cost"),
    )


def to_cirp_cases(result: VisionResult, period: str, page: int) -> list:
    """Convert vision rows into validated CirpCase records.

    Reuses the deterministic path's arithmetic check verbatim, so a
    vision-extracted row faces exactly the same evidential bar as a parsed one.
    """
    from .ibbi_cirp import CirpCase, validate_arithmetic

    out = []
    for r in result.rows:
        try:
            sl = int(r.get("sl_no") or 0)
        except (TypeError, ValueError):
            sl = 0
        name = str(r.get("corporate_debtor") or "").strip()
        if not name or len(name) < 3:
            continue

        def num(k: str):
            v = r.get(k)
            if v in (None, "", "-", "NA"):
                return None
            try:
                return float(str(v).replace(",", "").replace("%", ""))
            except ValueError:
                return None

        rec = CirpCase(
            sl_no=sl,
            corporate_debtor=name,
            defunct=(str(r["defunct"]).strip() if r.get("defunct") else None),
            cirp_commencement_date=(str(r["cirp_commencement_date"]) if r.get("cirp_commencement_date") else None),
            resolution_approval_date=(str(r["resolution_approval_date"]) if r.get("resolution_approval_date") else None),
            initiated_by=(str(r["initiated_by"]).upper() if r.get("initiated_by") else None),
            admitted_claims_cr=num("admitted_claims_cr"),
            liquidation_value_cr=num("liquidation_value_cr"),
            fair_value_cr=num("fair_value_cr"),
            realisable_amount_cr=num("realisable_amount_cr"),
            pct_of_claims=num("pct_of_claims"),
            pct_of_liquidation_value=num("pct_of_liquidation_value"),
            pct_of_fair_value=num("pct_of_fair_value"),
            source_period=period,
            source_page=page,
            part="",
            n_numeric_tokens=7,
            raw_row=json.dumps(r)[:400],
        )
        rec.arithmetic_ok, rec.arithmetic_detail = validate_arithmetic(rec)
        out.append(rec)
    return out
