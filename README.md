# Xmcp_unofficial

An **unofficial** [MCP](https://modelcontextprotocol.io) server that lets AI agents
(Claude Code, Claude Desktop, Cursor, ...) read public X (Twitter) data — search,
profiles, timelines, replies, followers, trends — without the paid official API.

日本語: [README.ja.md](README.ja.md)

> [!WARNING]
> This uses X's internal web GraphQL API with logged-in accounts. That is against
> X's Terms of Service, and the accounts you use **can be locked or suspended**.
> Use throwaway accounts, never your main account, and keep request volumes low.
> X changes its internal API without notice; things will break from time to time.
> This project is not affiliated with X Corp.

## Tools

All tools are read-only.

| Tool | What it does |
| --- | --- |
| `search_tweets(query, limit=20, mode="latest")` | Search tweets. `mode`: `latest` / `top` / `media`. Supports advanced operators (`from:`, `since:`, `min_faves:`, `lang:`, `-filter:replies`, ...) |
| `search_users(query, limit=20)` | Search accounts |
| `get_user(user)` | Profile: bio, counts, created date, pinned tweet ids |
| `get_user_tweets(user, limit=20, include_replies=false)` | A user's timeline |
| `get_user_media(user, limit=20)` | A user's photo/video tweets |
| `get_tweet(tweet)` | One tweet with metrics, media, quoted tweet |
| `get_tweet_replies(tweet, limit=20)` | Replies to a tweet |
| `get_retweeters(tweet, limit=50)` | Users who retweeted |
| `get_followers(user, limit=50)` / `get_following(user, limit=50)` | Follower / following lists |
| `get_list_tweets(list_id, limit=20)` | Latest tweets of an X List |
| `get_trends(limit=20)` | Trending topics |
| `account_status()` | Scraping-account pool health (active, rate-limited, errors) |

`user` accepts `jack`, `@jack`, a numeric id, or `https://x.com/jack`.
`tweet` accepts an id or a status URL. List tools return
`{"count", "items", "note"?, "warnings"?}` — `note` explains partial or empty results.

## Install

Requires Python 3.10+ and [uv](https://docs.astral.sh/uv/).

```bash
uv tool install git+https://github.com/peaceplayer0722/Xmcp_unofficial
```

or from a clone: `uv sync && uv run xmcp-unofficial --help`.

## Add a scraping account

The server needs at least one logged-in X account. Cookie login is the reliable way:

1. Log in to x.com in a browser with a **dedicated** account.
2. Open DevTools → Application → Cookies → `https://x.com`, copy `auth_token` and `ct0`.
3. Register it:

```bash
xmcp-unofficial accounts add my_reader --cookies "auth_token=xxxx; ct0=yyyy"
# optional per-account proxy
xmcp-unofficial accounts add my_reader2 --cookies-file cookies.txt --proxy http://user:pass@host:port

xmcp-unofficial accounts list      # status of all accounts
xmcp-unofficial accounts check     # fetch a profile to confirm it works
```

`--cookies` also accepts a JSON cookie export (e.g. from a browser extension).
Multiple accounts are rotated automatically; a rate-limited account is skipped until
its limit resets.

Accounts live in a SQLite file, `~/.xmcp_unofficial/accounts.db` by default
(`XMCP_DB` to change). The file is the same format as
[twscrape](https://github.com/vladkens/twscrape)'s `accounts.db`, so you can point
`XMCP_DB` at an existing twscrape database.

## Connect to an MCP client

**Claude Code**

```bash
claude mcp add x-scraper -- xmcp-unofficial
```

**Claude Desktop / Cursor / others** (`mcpServers` JSON):

```json
{
  "mcpServers": {
    "x-scraper": {
      "command": "xmcp-unofficial",
      "env": { "XMCP_REQ_DELAY": "1-3" }
    }
  }
}
```

Without installing: `"command": "uvx", "args": ["--from", "git+https://github.com/peaceplayer0722/Xmcp_unofficial", "xmcp-unofficial"]`.

## Configuration

| Env var | Default | Meaning |
| --- | --- | --- |
| `XMCP_DB` | `~/.xmcp_unofficial/accounts.db` | Account database |
| `XMCP_PROXY` | – | Proxy for all requests (overrides per-account proxies) |
| `XMCP_REQ_DELAY` | – | Delay between paginated requests: `2` (fixed) or `1-3` (random range, seconds) |
| `XMCP_TIMEOUT` | `120` | Max seconds per tool call; partial results are returned on timeout |
| `XMCP_MAX_LIMIT` | `200` | Upper bound for any `limit` argument |
| `TWS_LOG_LEVEL` | `INFO` | Log level (logs go to stderr) |

## Troubleshooting

- **Empty results with `warnings` mentioning `ConnectError`** — the account's proxy is
  unreachable. Fix it with `xmcp-unofficial accounts set-proxy <user> <url>`
  (or `none` to connect directly).
- **"No active scraping accounts"** — add one, or check `accounts list`: accounts whose
  cookies expired or that got banned are marked inactive. Re-add them with fresh cookies.
- **Timeouts / partial results** — all accounts are rate-limited for that endpoint.
  Add accounts or wait ~15 minutes. `accounts reset-locks` clears stale locks.

## Development

```bash
uv sync --extra dev
uv run pytest
uv run ruff check src tests
```

The scraping engine is a vendored copy of twscrape in
`src/xmcp_unofficial/_vendor/twscrape/`. When X changes its GraphQL operation IDs,
update the `OP_*` constants in `api.py` there.

## License & credits

MIT. The scraping engine is derived from
[twscrape](https://github.com/vladkens/twscrape) by vladkens (MIT License);
see [NOTICE](NOTICE) for the full attribution and list of modifications.
