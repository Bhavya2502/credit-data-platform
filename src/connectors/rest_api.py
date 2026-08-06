"""Archetype B — structured REST API connector.

Reusable across any source that exposes JSON over HTTP with query parameters
(FDIC, FRED, IMF, BIS, Brazil BCB, World Bank). Handles retries, backoff, rate
limiting and pagination; hands raw payloads to the caller for bronze storage.

Politeness here is a reliability requirement, not etiquette: a blocked IP breaks
a pipeline permanently, and re-establishing access costs far more than the
throttling ever saved (PLATFORM_PLAN §6.2).
"""

from __future__ import annotations

import gzip
import json
import time
from dataclasses import dataclass
from typing import Any

import httpx
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)


class FetchError(RuntimeError):
    """Raised when a source cannot be fetched after exhausting retries."""


@dataclass
class ApiResponse:
    """One API call: parsed payload plus the raw bytes destined for bronze."""

    url: str
    status_code: int
    payload: dict[str, Any]
    raw_bytes: bytes
    fetched_seconds: float

    def gzipped(self) -> bytes:
        """Bronze stores gzip — JSON compresses roughly 10x."""
        return gzip.compress(self.raw_bytes, compresslevel=6)


class RestApiConnector:
    """Polite JSON API client."""

    def __init__(
        self,
        *,
        base_url: str,
        headers: dict[str, str] | None = None,
        rate_limit_seconds: float = 1.0,
        timeout_seconds: float = 120.0,
        max_retries: int = 3,
    ):
        self.base_url = base_url.rstrip("/")
        self.headers = headers or {"User-Agent": "credit-data-platform/0.1"}
        self.rate_limit_seconds = rate_limit_seconds
        self.timeout_seconds = timeout_seconds
        self.max_retries = max_retries
        self._last_request_at = 0.0

    def _throttle(self) -> None:
        elapsed = time.monotonic() - self._last_request_at
        if elapsed < self.rate_limit_seconds:
            time.sleep(self.rate_limit_seconds - elapsed)
        self._last_request_at = time.monotonic()

    def get(self, params: dict[str, Any]) -> ApiResponse:
        """Single GET with retry/backoff. Raises FetchError on final failure."""

        @retry(
            stop=stop_after_attempt(self.max_retries),
            wait=wait_exponential(multiplier=2, min=2, max=30),
            retry=retry_if_exception_type((httpx.HTTPError, FetchError)),
            reraise=True,
        )
        def _attempt() -> ApiResponse:
            self._throttle()
            started = time.monotonic()
            with httpx.Client(follow_redirects=True, timeout=self.timeout_seconds) as client:
                resp = client.get(self.base_url, params=params, headers=self.headers)

            # 5xx and 429 are transient — retry. 4xx (except 429) will not
            # improve on retry, so fail immediately with a useful message.
            if resp.status_code >= 500 or resp.status_code == 429:
                raise FetchError(f"HTTP {resp.status_code} from {resp.url}")
            if resp.status_code >= 400:
                raise FetchError(
                    f"HTTP {resp.status_code} from {resp.url} — "
                    f"non-retryable. Body: {resp.text[:200]}"
                )

            try:
                payload = resp.json()
            except json.JSONDecodeError as exc:
                raise FetchError(
                    f"Response was not JSON ({resp.headers.get('content-type')}). "
                    f"First 200 chars: {resp.text[:200]}"
                ) from exc

            return ApiResponse(
                url=str(resp.url),
                status_code=resp.status_code,
                payload=payload,
                raw_bytes=resp.content,
                fetched_seconds=round(time.monotonic() - started, 2),
            )

        return _attempt()


class FdicConnector(RestApiConnector):
    """FDIC BankFind Suite specifics.

    The API wraps records as {"data": [{"data": {...}}, ...]} and reports the
    true row count in meta.total — which we use as the extraction-completeness
    control rather than trusting len(data).
    """

    BASE = "https://api.fdic.gov/banks/financials"
    PAGE_LIMIT = 10_000  # observed maximum accepted by the endpoint

    def __init__(self, **kwargs: Any):
        kwargs.setdefault("base_url", self.BASE)
        super().__init__(**kwargs)

    def fetch_quarter(self, repdte: str) -> tuple[list[dict[str, Any]], ApiResponse, int]:
        """Fetch every institution for one report date (YYYYMMDD).

        Returns (records, first_response, api_total). Paginates when an era has
        more institutions than PAGE_LIMIT — 1992 had 14,028.
        """
        first = self.get(
            {"filters": f"REPDTE:{repdte}", "limit": self.PAGE_LIMIT, "format": "json"}
        )
        api_total = int(first.payload.get("meta", {}).get("total", 0))
        records = [row["data"] for row in first.payload.get("data", [])]

        offset = len(records)
        while offset < api_total:
            page = self.get(
                {
                    "filters": f"REPDTE:{repdte}",
                    "limit": self.PAGE_LIMIT,
                    "offset": offset,
                    "format": "json",
                }
            )
            batch = [row["data"] for row in page.payload.get("data", [])]
            if not batch:
                break  # defensive: never spin if the API stops returning rows
            records.extend(batch)
            offset += len(batch)

        return records, first, api_total


def quarter_ends(start_year: int, start_quarter: int, end_repdte: str) -> list[str]:
    """Quarter-end dates as YYYYMMDD, inclusive, for backfill planning."""
    ends = {1: "0331", 2: "0630", 3: "0930", 4: "1231"}
    out: list[str] = []
    year, quarter = start_year, start_quarter
    while True:
        repdte = f"{year}{ends[quarter]}"
        if repdte > end_repdte:
            break
        out.append(repdte)
        quarter += 1
        if quarter > 4:
            year, quarter = year + 1, 1
    return out
