# Xmcp_unofficial

X（Twitter）の公開データを AI エージェント（Claude Code、Claude Desktop、Cursor など）から読めるようにする**非公式**の [MCP](https://modelcontextprotocol.io) サーバーです。
有料の公式 API を使わずに、検索、プロフィール、タイムライン、リプライ、フォロワー、トレンドを取得できます。

English: [README.md](README.md)

> [!WARNING]
> ログイン済みアカウントで X の内部 Web API（GraphQL）を叩きます。
> これは X の利用規約に反しており、使ったアカウントは**ロックや凍結の対象になり得ます**。
> メインアカウントは使わず、捨てアカウントで、リクエスト量を抑えて使ってください。
> X は内部 API を予告なく変えるため、ときどき壊れます。
> 本プロジェクトは X Corp. とは無関係です。

## 必要なもの

> [!IMPORTANT]
> 本プロジェクトは大規模なスクレイピングを推奨するものではありません。
> 捨てアカウントとプロキシを勧めるのは、AI エージェントから少し読むだけの用途でも**自分の X アカウントを最低限守る**ためです。
> たくさんスクレイピングするためではありません。

**1. 捨ての X アカウント（1 つ以上）**
メインアカウントは絶対に使わないでください。スクレイピングに使ったアカウントはいつロックや凍結されてもおかしくありません。
捨てアカウントは AccsMarket (https://www.accsmarket.com/en/?ref=818187) での購入をお勧めします。

**2. アカウントごとのプロキシ（推奨）**
捨てアカウントを自宅の IP から使うと、そのアカウントと自分が結び付いてしまいます。
固定の住宅用プロキシを使えば、アカウントごとに安定した普通の IP を割り当てられます。
プロキシは Proxy-Cheap (https://app.proxy-cheap.com/r/wCfesT) をお勧めします。
**Static Residential (ISP) IPv4** が月 **3.59 ドル程度**で使えます（2026 年 10 月時点。最新の価格はサイトで確認してください）。

**3. Python 3.10 以上と [uv](https://docs.astral.sh/uv/)**

<sub>上記の AccsMarket と Proxy-Cheap のリンクはアフィリエイトリンクです。利用者の負担は増えず、本プロジェクトの支援になります。</sub>

## ツール

すべて読み取り専用です。

| ツール | 内容 |
| --- | --- |
| `search_tweets(query, limit=20, mode="latest")` | ツイート検索。`mode` は `latest` / `top` / `media`。高度な検索演算子（`from:`、`since:`、`min_faves:`、`lang:`、`-filter:replies` など）が使える |
| `search_users(query, limit=20)` | アカウント検索 |
| `get_user(user)` | プロフィール（自己紹介、各種カウント、作成日、固定ツイート ID） |
| `get_user_tweets(user, limit=20, include_replies=false)` | ユーザーのタイムライン |
| `get_user_media(user, limit=20)` | 画像・動画付きツイート |
| `get_tweet(tweet)` | 単一ツイート（指標、メディア、引用元を含む） |
| `get_tweet_replies(tweet, limit=20)` | リプライ一覧 |
| `get_retweeters(tweet, limit=50)` | リツイートしたユーザー |
| `get_followers(user, limit=50)` / `get_following(user, limit=50)` | フォロワー / フォロー中 |
| `get_list_tweets(list_id, limit=20)` | リストの最新ツイート |
| `get_trends(limit=20)` | トレンド |
| `account_status()` | スクレイピング用アカウントの状態（有効、レート制限、エラー） |

`user` には `jack`、`@jack`、数値 ID、`https://x.com/jack` のいずれも渡せます。
`tweet` には ID かツイート URL を渡せます。
一覧系ツールは `{"count", "items", "note"?, "warnings"?}` を返し、`note` には結果が部分的・空になった理由が入ります。

## インストール

Python 3.10 以上と [uv](https://docs.astral.sh/uv/) が必要です。

```bash
uv tool install git+https://github.com/Kevin-OS7/Xmcp_unofficial
```

クローンして使う場合は `uv sync && uv run xmcp-unofficial --help` です。

## セットアップ

最初に一度、対話形式のセットアップを実行します。
捨てアカウントの登録（Cookie は画面に表示されない形で入力）、プロキシが x.com に届くかの確認、リクエスト間隔の設定、実際に 1 件取得しての動作確認までを順に行います。

```bash
xmcp-unofficial setup
```

Cookie の取り方：**専用の**アカウントでブラウザから x.com にログインし、DevTools → Application → Cookies → `https://x.com` から `auth_token` と `ct0` をコピーします（`auth_token=...; ct0=...` の形か、JSON で書き出したもの）。

[twscrape](https://github.com/vladkens/twscrape) の DB にすでにアカウントがあるなら、取り込めます。

```bash
xmcp-unofficial accounts import /path/to/twscrape/accounts.db
```

対話なしで使うアカウント操作コマンドは次のとおりです。

```bash
xmcp-unofficial accounts add my_reader --cookies "auth_token=xxxx; ct0=yyyy" --proxy http://user:pass@host:port
xmcp-unofficial accounts set-proxy my_reader http://user:pass@host:port   # "none" で解除
xmcp-unofficial accounts list      # 全アカウントの状態
xmcp-unofficial accounts check     # プロフィールを 1 件取得して動作確認
xmcp-unofficial accounts remove my_reader
```

複数アカウントは自動でローテーションされ、レート制限中のアカウントは解除まで使われません。
アカウントは `~/.xmcp_unofficial/accounts.db` に保存されます。

## MCP クライアントへの接続

**Claude Code**

```bash
claude mcp add x-scraper -- xmcp-unofficial
```

**Claude Desktop / Cursor など**（`mcpServers` の JSON）

```json
{
  "mcpServers": {
    "x-scraper": {
      "command": "xmcp-unofficial"
    }
  }
}
```

インストールせずに使う場合は `"command": "uvx", "args": ["--from", "git+https://github.com/Kevin-OS7/Xmcp_unofficial", "xmcp-unofficial"]` とします。

## 設定

設定は `~/.xmcp_unofficial/config.toml`（`setup` が書き出す）から読むので、複数の MCP クライアントで共有されます。
クライアントの `env` などで `XMCP_*` 環境変数を指定すると、そちらが優先されます。

```toml
req_delay = "1.5"      # ページング間の待ち秒数。1.5 は固定、"1-3" は範囲内でランダム、0 は待ちなし
timeout = 120
max_limit = 200
# proxy = "http://user:pass@host:port"   # 全アカウント共通のプロキシ
# db = "~/.xmcp_unofficial/accounts.db"
```

| config.toml | 環境変数 | 既定値 | 意味 |
| --- | --- | --- | --- |
| `db` | `XMCP_DB` | `~/.xmcp_unofficial/accounts.db` | アカウント DB |
| `proxy` | `XMCP_PROXY` | なし | 全リクエスト共通のプロキシ（アカウント個別の設定より優先） |
| `req_delay` | `XMCP_REQ_DELAY` | `1.5` | ページング間の待ち秒数 |
| `timeout` | `XMCP_TIMEOUT` | `120` | 1 回のツール呼び出しの上限秒数。超えたら取得済みの分だけ返す |
| `max_limit` | `XMCP_MAX_LIMIT` | `200` | `limit` 引数の上限 |
| なし | `XMCP_CONFIG` | `~/.xmcp_unofficial/config.toml` | 設定ファイルの場所 |
| なし | `TWS_LOG_LEVEL` | `INFO` | ログレベル（ログは stderr に出る） |

## トラブルシューティング

- **結果が空で、`warnings` に `ConnectError` が出る**：アカウントのプロキシに接続できていません。`xmcp-unofficial accounts set-proxy <user> <url>` で直してください（`none` で直接接続）。
- **「No active scraping accounts」**：アカウントを追加するか、`accounts list` を確認してください。Cookie が切れたアカウントや凍結されたアカウントは無効になります。新しい Cookie で登録し直してください。
- **タイムアウト・部分的な結果**：そのエンドポイントで全アカウントがレート制限中です。アカウントを増やすか、15 分ほど待ってください。`accounts reset-locks` で残ったロックを消せます。

## 開発

```bash
uv sync --extra dev
uv run pytest
uv run ruff check src tests
```

スクレイピング部分は twscrape をベンダリングしたもので、`src/xmcp_unofficial/_vendor/twscrape/` にあります。
X が GraphQL の operation ID を変えたときは、そこにある `api.py` の `OP_*` 定数を更新してください。

## ライセンスとクレジット

MIT ライセンスです。
スクレイピング部分は vladkens 氏の [twscrape](https://github.com/vladkens/twscrape)（MIT License）を元にしています。
帰属表示と変更点の一覧は [NOTICE](NOTICE) を参照してください。
