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

- Set `RSS_URLS` to one or more comma-separated RSS feed URLs.
- Set `TARGET_TOPIC` to comma-separated topic keywords, or leave it empty to disable topic filtering.
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
| `DIRECT_PUBLISH_ENABLED` | Publish directly to configured Telegram/VK channels (default: `true`); when disabled, configure Hub delivery |

Advanced settings (LLM, Hub integration, deduplication, etc.) are documented in [docs/config.md](docs/config.md).

LLM access is optional. Without it, the service uses Google Translate as a fallback and generates simple summaries locally.

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
