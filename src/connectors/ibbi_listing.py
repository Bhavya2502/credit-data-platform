"""Discovery for S-079 — the IBBI newsletter listing.

Newsletter PDFs carry opaque hash filenames with no date, so the listing table
is the only source of period metadata. Two quirks defeat naive scraping:
links are unquoted in the HTML (href=/uploads/... with no quote characters),
and the listing is paginated with no "next" marker on the final page.
"""

from __future__ import annotations

import html
import re
import time
from dataclasses import dataclass

import httpx

BASE = "https://ibbi.gov.in"
LISTING = f"{BASE}/publication"
UA = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
    )
}

MONTHS = {m: i for i, m in enumerate(
    ["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"], 1
)}


@dataclass
class Newsletter:
    period: str          # as printed, e.g. "Jan, 2026 - Mar, 2026"
    title: str
    url: str
    size: str
    year: int | None = None
    quarter: int | None = None

    @property
    def slug(self) -> str:
        if self.year and self.quarter:
            return f"{self.year}Q{self.quarter}"
        return re.sub(r"[^A-Za-z0-9]+", "_", self.period)[:40] or "unknown"


def _parse_period(period: str) -> tuple[int | None, int | None]:
    """'Jan, 2026 - Mar, 2026' -> (2026, 1). Quarter from the END month."""
    months = re.findall(r"([A-Za-z]{3})[a-z]*,?\s*(\d{4})", period)
    if not months:
        return None, None
    mon, year = months[-1]
    m = MONTHS.get(mon.lower())
    if not m:
        return int(year), None
    return int(year), (m - 1) // 3 + 1


def discover(max_pages: int = 10, rate_limit: float = 2.0) -> list[Newsletter]:
    """Crawl the listing and return English newsletters, newest first."""
    out: list[Newsletter] = []
    seen: set[str] = set()

    with httpx.Client(follow_redirects=True, timeout=120.0, headers=UA) as client:
        for page in range(1, max_pages + 1):
            url = LISTING + (f"?page={page}" if page > 1 else "")
            resp = client.get(url)
            if resp.status_code != 200:
                break

            for tr in re.findall(r"<tr[^>]*>(.*?)</tr>", resp.text, re.S):
                if "/uploads/publication/" not in tr:
                    continue
                m = re.search(r'href=["\']?(/uploads/publication/[^"\'\s>]+\.pdf)', tr, re.I)
                if not m:
                    continue
                href = html.unescape(m.group(1))
                if href in seen:
                    continue

                cells = [
                    re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", td)).strip()
                    for td in re.findall(r"<td[^>]*>(.*?)</td>", tr, re.S)
                ]
                period = next((c for c in cells if re.search(r"\d{4}", c) and "-" in c), "")
                title = next((c for c in cells if "NEWSLETTER" in c.upper()), "")
                size = (re.search(r"\(([\d.]+ ?[KM]B)\)", tr) or [None, ""])[1]

                # Hindi editions duplicate the English content
                if "hindi" in title.lower() or "hindi" in href.lower():
                    continue

                seen.add(href)
                year, quarter = _parse_period(period)
                out.append(Newsletter(
                    period=period, title=title, url=BASE + href,
                    size=size or "", year=year, quarter=quarter,
                ))

            if "?page=" not in resp.text:
                break
            time.sleep(rate_limit)

    out.sort(key=lambda n: (n.year or 0, n.quarter or 0), reverse=True)
    return out


def fetch_pdf(url: str, timeout: float = 600.0) -> bytes:
    with httpx.Client(follow_redirects=True, timeout=timeout, headers=UA) as client:
        resp = client.get(url)
        resp.raise_for_status()
        return resp.content
