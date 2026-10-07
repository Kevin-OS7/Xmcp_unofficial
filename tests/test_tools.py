import json

import pytest
from mcp import Client

from xmcp_unofficial import server
from xmcp_unofficial.scraper import ScrapeError, parse_tweet_id, parse_username

DETAIL_ID = "1649191520250245121"


def test_parse_refs():
    assert parse_tweet_id("123") == 123
    assert parse_tweet_id("https://x.com/a/status/456?s=20") == 456
    assert parse_tweet_id("https://twitter.com/a/statuses/789") == 789
    with pytest.raises(ScrapeError):
        parse_tweet_id("hello")
    assert parse_username("@jack") == "jack"
    assert parse_username("https://x.com/jack/with_replies") == "jack"
    assert parse_username("12345") == "12345"


async def test_search_respects_limit_and_mode(scraper):
    res = await scraper.search_tweets("python", 3, "top")
    assert res["count"] == 3
    t = res["items"][0]
    assert {"id", "url", "date", "author", "text", "likes"} <= t.keys()
    json.dumps(res)  # must be JSON-serializable
    name, args, kwargs = scraper.api.calls[-1]
    assert name == "search" and kwargs["kv"] == {"product": "Top"}


async def test_limit_capped_by_max_limit(scraper):
    await scraper.followers("XDevelopers", 10_000)
    _, _, kwargs = scraper.api.calls[-1]
    assert kwargs["limit"] == scraper.settings.max_limit


async def test_user_tweets_resolves_username(scraper):
    res = await scraper.user_tweets("@XDevelopers", 5, include_replies=True)
    assert res["count"] == 5
    assert scraper.api.calls[0][0] == "user_by_login"
    assert scraper.api.calls[1][0] == "user_tweets_and_replies"
    assert scraper.api.calls[1][1] == (2244994945,)


async def test_unknown_user_explains_missing_accounts(scraper):
    with pytest.raises(ScrapeError, match="No active scraping accounts"):
        await scraper.get_user("nobody_here")


async def test_get_tweet_from_url(scraper):
    res = await scraper.get_tweet(f"https://x.com/XDevelopers/status/{DETAIL_ID}")
    assert res["id"] == DETAIL_ID
    json.dumps(res)


async def test_timeout_returns_partial(scraper):
    import asyncio

    raw = [t async for t in scraper.api.search("x", limit=1)]
    scraper.settings = scraper.settings.__class__(**{**scraper.settings.__dict__, "timeout": 0.2})

    async def slow_gen(*args, **kwargs):
        yield raw[0]
        await asyncio.sleep(10)

    scraper.api.search = slow_gen
    res = await scraper.search_tweets("x", 5, "latest")
    assert res["count"] == 1
    assert "partial" in res["note"]


async def test_mcp_roundtrip(scraper):
    async with Client(server.mcp) as client:
        tools = {t.name for t in (await client.list_tools()).tools}
        assert {"search_tweets", "get_user", "get_tweet", "get_trends", "account_status"} <= tools

        res = await client.call_tool("get_user", {"user": "XDevelopers"})
        assert not res.is_error
        assert res.structured_content["username"] == "XDevelopers"

        res = await client.call_tool("search_tweets", {"query": "q", "limit": 2})
        assert res.structured_content["count"] == 2

        res = await client.call_tool("get_user", {"user": "ghost"})
        assert res.is_error

        res = await client.call_tool("get_trends", {"limit": 3})
        assert not res.is_error and res.structured_content["count"] <= 3

        res = await client.call_tool("account_status", {})
        assert res.structured_content["stats"]["total"] == 0


async def test_empty_result_surfaces_scraper_warnings(scraper):
    from xmcp_unofficial._vendor.twscrape.logger import logger

    await scraper.pool.add_account("reader", "", "", "", cookies="auth_token=a; ct0=b")

    async def failing(*args, **kwargs):
        logger.warning("XClIdGen creation attempt 1/3 failed: ConnectError")
        return
        yield

    async def none_user(*args, **kwargs):
        logger.warning("Session expired or banned")
        return None

    scraper.api.search = failing
    res = await scraper.search_tweets("x", 5, "latest")
    assert res["count"] == 0
    assert res["warnings"] == ["XClIdGen creation attempt 1/3 failed: ConnectError"]

    scraper.api.user_by_login = none_user
    with pytest.raises(ScrapeError, match="Session expired or banned"):
        await scraper.get_user("someone")
