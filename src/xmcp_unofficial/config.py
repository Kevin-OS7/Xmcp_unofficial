"""Runtime settings.

Precedence, highest first: environment variables (e.g. the `env` block of an MCP client
config), then `~/.xmcp_unofficial/config.toml` (written by `xmcp-unofficial setup`), then
built-in defaults. Keeping settings in the file means every MCP client shares them.
"""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

if sys.version_info >= (3, 11):
    import tomllib
else:  # pragma: no cover
    import tomli as tomllib

Delay = float | tuple[float, float] | None

# Pause between paginated requests unless configured otherwise: bursts of back-to-back
# requests are what gets scraping accounts flagged first.
DEFAULT_REQ_DELAY: Delay = 1.5


def home_dir() -> Path:
    return Path.home() / ".xmcp_unofficial"


def config_path() -> Path:
    p = os.getenv("XMCP_CONFIG")
    return Path(p).expanduser() if p else home_dir() / "config.toml"


def default_db_path() -> Path:
    return home_dir() / "accounts.db"


def parse_delay(val: Any, key: str = "req_delay") -> Delay:
    """`2` -> fixed 2s, `"1.5-4"` or `[1.5, 4]` -> random in range, `0` -> no delay."""
    try:
        if isinstance(val, (list, tuple)):
            lo, hi = (float(x) for x in val)
        elif isinstance(val, str) and "-" in val.strip()[1:]:
            lo, hi = (float(x) for x in val.split("-", 1))
        else:
            d = float(val)
            if d < 0:
                raise ValueError
            return d or None
        if not 0 <= lo <= hi:
            raise ValueError
        return (lo, hi)
    except (TypeError, ValueError) as e:
        raise ValueError(f"{key} must look like 2, '1.5-4' or [1.5, 4]; got {val!r}") from e


def format_delay(d: Delay) -> str:
    if d is None:
        return "0"
    if isinstance(d, tuple):
        return f"{d[0]:g}-{d[1]:g}"
    return f"{d:g}"


def load_file(path: Path | None = None) -> dict[str, Any]:
    path = path or config_path()
    if not path.exists():
        return {}
    try:
        with path.open("rb") as f:
            return tomllib.load(f)
    except tomllib.TOMLDecodeError as e:
        raise ValueError(f"Invalid config file {path}: {e}") from e


@dataclass(frozen=True)
class Settings:
    db_path: Path
    proxy: str | None
    req_delay: Delay
    timeout: float
    max_limit: int

    @classmethod
    def from_env(cls) -> Settings:
        file = load_file()

        def get(env_key: str, file_key: str) -> Any:
            v = os.getenv(env_key)
            return v if v not in (None, "") else file.get(file_key)

        def number(env_key: str, file_key: str, default: float) -> float:
            v = get(env_key, file_key)
            if v is None:
                return default
            try:
                return float(v)
            except (TypeError, ValueError) as e:
                raise ValueError(f"{env_key} / {file_key} must be a number, got {v!r}") from e

        db = get("XMCP_DB", "db")
        delay = get("XMCP_REQ_DELAY", "req_delay")
        return cls(
            db_path=Path(db).expanduser() if db else default_db_path(),
            proxy=get("XMCP_PROXY", "proxy") or None,
            req_delay=DEFAULT_REQ_DELAY if delay is None else parse_delay(delay),
            timeout=number("XMCP_TIMEOUT", "timeout", 120.0),
            max_limit=int(number("XMCP_MAX_LIMIT", "max_limit", 200)),
        )


def write_file(values: dict[str, Any], path: Path | None = None) -> Path:
    """Write a flat config.toml. Only str / number / bool values are supported."""
    path = path or config_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = ["# xmcp-unofficial settings. Environment variables (XMCP_*) override these."]
    for k, v in values.items():
        if v is None:
            continue
        if isinstance(v, bool):
            lines.append(f"{k} = {'true' if v else 'false'}")
        elif isinstance(v, (int, float)):
            lines.append(f"{k} = {v:g}")
        else:
            s = str(v).replace("\\", "\\\\").replace('"', '\\"')
            lines.append(f'{k} = "{s}"')
    path.write_text("\n".join(lines) + "\n")
    # may contain a proxy password
    path.chmod(0o600)
    return path
