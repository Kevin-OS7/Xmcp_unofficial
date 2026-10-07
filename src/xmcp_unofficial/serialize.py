"""Convert scraper models into compact, JSON-safe dicts for LLM consumption.

The full twscrape models carry a lot of fields an LLM rarely needs (snscrape
compatibility fields, duplicated id/id_str, banner URLs ...). Tools return these
compact shapes by default to keep responses small.
"""

from __future__ import annotations

from typing import Any

from ._vendor.twscrape.models import Media, Trend, Tweet, User


def user_brief(u: User) -> dict[str, Any]:
    return {
        "id": u.id_str,
        "username": u.username,
        "displayname": u.displayname,
        "followers": u.followersCount,
        "verified": bool(u.verified or u.blue),
    }


def user_full(u: User) -> dict[str, Any]:
    return {
        "id": u.id_str,
        "username": u.username,
        "displayname": u.displayname,
        "url": u.url,
        "description": u.rawDescription,
        "location": u.location,
        "created": u.created.isoformat(),
        "followers": u.followersCount,
        "following": u.friendsCount,
        "tweets": u.statusesCount,
        "likes": u.favouritesCount,
        "media": u.mediaCount,
        "listed": u.listedCount,
        "protected": u.protected,
        "verified": u.verified,
        "blue": u.blue,
        "blue_type": u.blueType,
        "profile_image": u.profileImageUrl,
        "banner": u.profileBannerUrl,
        "links": [x.url for x in u.descriptionLinks],
        "pinned_tweet_ids": [str(x) for x in u.pinnedIds],
    }


def _media(m: Media) -> dict[str, Any] | None:
    out: dict[str, Any] = {}
    if m.photos:
        out["photos"] = [p.url for p in m.photos]
    if m.videos:
        videos = []
        for v in m.videos:
            mp4 = [x for x in v.variants if x.contentType == "video/mp4"]
            best = max(mp4, key=lambda x: x.bitrate) if mp4 else None
            videos.append(
                {
                    "thumbnail": v.thumbnailUrl,
                    "url": best.url if best else None,
                    "duration_ms": v.duration,
                    "views": v.views,
                }
            )
        out["videos"] = videos
    if m.animated:
        out["gifs"] = [a.videoUrl for a in m.animated]
    return out or None


def tweet(t: Tweet, depth: int = 0) -> dict[str, Any]:
    out: dict[str, Any] = {
        "id": t.id_str,
        "url": t.url,
        "date": t.date.isoformat(),
        "author": user_brief(t.user),
        "text": t.rawContent,
        "lang": t.lang,
        "replies": t.replyCount,
        "retweets": t.retweetCount,
        "likes": t.likeCount,
        "quotes": t.quoteCount,
        "bookmarks": t.bookmarkedCount,
        "views": t.viewCount,
        "conversation_id": t.conversationIdStr,
    }
    if t.inReplyToTweetIdStr:
        out["in_reply_to"] = t.inReplyToTweetIdStr
        if t.inReplyToUser:
            out["in_reply_to_user"] = t.inReplyToUser.username
    if t.hashtags:
        out["hashtags"] = t.hashtags
    if t.links:
        out["links"] = [x.url for x in t.links]
    if media := _media(t.media):
        out["media"] = media
    if t.possibly_sensitive:
        out["sensitive"] = True
    # Nested tweets are kept one level deep so a quote-of-a-quote doesn't balloon the output.
    if depth == 0:
        if t.quotedTweet:
            out["quoted"] = tweet(t.quotedTweet, depth + 1)
        if t.retweetedTweet:
            out["retweeted"] = tweet(t.retweetedTweet, depth + 1)
    return out


def trend(t: Trend) -> dict[str, Any]:
    return {
        "name": t.name,
        "rank": t.rank,
        "context": t.trend_metadata.domain_context or None,
        "description": t.trend_metadata.meta_description or None,
        "social_context": t.social_context,
        "related": [g.name for g in t.grouped_trends],
    }
