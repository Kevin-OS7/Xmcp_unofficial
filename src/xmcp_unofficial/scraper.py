"""Thin async layer over the vendored twscrape API used by the MCP tools."""

from __future__ import annotations

import asyncio
import contextvars
import re
from collections.abc import AsyncIterator, Callable
from contextlib import aclosing, contextmanager
from typing import Any, Literal, TypeVar

from . import serialize
from ._vendor.twscrape import API, AccountsPool
from ._vendor.twscrape.logger import logger
from .config import Settings

T = TypeVar("T")

SearchMode = Literal["latest", "top", "media"]
_PRODUCT = {"latest": "Latest", "top": "Top", "media": "Media"}

_TWEET_URL = re.compile(r"(?:x|twitter)\.com/[^/]+/status(?:es)?/(\d+)")
_USER_URL = re.compile(r"(?:x|twitter)\.com/([A-Za-z0-9_]{1,15})")

# twscrape swallows most request failures (dead proxy, banned account, X-side errors) and
# just yields nothing, logging a warning. Warnings logged while a tool call runs are
# collected here so an empty result can say *why* it is empty.
_warnings: contextvars.ContextVar[list[str] | None] = contextvars.ContextVar(
    "xmcp_warnings", default=None
)


def _warning_sink(message) -> None:
    if (bucket := _warnings.get()) is not None and len(bucket) < 20:
        bucket.append(message.record["message"])


logger.add(_warning_sink, level="WARNING", format="{message}")


class ScrapeError(Exception):
    pass


def parse_tweet_id(value: str | int) -> int:
    s = str(value).strip()
    if s.isdigit():
        return int(s)
    if m := _TWEET_URL.search(s):
        return int(m.group(1))
    raise ScrapeError(f"Not a tweet id or tweet URL: {value!r}")


def parse_username(value: str) -> str:
    s = value.strip()
    if m := _USER_URL.search(s):
        return m.group(1)
    return s.lstrip("@")


@contextmanager
def capture_warnings():
    bucket: list[str] = []
    token = _warnings.set(bucket)
    try:
        yield bucket
    finally:
        _warnings.reset(token)


def _dedupe(msgs: list[str], n: int = 5) -> list[str]:
    return list(dict.fromkeys(msgs))[:n]


