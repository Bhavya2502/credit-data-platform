"""Archetype A — bulk file download.

Reusable for any source that publishes a whole dataset as one file: Bondora,
Freddie Mac, SBA, MIX Market, EBA CSVs. Streams to disk rather than holding the
payload in memory, since these run to hundreds of megabytes.

Conditional fetching is the point of the HEAD probe: these files are republished
on a schedule but only change when the publisher refreshes them. Comparing
Last-Modified and Content-Length against the previous fetch avoids pulling
150 MB to discover nothing moved — politeness and runtime both.
"""

from __future__ import annotations

import hashlib
import shutil
import tempfile
from dataclasses import dataclass
from pathlib import Path

import httpx
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential


class FetchError(RuntimeError):
    pass


@dataclass
class RemoteFileInfo:
    url: str
    status_code: int
    content_length: int | None
    content_type: str
    last_modified: str
    etag: str


@dataclass
class DownloadedFile:
    path: Path
    url: str
    size_bytes: int
    sha256: str
    content_type: str
    last_modified: str
    seconds: float

    def read_bytes(self) -> bytes:
        return self.path.read_bytes()


def probe(url: str, headers: dict[str, str] | None = None, timeout: float = 60.0) -> RemoteFileInfo:
    """HEAD the file to learn size and freshness before committing to a download."""
    with httpx.Client(follow_redirects=True, timeout=timeout) as client:
        resp = client.head(url, headers=headers or {})
    return RemoteFileInfo(
        url=str(resp.url),
        status_code=resp.status_code,
        content_length=int(resp.headers["content-length"]) if "content-length" in resp.headers else None,
        content_type=resp.headers.get("content-type", ""),
        last_modified=resp.headers.get("last-modified", ""),
        etag=resp.headers.get("etag", ""),
    )


def download(
    url: str,
    *,
    headers: dict[str, str] | None = None,
    timeout: float = 900.0,
    max_retries: int = 3,
    dest_dir: str | Path | None = None,
    filename: str | None = None,
) -> DownloadedFile:
    """Stream a file to disk, hashing as it goes."""
    import time

    target_dir = Path(dest_dir) if dest_dir else Path(tempfile.mkdtemp(prefix="bulkfile_"))
    target_dir.mkdir(parents=True, exist_ok=True)
    name = filename or url.rsplit("/", 1)[-1].split("?")[0] or "download.bin"
    target = target_dir / name

    @retry(
        stop=stop_after_attempt(max_retries),
        wait=wait_exponential(multiplier=2, min=2, max=30),
        retry=retry_if_exception_type((httpx.HTTPError, FetchError)),
        reraise=True,
    )
    def _attempt() -> DownloadedFile:
        started = time.monotonic()
        digest = hashlib.sha256()
        size = 0
        ctype = last_mod = ""

        with httpx.Client(follow_redirects=True, timeout=timeout) as client:
            with client.stream("GET", url, headers=headers or {}) as resp:
                if resp.status_code >= 500 or resp.status_code == 429:
                    raise FetchError(f"HTTP {resp.status_code} from {resp.url}")
                if resp.status_code >= 400:
                    raise FetchError(
                        f"HTTP {resp.status_code} from {resp.url} — non-retryable"
                    )
                ctype = resp.headers.get("content-type", "")
                last_mod = resp.headers.get("last-modified", "")
                with target.open("wb") as fh:
                    for chunk in resp.iter_bytes(chunk_size=1 << 20):
                        fh.write(chunk)
                        digest.update(chunk)
                        size += len(chunk)

        if size == 0:
            raise FetchError(f"Downloaded 0 bytes from {url}")

        return DownloadedFile(
            path=target, url=url, size_bytes=size, sha256=digest.hexdigest(),
            content_type=ctype, last_modified=last_mod,
            seconds=round(time.monotonic() - started, 1),
        )

    return _attempt()


def cleanup(downloaded: DownloadedFile) -> None:
    """Remove the temp directory a download created."""
    try:
        shutil.rmtree(downloaded.path.parent, ignore_errors=True)
    except Exception:
        pass
