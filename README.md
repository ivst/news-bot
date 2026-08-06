# NEWS BOT

A news automation service that collects fresh RSS items for `TARGET_TOPIC`, translates them, creates short summaries, and publishes them to Telegram and/or VK on a schedule.

Russian version: [README.ru.md](README.ru.md)

## Quick start

### 1. Clone the repo

```bash
git clone https://github.com/ivst/news-bot.git
cd news-bot
```

### 2. Choose how to run it

**Docker:**

```bash
cp .env.example .env
# Configure .env as described below, then run:
docker compose up -d --build
docker compose logs -f
```

**Python** — install the dependencies first:

```bash
sudo apt install -y python3 python3-venv python3-pip  # Debian/Ubuntu
```

Then:

```bash
cp .env.example .env
# Configure .env as described below, then run:
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python main.py
```

**systemd** — install the dependencies first:

```bash
sudo apt install -y git python3 python3-venv python3-pip  # Debian/Ubuntu
```

Then:

```bash
sudo git clone https://github.com/ivst/news-bot.git /opt/news-bot
cd /opt/news-bot
sudo chmod +x scripts/install.sh
sudo ./scripts/install.sh  # Answer "n" when prompted to start the service
```

The installer creates `/opt/news-bot/.env` from the template. Configure it, then start the service:

```bash
sudo systemctl enable --now news-bot
sudo journalctl -u news-bot -f
```

### 3. Configure `.env`

At minimum:

- In the regular mode, set `RSS_URLS` to one or more comma-separated RSS feed URLs and configure `TARGET_TOPIC` keywords.
- For multiple streams, use `STREAMS_CONFIG_PATH` or `STREAMS_CONFIG_JSON` instead (see below).
- Configure at least one publishing channel:
    - Telegram: `TELEGRAM_BOT_TOKEN` and `TELEGRAM_CHAT_ID`.
    - VK: `VK_GROUP_ID` and `VK_ACCESS_TOKEN`.

Common settings:

| Variable | What it does |
|----------|-------------|
| `TARGET_LANGUAGE` | Output language (default: `ru`) |
| `TIMEZONE` | Scheduler and active-hours timezone (default: `Europe/Moscow`) |
| `SCHEDULE_CRON` | Publication schedule (default: `*/30 * * * *`) |
| `MAX_NEWS_PER_RUN` | Maximum successfully processed items per cycle (default: `3`) |
| `VK_DRAFT_MODE` | Create postponed VK posts instead of publishing immediately (default: `false`) |
| `DIRECT_PUBLISH_ENABLED` | Publish directly to configured Telegram/VK channels (default: `true`); when disabled, configure Hub delivery and `HUB_CHANNELS` |

### Multiple streams in one instance

Use `STREAMS_CONFIG_PATH` or `STREAMS_CONFIG_JSON` to run multiple independent topic streams in one process. A ready example is available in `config/streams.example.json`.

For a local file-based setup:

```bash
cp config/streams.example.json config/streams.json
# edit RSS URLs, keywords, schedules, and channels if needed
STREAMS_CONFIG_PATH=./config/streams.json python main.py
```

In Docker set `STREAMS_CONFIG_PATH=/app/config/streams.json` and mount the file into the container. On Railway or another PaaS, you can provide the complete JSON through `STREAMS_CONFIG_JSON`.

Each stream can define its own `rss_urls`, `target_topic` keywords, `schedule_cron`, `max_news_per_run`, and `telegram`/`vk` channels. If `channels` is omitted, global delivery channels are used. Deduplication remains shared across streams, so a story arriving through different RSS searches is not published twice to the same channel. The stream ID is stored in attempt history and sent to Hub.

For direct Bitrix24 News Feed publication, add `bitrix24` to a stream's `channels` and configure `BITRIX24_WEBHOOK_URL`. The webhook must have the `log` permission; the default `BITRIX24_DESTINATION=UA` publishes to all authorized portal users. When an image is available, the bot attaches it to the post and enables source-link preview. In Hub mode, add `bitrix24` to `HUB_CHANNELS` and configure the webhook in `news-hub` instead.

If neither `STREAMS_CONFIG_PATH` nor `STREAMS_CONFIG_JSON` is set, the legacy `RSS_URLS`/`TARGET_TOPIC` mode remains unchanged.

