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
uv tool install git+https://github.com/Kevin-OS7/Xmcp_unofficial
```

or from a clone: `uv sync && uv run xmcp-unofficial --help`.

## Setup

Run the interactive setup once. It registers throwaway accounts (cookies are entered
hidden), checks each proxy can reach x.com, sets the request delay, and verifies the
result with a real request:

```bash
xmcp-unofficial setup
```

To get cookies: log in to x.com with a **dedicated** account, open DevTools →
Application → Cookies → `https://x.com`, and copy `auth_token` and `ct0`
(`auth_token=...; ct0=...`, or a JSON cookie export).

Already have accounts in a [twscrape](https://github.com/vladkens/twscrape) database?
Import them:

```bash
xmcp-unofficial accounts import /path/to/twscrape/accounts.db
```

Non-interactive account commands:

```bash
xmcp-unofficial accounts add my_reader --cookies "auth_token=xxxx; ct0=yyyy" --proxy http://user:pass@host:port
xmcp-unofficial accounts set-proxy my_reader http://user:pass@host:port   # or "none"
xmcp-unofficial accounts list      # status of all accounts
xmcp-unofficial accounts check     # fetch a profile to confirm it works
xmcp-unofficial accounts remove my_reader
```

Multiple accounts are rotated automatically; a rate-limited account is skipped until
its limit resets. Accounts are stored in `~/.xmcp_unofficial/accounts.db`.

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
      "command": "xmcp-unofficial"
    }
  }
}
```

Without installing: `"command": "uvx", "args": ["--from", "git+https://github.com/Kevin-OS7/Xmcp_unofficial", "xmcp-unofficial"]`.

## Configuration

Settings are read from `~/.xmcp_unofficial/config.toml` (written by `setup`), so every
MCP client shares them. An `XMCP_*` environment variable, e.g. in a client's `env`
block, overrides the file.

```toml
req_delay = "1.5"      # seconds between paginated requests: 1.5 fixed, "1-3" random, 0 none
timeout = 120
max_limit = 200
# proxy = "http://user:pass@host:port"   # applies to every account
# db = "~/.xmcp_unofficial/accounts.db"
```

| config.toml | Env var | Default | Meaning |
| --- | --- | --- | --- |
| `db` | `XMCP_DB` | `~/.xmcp_unofficial/accounts.db` | Account database |
| `proxy` | `XMCP_PROXY` | – | Proxy for all requests (overrides per-account proxies) |
| `req_delay` | `XMCP_REQ_DELAY` | `1.5` | Delay between paginated requests |
| `timeout` | `XMCP_TIMEOUT` | `120` | Max seconds per tool call; partial results are returned on timeout |
| `max_limit` | `XMCP_MAX_LIMIT` | `200` | Upper bound for any `limit` argument |
| – | `XMCP_CONFIG` | `~/.xmcp_unofficial/config.toml` | Config file location |
| – | `TWS_LOG_LEVEL` | `INFO` | Log level (logs go to stderr) |

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
