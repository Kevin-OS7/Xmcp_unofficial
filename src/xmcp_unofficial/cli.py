"""Command-line entry point: run the MCP server or manage scraping accounts."""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

from .config import Settings


def _read_cookies(args: argparse.Namespace) -> str:
    if args.cookies_file:
        return Path(args.cookies_file).expanduser().read_text().strip()
    if args.cookies == "-":
        return sys.stdin.read().strip()
    return args.cookies


async def _accounts(args: argparse.Namespace) -> int:
    from .scraper import Scraper

    scraper = Scraper(Settings.from_env())
    pool = scraper.pool

    if args.action == "add":
        cookies = _read_cookies(args)
        from ._vendor.twscrape.utils import parse_cookies

        parsed = parse_cookies(cookies)
        missing = {"auth_token", "ct0"} - parsed.keys()
        if missing:
            print(f"error: cookies are missing {sorted(missing)}", file=sys.stderr)
            return 1
        await pool.add_account(
            args.username,
            password=args.password or "",
            email=args.email or "",
            email_password="",
            cookies=cookies,
            proxy=args.proxy,
        )
        return 0

    if args.action == "list":
        print(json.dumps(await scraper.account_status(), indent=2, ensure_ascii=False))
        return 0

    if args.action == "remove":
        await pool.delete_accounts(args.usernames)
        print(f"removed: {', '.join(args.usernames)}")
        return 0

    if args.action == "set-proxy":
        account = await pool.get(args.username)
        account.proxy = None if args.proxy == "none" else args.proxy
        await pool.save(account)
        print(f"{args.username}: proxy {'cleared' if account.proxy is None else 'updated'}")
        return 0

    if args.action == "reset-locks":
        await pool.reset_locks()
        print("all rate-limit locks cleared")
        return 0

    if args.action == "check":
        res = await scraper.get_user(args.user)
        print(json.dumps(res, indent=2, ensure_ascii=False))
        return 0

    raise AssertionError(args.action)


def main(argv: list[str] | None = None) -> None:
    p = argparse.ArgumentParser(
        prog="xmcp-unofficial",
        description="Unofficial X (Twitter) scraping MCP server. Run without arguments to serve.",
    )
    sub = p.add_subparsers(dest="command")
    sub.add_parser("serve", help="run the MCP server over stdio (default)")

    acc = sub.add_parser("accounts", help="manage scraping accounts")
    asub = acc.add_subparsers(dest="action", required=True)

    add = asub.add_parser("add", help="add an account from browser cookies")
    add.add_argument("username")
    src = add.add_mutually_exclusive_group(required=True)
    src.add_argument(
        "--cookies",
        help="cookie string ('auth_token=...; ct0=...'), JSON, or '-' to read stdin",
    )
    src.add_argument("--cookies-file", help="file containing the cookies")
    add.add_argument("--proxy", help="per-account proxy, e.g. http://user:pass@host:port")
    add.add_argument("--password", help=argparse.SUPPRESS)
    add.add_argument("--email", help=argparse.SUPPRESS)

    asub.add_parser("list", help="show accounts and rate-limit status")
    rm = asub.add_parser("remove", help="remove accounts")
    rm.add_argument("usernames", nargs="+")
    sp = asub.add_parser("set-proxy", help="change or clear ('none') an account's proxy")
    sp.add_argument("username")
    sp.add_argument("proxy", help="proxy URL, or 'none' to connect directly")
    asub.add_parser("reset-locks", help="clear all rate-limit locks")
    chk = asub.add_parser("check", help="fetch a profile to verify the pool works")
    chk.add_argument("user", nargs="?", default="X")

    args = p.parse_args(argv)

    if args.command == "accounts":
        from .scraper import ScrapeError

        try:
            sys.exit(asyncio.run(_accounts(args)))
        except (ScrapeError, ValueError, OSError) as e:
            print(f"error: {e}", file=sys.stderr)
            sys.exit(1)

    from .server import run

    run()