Advanced settings (LLM, Hub integration, deduplication, etc.) are documented in [docs/config.md](docs/config.md).

LLM access is optional. Without it, the service uses Google Translate as a fallback and generates simple summaries locally.

## Processing modes

By default, `news-bot` works standalone and publishes directly to Telegram/VK. To use Hub as the storage, moderation, deduplication, and publication service, set:

```env
HUB_ENABLED=true
DIRECT_PUBLISH_ENABLED=false
HUB_CREATE_JOBS=true
HUB_BASE_URL=https://your-hub.example
HUB_API_KEY=your-api-key
```

In Hub mode the bot sends the source text, translation, enrichment status, source provenance, and deduplication metadata. Hub performs the final duplicate check before creating a publication job.

## Source enrichment and deduplication

Source enrichment is disabled by default for compatibility with existing deployments. Enable it explicitly with `ENRICHMENT_ENABLED=true`. Use `ENRICHMENT_MODE=source_only` to load only the original article without a Search API. With `ENRICHMENT_MODE=source_then_search`, the configured Search API is used only when the original page is unavailable. Search results are fetched as real source pages; search snippets are not used as article text.

To publish an AI-edited post based on the enriched article, enable `LLM_REWRITE_ENABLED=true` together with `LLM_ENABLED=true`. The text is generated from `LLM_REWRITE_PROMPT`; without this setting the bot publishes the existing short summary. Truncated LLM responses are rejected instead of being published.

The standalone deduplication checks the configured number of recent published posts using normalized links, titles, text similarity, character n-grams, and event tokens. Configure the window with `DEDUP_RECENT_PUBLISHED_LIMIT` (the legacy `SIMILAR_DEDUP_WINDOW` remains supported).

VK image upload retries use a fresh upload server and a normalized JPEG on each attempt. Configure `VK_PHOTO_UPLOAD_RETRIES` and `VK_PHOTO_UPLOAD_RETRY_BACKOFF_SECONDS`; if all attempts fail, the post is published without the image.

## Tests

Run the bot test suite with:

```bash
python -m unittest discover -s tests -p 'test_*.py'
```

---

## Production (systemd)

### Full installation

```bash
sudo git clone https://github.com/ivst/news-bot.git /opt/news-bot
cd /opt/news-bot
sudo chmod +x scripts/install.sh
sudo ./scripts/install.sh
```

The script creates the `news-bot` user, venv, installs dependencies, copies `.env.example` → `.env`, and installs the systemd unit.

### Update

```bash
sudo ./scripts/update_service.sh
```

The script runs `git pull` and `pip install`, then restarts all loaded `news-bot@*.service` instances, including inactive ones. If it finds no template instances, it restarts `news-bot.service`. To update only one service, set `SERVICE`, for example:

```bash
sudo SERVICE='news-bot@main' ./scripts/update_service.sh
```

### Multiple instances

```bash
sudo SERVICE='news-bot@main' ./scripts/install.sh  # installs template
sudo cp /opt/news-bot/.env /opt/news-bot/.env.main  # separate config
sudo systemctl enable --now news-bot@main
sudo journalctl -u news-bot@main -f
```

Each instance needs its own `.env.{name}` file. Configure its channel IDs, topic, and database path for that instance. Use different `DATABASE_PATH` values when publication and deduplication histories must remain isolated.

---

## Docker

```bash
cp .env.example .env
# edit .env with your tokens, then:
docker compose up -d --build
docker compose logs -f
```

Data is persisted in `./data/`.

---

## Notes

- **Database**: published links are stored in `data/news.db` (SQLite).
- **Publish history**: `sqlite3 data/news.db "SELECT channel,status,similarity,substr(title,1,90),created_at FROM post_attempts ORDER BY id DESC LIMIT 30;"`
- **Rejected as similar**: `sqlite3 data/news.db "SELECT channel,similarity,link,created_at FROM post_attempts WHERE status='rejected_similar' ORDER BY id DESC LIMIT 30;"`
- **SQLite CLI**: the diagnostic commands above require the optional `sqlite3` package (`sudo apt install sqlite3` on Debian/Ubuntu).
- **Empty `RSS_URLS`**: the service remains running but has no items to fetch or publish.

## License

MIT. See [LICENSE](LICENSE).
