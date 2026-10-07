import json
from pathlib import Path

import httpx
import pytest

from xmcp_unofficial import server
from xmcp_unofficial._vendor.twscrape.models import (
    parse_trends,
    parse_tweet,
    parse_tweets,
    parse_user,
    parse_users,
)
from xmcp_unofficial.config import Settings
from xmcp_unofficial.scraper import Scraper

FIXTURES = Path(__file__).parent / "fixtures"


def load(name: str) -> dict:
    return json.loads((FIXTURES / f"{name}.json").read_text())


def _gen(items):
    async def gen(*args, **kwargs):
        limit = kwargs.get("limit", -1)
        for i, x in enumerate(items):
            if limit > 0 and i >= limit:
                return
            yield x

    return gen


class FakeAPI:
    """Stands in for the vendored twscrape API, serving parsed fixture data."""

    def __init__(self):
        self.calls: list[tuple[str, tuple, dict]] = []
        tweets = list(parse_tweets(load("raw_search")))
        user_tweets = list(parse_tweets(load("raw_user_tweets")))
        users = list(parse_users(load("raw_followers")))
        user = parse_user(load("raw_user_by_login"))
        detail_raw = load("raw_tweet_details")
        self._detail_raw = detail_raw
        self._user = user
        trends_rep = httpx.Response(200, json=load("raw_trends"))

        self.search = self._rec("search", _gen(tweets))
        self.search_user = self._rec("search_user", _gen(users))
        self.user_tweets = self._rec("user_tweets", _gen(user_tweets))
        self.user_tweets_and_replies = self._rec("user_tweets_and_replies", _gen(user_tweets))
        self.user_media = self._rec("user_media", _gen(user_tweets))
        self.tweet_replies = self._rec("tweet_replies", _gen(tweets))
        self.retweeters = self._rec("retweeters", _gen(users))
        self.followers = self._rec("followers", _gen(users))
        self.following = self._rec("following", _gen(users))
        self.list_timeline = self._rec("list_timeline", _gen(tweets))
        self.trends = self._rec("trends", _gen(list(parse_trends(trends_rep))))

    def _rec(self, name, fn):
        def wrapper(*args, **kwargs):
            self.calls.append((name, args, kwargs))
            return fn(*args, **kwargs)

        return wrapper

    async def user_by_login(self, login, kv=None):
        self.calls.append(("user_by_login", (login,), {}))
        return self._user if login.lower() == self._user.username.lower() else None

    async def user_by_id(self, uid, kv=None):
        self.calls.append(("user_by_id", (uid,), {}))
        return self._user if uid == self._user.id else None

    async def tweet_details(self, twid, kv=None):
        self.calls.append(("tweet_details", (twid,), {}))
        return parse_tweet(self._detail_raw, twid)


@pytest.fixture
def scraper(tmp_path, monkeypatch):
    settings = Settings(
        db_path=tmp_path / "accounts.db", proxy=None, req_delay=None, timeout=5, max_limit=50
    )
    s = Scraper(settings)
    s.api = FakeAPI()  # type: ignore[assignment]
    monkeypatch.setattr(server, "_scraper", lambda: s)
    return s
