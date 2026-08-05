"""Runtime configuration, read from environment variables.

Secrets are injected by GitHub Actions from repository secrets; nothing is ever
read from a file on disk or committed to the repository (see ADR-002, ADR-007).
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field

BRONZE_BUCKET = "credit-data-lake"
MD_DATABASE = "credit_data"


class MissingCredential(RuntimeError):
    """Raised when a required secret is absent from the environment."""


def _env(name: str, *, required: bool = True) -> str:
    value = os.environ.get(name, "").strip()
    if required and not value:
        raise MissingCredential(
            f"Environment variable {name} is not set. "
            f"In GitHub Actions this comes from repository secrets; "
            f"check Settings → Secrets and variables → Actions."
        )
    return value


@dataclass(frozen=True)
class Settings:
    """All external service configuration for a pipeline run."""

    r2_access_key_id: str = field(repr=False)
    r2_secret_access_key: str = field(repr=False)
    r2_endpoint: str
    motherduck_token: str = field(repr=False)
    openrouter_api_key: str = field(repr=False)

    bronze_bucket: str = BRONZE_BUCKET
    md_database: str = MD_DATABASE

    @classmethod
    def from_env(cls, *, require_llm: bool = False) -> "Settings":
        return cls(
            r2_access_key_id=_env("R2_ACCESS_KEY_ID"),
            r2_secret_access_key=_env("R2_SECRET_ACCESS_KEY"),
            # A trailing slash breaks boto3's endpoint handling — normalise it away.
            r2_endpoint=_env("R2_ENDPOINT").rstrip("/"),
            motherduck_token=_env("MOTHERDUCK_TOKEN"),
            openrouter_api_key=_env("OPENROUTER_API_KEY", required=require_llm),
        )
