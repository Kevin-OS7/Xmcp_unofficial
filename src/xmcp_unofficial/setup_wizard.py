"""Interactive `xmcp-unofficial setup`: register accounts, proxies and request pacing."""

from __future__ import annotations

import getpass
import json
from collections.abc import Callable
from typing import Any

import httpx

from . import config
from ._vendor.twscrape.utils import parse_cookies

Ask = Callable[[str], str]


def _normalize_cookies(raw: str) -> dict[str, str] | None:
    raw = raw.strip()
    if not raw:
        return None
    if not raw.startswith(("{", "[")):
        # tolerate "a=1;b=2" and stray spaces, which twscrape's parser does not
        raw = "; ".join(p.strip() for p in raw.split(";") if p.strip())
    try:
        return parse_cookies(raw)
    except ValueError:
        # the parser's message echoes the raw cookie; never print it
        return None


def check_proxy(proxy: str | None, timeout: float = 15) -> str | None:
    """Return None if x.com is reachable through `proxy`, else a short reason."""
    try:
        with httpx.Client(proxy=proxy, timeout=timeout) as c:
            c.get("https://x.com/")
        return None
    except httpx.HTTPError as e:
        return f"{type(e).__name__}: {e}".split("\n")[0][:200]


def _yes(ask: Ask, q: str, default: bool) -> bool:
    hint = "Y/n" if default else "y/N"
    a = ask(f"{q} [{hint}]: ").strip().lower()
    return default if not a else a in ("y", "yes")


async def run_setup(ask: Ask = input, secret: Ask = getpass.getpass) -> int:
    from .scraper import Scraper

    file = config.load_file()
    settings = config.Settings.from_env()
    scraper = Scraper(settings)
    pool = scraper.pool

    print(f"Config file : {config.config_path()}")
    print(f"Account DB  : {settings.db_path}\n")

    existing = await pool.accounts_info()
    if existing:
        print("Registered accounts:")
        for a in existing:
            state = "active" if a["active"] else f"inactive ({a['error_msg']})"
            print(f"  - {a['username']}: {state}")
        print()

    # --- accounts ---------------------------------------------------------------------
    print("Use throwaway accounts only. Scraping can get them locked or suspended.\n")
    while _yes(ask, "Add a scraping account?", default=not existing):
        username = ask("  X username (without @): ").strip().lstrip("@")
        if not username:
            continue
        print("  Paste cookies from x.com (DevTools > Application > Cookies).")
        print("  Either 'auth_token=...; ct0=...' or a JSON export. Input is hidden.")
        cookies = _normalize_cookies(secret("  cookies: "))
        if cookies is None:
            print("  ! Could not parse the cookies. Try again.\n")
            continue
        missing = {"auth_token", "ct0"} - cookies.keys()
        if missing:
            print(f"  ! Missing {sorted(missing)}. Try again.\n")
            continue

        proxy = ask("  Proxy for this account (http://user:pass@host:port, Enter for none): ")
        proxy = proxy.strip() or None
        if proxy:
            print("  Checking proxy...", end=" ", flush=True)
            if err := check_proxy(proxy):
                print(f"failed\n  ! {err}")
                if not _yes(ask, "  Save it anyway?", default=False):
                    continue
            else:
                print("ok")

        if any(a["username"] == username for a in existing):
            await pool.delete_accounts(username)
        await pool.add_account(username, "", "", "", cookies=json.dumps(cookies), proxy=proxy)
        existing = await pool.accounts_info()
        print(f"  Saved {username}.\n")

    # --- pacing -----------------------------------------------------------------------
    current = config.format_delay(settings.req_delay)
    print("\nDelay between paginated requests, in seconds.")
    print("  e.g. 1.5 (fixed), 1-3 (random in range), 0 (none; not recommended)")
    while True:
        raw = ask(f"  Request delay [{current}]: ").strip() or current
        try:
            delay = config.parse_delay(raw)
            break
        except ValueError as e:
            print(f"  ! {e}")

    values: dict[str, Any] = {**file, "req_delay": config.format_delay(delay)}
    path = config.write_file(values)
    print(f"\nSaved settings to {path}")

    # --- verify -----------------------------------------------------------------------
    if existing and _yes(ask, "\nFetch one profile to verify the setup?", default=True):
        from .scraper import ScrapeError

        try:
            user = await Scraper(config.Settings.from_env()).get_user("X")
            print(f"  ok: @{user['username']} has {user['followers']:,} followers")
        except ScrapeError as e:
            print(f"  ! {e}")

    print(
        "\nConnect it to your MCP client:\n"
        "  Claude Code : claude mcp add x-scraper -- xmcp-unofficial\n"
        '  JSON config : {"mcpServers": {"x-scraper": {"command": "xmcp-unofficial"}}}\n'
        "Settings above are picked up automatically; XMCP_* env vars override them."
    )
    return 0