class Scraper:
    def __init__(self, settings: Settings):
        self.settings = settings
        settings.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.pool = AccountsPool(str(settings.db_path))
        self.api = API(self.pool, proxy=settings.proxy, req_delay=settings.req_delay)

    def _limit(self, limit: int) -> int:
        if limit < 1:
            raise ScrapeError("limit must be >= 1")
        return min(limit, self.settings.max_limit)

    async def _collect(
        self, gen: AsyncIterator[T], limit: int, fn: Callable[[T], dict[str, Any]]
    ) -> dict[str, Any]:
        """Drain `gen` up to `limit` items, stopping early on timeout or error.

        Rate-limited accounts make twscrape wait for the lock to expire, which can take
        ~15 minutes. Returning partial results with a note is more useful to an agent than
        blocking the tool call that long.
        """
        items: list[dict[str, Any]] = []

        async def run():
            async with aclosing(gen) as g:  # type: ignore[type-var]
                async for x in g:
                    items.append(fn(x))
                    if len(items) >= limit:
                        break

        out: dict[str, Any] = {}
        with capture_warnings() as warnings:
            try:
                await asyncio.wait_for(run(), timeout=self.settings.timeout)
            except asyncio.TimeoutError:
                out["note"] = (
                    f"Stopped after {self.settings.timeout:.0f}s (accounts may be "
                    "rate-limited); results are partial."
                )
            except Exception as e:
                if not items:
                    raise ScrapeError(self._failure(f"{type(e).__name__}: {e}", warnings)) from e
                out["note"] = f"Stopped early by {type(e).__name__}: {e}; results are partial."

        out["count"] = len(items)
        out["items"] = items
        if not items and "note" not in out:
            if note := await self._why_empty(warnings):
                out["note"] = note
        if warnings and not items:
            out["warnings"] = _dedupe(warnings)
        return out

    async def _why_empty(self, warnings: list[str]) -> str | None:
        stats = await self.pool.stats()
        if not stats.get("active"):
            return (
                "No active scraping accounts. Add one with "
                "`xmcp-unofficial accounts add <username> --cookies '<cookies>'`, "
                "or check `account_status` for banned/expired accounts."
            )
        if warnings:
            return (
                "The scraper hit errors (commonly a dead proxy, expired cookies or a "
                "banned account)."
            )
        return None

    def _failure(self, msg: str, warnings: list[str]) -> str:
        if warnings:
            msg += " | scraper warnings: " + " / ".join(_dedupe(warnings, 3))
        return msg

    async def _one(self, coro, not_found: str) -> Any:
        """Await a single-item lookup; raise ScrapeError with the likely cause on miss."""
        with capture_warnings() as warnings:
            try:
                res = await asyncio.wait_for(coro, timeout=self.settings.timeout)
            except asyncio.TimeoutError as e:
                raise ScrapeError(
                    f"Timed out after {self.settings.timeout:.0f}s (accounts may be rate-limited)."
                ) from e
            except Exception as e:
                raise ScrapeError(self._failure(f"{type(e).__name__}: {e}", warnings)) from e
        if res is None:
            reason = await self._why_empty(warnings)
            raise ScrapeError(self._failure(reason, warnings) if reason else not_found)
        return res

    async def _uid(self, username: str) -> int:
        name = parse_username(username)
        if name.isdigit():
            return int(name)
        user = await self._one(self.api.user_by_login(name), f"User @{name} not found")
        return user.id

    # --- tools -------------------------------------------------------------

    async def search_tweets(self, query: str, limit: int, mode: SearchMode):
        limit = self._limit(limit)
        kv = {"product": _PRODUCT[mode]}
        return await self._collect(
            self.api.search(query, limit=limit, kv=kv), limit, serialize.tweet
        )

    async def search_users(self, query: str, limit: int):
        limit = self._limit(limit)
        return await self._collect(
            self.api.search_user(query, limit=limit), limit, serialize.user_full
        )

    async def get_user(self, username: str):
        name = parse_username(username)
        not_found = f"User {username!r} not found"
        if name.isdigit():
            user = await self._one(self.api.user_by_id(int(name)), not_found)
        else:
            user = await self._one(self.api.user_by_login(name), not_found)
        return serialize.user_full(user)

    async def user_tweets(self, username: str, limit: int, include_replies: bool):
        limit = self._limit(limit)
        uid = await self._uid(username)
        fn = self.api.user_tweets_and_replies if include_replies else self.api.user_tweets
        return await self._collect(fn(uid, limit=limit), limit, serialize.tweet)

    async def user_media(self, username: str, limit: int):
        limit = self._limit(limit)
        uid = await self._uid(username)
        return await self._collect(self.api.user_media(uid, limit=limit), limit, serialize.tweet)

    async def get_tweet(self, tweet: str):
        twid = parse_tweet_id(tweet)
        doc = await self._one(
            self.api.tweet_details(twid), f"Tweet {twid} not found (deleted or protected?)"
        )
        return serialize.tweet(doc)

    async def tweet_replies(self, tweet: str, limit: int):
        limit = self._limit(limit)
        twid = parse_tweet_id(tweet)
        return await self._collect(
            self.api.tweet_replies(twid, limit=limit), limit, serialize.tweet
        )

    async def retweeters(self, tweet: str, limit: int):
        limit = self._limit(limit)
        twid = parse_tweet_id(tweet)
        return await self._collect(
            self.api.retweeters(twid, limit=limit), limit, serialize.user_full
        )

    async def followers(self, username: str, limit: int):
        limit = self._limit(limit)
        uid = await self._uid(username)
        return await self._collect(
            self.api.followers(uid, limit=limit), limit, serialize.user_full
        )

    async def following(self, username: str, limit: int):
        limit = self._limit(limit)
        uid = await self._uid(username)
        return await self._collect(
            self.api.following(uid, limit=limit), limit, serialize.user_full
        )

    async def list_tweets(self, list_id: str, limit: int):
        limit = self._limit(limit)
        m = re.search(r"(\d+)", str(list_id))
        if not m:
            raise ScrapeError(f"Not a list id or list URL: {list_id!r}")
        return await self._collect(
            self.api.list_timeline(int(m.group(1)), limit=limit), limit, serialize.tweet
        )

    async def trends(self, limit: int):
        limit = self._limit(limit)
        return await self._collect(
            self.api.trends("trending", limit=limit), limit, serialize.trend
        )

    async def account_status(self):
        stats = await self.pool.stats()
        accounts = await self.pool.accounts_info()
        return {
            "db": str(self.settings.db_path),
            "stats": stats,
            "accounts": [
                {
                    "username": a["username"],
                    "active": a["active"],
                    "logged_in": a["logged_in"],
                    "last_used": a["last_used"].isoformat() if a["last_used"] else None,
                    "total_requests": a["total_req"],
                    "error": a["error_msg"] if a["error_msg"] != "None" else None,
                }
                for a in accounts
            ],
        }
