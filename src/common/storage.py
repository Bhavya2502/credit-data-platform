"""Bronze-layer object storage on Cloudflare R2.

Bronze is immutable (ADR-003): every fetch writes a new timestamped object plus a
manifest record. Parsers are replayed against stored bronze objects rather than
re-fetching from the publisher — which protects history when a source changes or
disappears, and keeps our request volume low.
"""

from __future__ import annotations

import hashlib
import io
import json
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Iterator

import boto3
from botocore.config import Config
from botocore.exceptions import ClientError

from .settings import Settings


@dataclass
class BronzeObject:
    """Manifest record for one fetched file."""

    source_id: str
    key: str
    source_url: str
    fetched_at: str
    size_bytes: int
    sha256: str
    http_status: int
    content_type: str = ""
    notes: str = ""

    def to_json(self) -> str:
        return json.dumps(asdict(self), indent=2, sort_keys=True)


class BronzeStore:
    """Thin wrapper over the R2 S3-compatible API."""

    def __init__(self, settings: Settings):
        self._bucket = settings.bronze_bucket
        self._client = boto3.client(
            "s3",
            endpoint_url=settings.r2_endpoint,
            aws_access_key_id=settings.r2_access_key_id,
            aws_secret_access_key=settings.r2_secret_access_key,
            # R2 ignores regions but boto3 requires one; "auto" is Cloudflare's convention.
            region_name="auto",
            config=Config(
                retries={"max_attempts": 5, "mode": "standard"},
                s3={"addressing_style": "path"},
            ),
        )

    # ── health ────────────────────────────────────────────────────────
    def check_access(self) -> tuple[bool, str]:
        """Verify credentials and bucket reachability. Returns (ok, detail)."""
        try:
            self._client.head_bucket(Bucket=self._bucket)
            return True, f"bucket '{self._bucket}' reachable"
        except ClientError as exc:
            code = exc.response.get("Error", {}).get("Code", "unknown")
            hint = {
                "404": "bucket not found — check the name is exactly 'credit-data-lake'",
                "403": "access denied — the API token may lack Object Read & Write on this bucket",
                "SignatureDoesNotMatch": "secret key looks wrong — re-copy R2_SECRET_ACCESS_KEY",
                "InvalidAccessKeyId": "access key id looks wrong — re-copy R2_ACCESS_KEY_ID",
            }.get(code, "")
            return False, f"{code}: {exc.response.get('Error', {}).get('Message', exc)}" + (
                f" — {hint}" if hint else ""
            )
        except Exception as exc:  # endpoint typos surface here, not as ClientError
            return False, f"{type(exc).__name__}: {exc} — check R2_ENDPOINT is the full https URL"

    # ── paths ─────────────────────────────────────────────────────────
    @staticmethod
    def bronze_key(source_id: str, filename: str, when: datetime | None = None) -> str:
        ts = when or datetime.now(timezone.utc)
        return f"bronze/{source_id}/{ts:%Y/%m/%d}/{ts:%H%M%S}_{filename}"

    # ── writes ────────────────────────────────────────────────────────
    def put_bytes(
        self,
        *,
        source_id: str,
        filename: str,
        payload: bytes,
        source_url: str,
        http_status: int = 200,
        content_type: str = "",
        notes: str = "",
    ) -> BronzeObject:
        """Write one object to bronze and return its manifest record."""
        now = datetime.now(timezone.utc)
        key = self.bronze_key(source_id, filename, now)

        self._client.put_object(
            Bucket=self._bucket,
            Key=key,
            Body=payload,
            ContentType=content_type or "application/octet-stream",
        )

        record = BronzeObject(
            source_id=source_id,
            key=key,
            source_url=source_url,
            fetched_at=now.isoformat(),
            size_bytes=len(payload),
            sha256=hashlib.sha256(payload).hexdigest(),
            http_status=http_status,
            content_type=content_type,
            notes=notes,
        )

        # Manifest sits beside the object so bronze is self-describing even if
        # the catalog database is rebuilt from scratch.
        self._client.put_object(
            Bucket=self._bucket,
            Key=f"{key}.manifest.json",
            Body=record.to_json().encode(),
            ContentType="application/json",
        )
        return record

    # ── reads ─────────────────────────────────────────────────────────
    def get_bytes(self, key: str) -> bytes:
        buf = io.BytesIO()
        self._client.download_fileobj(self._bucket, key, buf)
        return buf.getvalue()

    def list_keys(self, prefix: str) -> Iterator[str]:
        paginator = self._client.get_paginator("list_objects_v2")
        for page in paginator.paginate(Bucket=self._bucket, Prefix=prefix):
            for item in page.get("Contents", []):
                key = item["Key"]
                if not key.endswith(".manifest.json"):
                    yield key

    def latest_key(self, source_id: str) -> str | None:
        """Most recent bronze object for a source (keys sort chronologically)."""
        keys = sorted(self.list_keys(f"bronze/{source_id}/"))
        return keys[-1] if keys else None
