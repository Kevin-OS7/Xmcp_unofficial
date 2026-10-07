"""MCP server exposing read-only X (Twitter) scraping tools."""

from __future__ import annotations

from functools import cache
from typing import Annotated, Any

from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.exceptions import ToolError
from mcp.types import ToolAnnotations
from pydantic import Field

from .config import Settings
from .scraper import ScrapeError, Scraper, SearchMode

INSTRUCTIONS = """\
Read-only access to public X (Twitter) data via X's internal web API, using a pool of
logged-in scraping accounts. Users can be given as `username`, `@username`, a numeric id,
or a profile URL; tweets as a numeric id or a status URL. List-returning tools return
{"count", "items", "note"?}; a "note" means the result is partial or explains why it's empty.
Search queries accept X's advanced search operators, e.g. `from:user`, `since:2026-01-01`,
`min_faves:100`, `lang:ja`, `filter:media`, `-filter:replies`.
"""

mcp = MCPServer("xmcp-unofficial", instructions=INSTRUCTIONS)

READ_ONLY = ToolAnnotations(readOnlyHint=True, openWorldHint=True)

User = Annotated[str, Field(description="username, @username, numeric user id, or profile URL")]
TweetRef = Annotated[str, Field(description="Tweet id or tweet URL")]


def Limit(default: int) -> Any:  # noqa: N802 - reads like a type in signatures
    return Field(default=default, ge=1, description="Max number of results")


@cache
def _scraper() -> Scraper:
    return Scraper(Settings.from_env())


async def _call(coro) -> Any:
    try:
        return await coro
    except ScrapeError as e:
        raise ToolError(str(e)) from e


@mcp.tool(annotations=READ_ONLY)
async def search_tweets(
    query: Annotated[str, Field(description="Search query; X advanced search operators allowed")],
    limit: int = Limit(20),
    mode: Annotated[SearchMode, Field(description="latest | top | media")] = "latest",
) -> dict[str, Any]:
    """Search tweets."""
    return await _call(_scraper().search_tweets(query, limit, mode))


@mcp.tool(annotations=READ_ONLY)
async def search_users(
    query: Annotated[str, Field(description="Search query")],
    limit: int = Limit(20),
) -> dict[str, Any]:
    """Search user accounts."""
    return await _call(_scraper().search_users(query, limit))


@mcp.tool(annotations=READ_ONLY)
async def get_user(user: User) -> dict[str, Any]:
    """Get a user's profile (bio, follower counts, creation date, pinned tweets...)."""
    return await _call(_scraper().get_user(user))


@mcp.tool(annotations=READ_ONLY)
async def get_user_tweets(
    user: User,
    limit: int = Limit(20),
    include_replies: Annotated[bool, Field(description="Include the user's replies")] = False,
) -> dict[str, Any]:
    """Get a user's recent tweets (timeline order; pinned tweet may come first)."""
    return await _call(_scraper().user_tweets(user, limit, include_replies))


@mcp.tool(annotations=READ_ONLY)
async def get_user_media(user: User, limit: int = Limit(20)) -> dict[str, Any]:
    """Get a user's tweets that contain photos or videos."""
    return await _call(_scraper().user_media(user, limit))


@mcp.tool(annotations=READ_ONLY)
async def get_tweet(tweet: TweetRef) -> dict[str, Any]:
    """Get a single tweet with its metrics, media and quoted tweet."""
    return await _call(_scraper().get_tweet(tweet))


@mcp.tool(annotations=READ_ONLY)
async def get_tweet_replies(tweet: TweetRef, limit: int = Limit(20)) -> dict[str, Any]:
    """Get replies to a tweet."""
    return await _call(_scraper().tweet_replies(tweet, limit))


@mcp.tool(annotations=READ_ONLY)
async def get_retweeters(tweet: TweetRef, limit: int = Limit(50)) -> dict[str, Any]:
    """Get users who retweeted a tweet."""
    return await _call(_scraper().retweeters(tweet, limit))


@mcp.tool(annotations=READ_ONLY)
async def get_followers(user: User, limit: int = Limit(50)) -> dict[str, Any]:
    """Get a user's followers."""
    return await _call(_scraper().followers(user, limit))


@mcp.tool(annotations=READ_ONLY)
async def get_following(user: User, limit: int = Limit(50)) -> dict[str, Any]:
    """Get accounts a user follows."""
    return await _call(_scraper().following(user, limit))


@mcp.tool(annotations=READ_ONLY)
async def get_list_tweets(
    list_id: Annotated[str, Field(description="List id or list URL")],
    limit: int = Limit(20),
) -> dict[str, Any]:
    """Get the latest tweets from an X List."""
    return await _call(_scraper().list_tweets(list_id, limit))


@mcp.tool(annotations=READ_ONLY)
async def get_trends(limit: int = Limit(20)) -> dict[str, Any]:
    """Get currently trending topics (as seen by the scraping account's region)."""
    return await _call(_scraper().trends(limit))


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=True, openWorldHint=False))
async def account_status() -> dict[str, Any]:
    """Show the scraping account pool: which accounts are active, rate-limit locks, errors.

    Use this when other tools return empty results or time out.
    """
    return await _call(_scraper().account_status())


def run() -> None:
    mcp.run("stdio")
