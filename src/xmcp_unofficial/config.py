"""Runtime settings, read from environment variables."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


def _float_env(key: str, default: float) -> float:
    val = os.getenv(key)
    if not val:
        return default
    try:
        return float(val)
    except ValueError as e:
        raise ValueError(f"{key} must be a number, got {val!r}") from e


def _delay_env(key: str) -> float | tuple[float, float] | None:
    # "2" -> fixed 2s, "1.5-4" -> random between 1.5s and 4s
    val = os.getenv(key)
    if not val:
        return None
    try:
        if "-" in val:
            lo, hi = (float(x) for x in val.split("-", 1))
            return (lo, hi)
        return float(val)
    except ValueError as e:
        raise ValueError(f"{key} must look like '2' or '1.5-4', got {val!r}") from e


def default_db_path() -> Path:
    return Path.home() / ".xmcp_unofficial" / "accounts.db"


@dataclass(frozen=True)
class Settings:
    db_path: Path
    proxy: str | None
    req_delay: float | tuple[float, float] | None
    timeout: float
    max_limit: int

    @classmethod
    def from_env(cls) -> Settings:
        db = os.getenv("XMCP_DB")
        return cls(
            db_path=Path(db).expanduser() if db else default_db_path(),
            proxy=os.getenv("XMCP_PROXY") or None,
            req_delay=_delay_env("XMCP_REQ_DELAY"),
            timeout=_float_env("XMCP_TIMEOUT", 120.0),
            max_limit=int(_float_env("XMCP_MAX_LIMIT", 200)),
        )
