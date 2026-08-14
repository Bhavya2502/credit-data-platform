"""Archetype I — authenticated Kaggle API download.

Kaggle hosts several of the few genuinely borrower-level credit datasets that
exist publicly. Unlike our other sources these require credentials, and
competition data carries an extra gate: the account must have accepted that
competition's rules **in a browser** before the API will serve the files.

That gate is why this connector probes first. An unaccepted competition returns
403 on download — after the request has been made, and with a message that does
not name the real cause. Checking accessibility up front turns a confusing
mid-run failure into a clear pre-run report.

Uses the REST API directly with HTTP Basic auth rather than the `kaggle`
package, which is built around CLI usage and writes credential files to disk.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from pathlib import Path

import httpx
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

API = "https://www.kaggle.com/api/v1"


class KaggleError(RuntimeError):
    pass


@dataclass
class KaggleTarget:
    """A dataset or competition to fetch."""

    key: str                    # our short name
    kind: str                   # "competition" | "dataset"
    ref: str                    # competition slug, or "owner/dataset-slug"
    note: str = ""

    @property
    def download_url(self) -> str:
        if self.kind == "competition":
            return f"{API}/competitions/data/download-all/{self.ref}"
        return f"{API}/datasets/download/{self.ref}"

    @property
    def metadata_url(self) -> str:
        if self.kind == "competition":
            return f"{API}/competitions/list?search={self.ref}"
        owner, slug = self.ref.split("/", 1)
        return f"{API}/datasets/list?user={owner}&search={slug}"


@dataclass
class ProbeResult:
    target: KaggleTarget
    status_code: int
    accessible: bool
    size_bytes: int | None
    reason: str


def _auth(username: str, key: str) -> tuple[str, str]:
    if not username or not key:
        raise KaggleError(
            "KAGGLE_USERNAME / KAGGLE_KEY not set. In GitHub Actions these come "
            "from repository secrets."
        )
    return (username, key)


def probe(target: KaggleTarget, *, username: str, key: str, timeout: float = 60.0) -> ProbeResult:
    """Check whether the credentials can actually reach this target.

    Kaggle answers a download request with a redirect to storage when access is
    granted, so we deliberately do NOT follow redirects — a 302 is the success
    signal and costs nothing, whereas following it would start the transfer.
    """
    try:
        with httpx.Client(follow_redirects=False, timeout=timeout) as client:
            resp = client.get(target.download_url, auth=_auth(username, key))
    except Exception as exc:
        return ProbeResult(target, 0, False, None, f"{type(exc).__name__}: {exc}")

    code = resp.status_code
    size = None
    if "content-length" in resp.headers:
        try:
            size = int(resp.headers["content-length"])
        except ValueError:
            pass

    if code in (200, 206, 301, 302, 303, 307, 308):
        return ProbeResult(target, code, True, size, "accessible")
    if code == 403:
        hint = (
            "rules not accepted — open the competition page in a browser and "
            "accept the rules"
            if target.kind == "competition"
            else "forbidden — check the dataset is public and the token is valid"
        )
        return ProbeResult(target, code, False, size, hint)
    if code == 401:
        return ProbeResult(target, code, False, size, "unauthorised — token invalid or expired")
    if code == 404:
        return ProbeResult(target, code, False, size, "not found — check the ref/slug")
    return ProbeResult(target, code, False, size, f"unexpected HTTP {code}")


def download(
    target: KaggleTarget,
    *,
    username: str,
    key: str,
    dest_dir: str | Path,
    timeout: float = 3600.0,
    max_retries: int = 3,
) -> Path:
    """Stream the archive to disk. Returns the written path."""
    dest = Path(dest_dir)
    dest.mkdir(parents=True, exist_ok=True)
    out = dest / f"{target.key}.zip"

    @retry(
        stop=stop_after_attempt(max_retries),
        wait=wait_exponential(multiplier=2, min=3, max=40),
        retry=retry_if_exception_type((httpx.HTTPError, KaggleError)),
        reraise=True,
    )
    def _attempt() -> Path:
        started = time.monotonic()
        size = 0
        with httpx.Client(follow_redirects=True, timeout=timeout) as client:
            with client.stream("GET", target.download_url, auth=_auth(username, key)) as resp:
                if resp.status_code == 403:
                    raise KaggleError(
                        f"403 for {target.ref} — competition rules likely not accepted. "
                        f"This is not retryable; accept the rules in a browser first."
                    )
                if resp.status_code >= 500 or resp.status_code == 429:
                    raise KaggleError(f"HTTP {resp.status_code} for {target.ref}")
                if resp.status_code >= 400:
                    raise KaggleError(f"HTTP {resp.status_code} for {target.ref} — non-retryable")
                with out.open("wb") as fh:
                    for chunk in resp.iter_bytes(chunk_size=1 << 20):
                        fh.write(chunk)
                        size += len(chunk)
        if size == 0:
            raise KaggleError(f"Downloaded 0 bytes for {target.ref}")
        print(f"     downloaded {size/1_048_576:.1f} MB in {time.monotonic()-started:.0f}s")
        return out

    return _attempt()


# The five borrower-level datasets worth having. Competition entries require
# browser rule-acceptance; dataset entries do not.
TARGETS: list[KaggleTarget] = [
    KaggleTarget(
        key="amex_default",
        kind="competition",
        ref="amex-default-prediction",
        note="459k customers x monthly statements, 190 anonymised features — behavioural PD",
    ),
    KaggleTarget(
        key="home_credit_stability",
        kind="competition",
        ref="home-credit-credit-risk-model-stability",
        note="relational, decision-dated, out-of-time weekly splits — model stability testbed",
    ),
    KaggleTarget(
        key="home_credit_default",
        kind="competition",
        ref="home-credit-default-risk",
        note="application + bureau + prior applications — EM application scorecard",
    ),
    KaggleTarget(
        key="lending_club",
        kind="dataset",
        ref="wordsforthewise/lending-club",
        note="2.2M loans INCLUDING rejected applications — reject inference",
    ),
    KaggleTarget(
        key="ltfs_vehicle",
        kind="dataset",
        ref="mamtadhaker/lt-vehicle-loan-default-prediction",
        note="233k Indian vehicle loans with CIBIL scores — the only India loan-level set",
    ),
]
