# NEWS BOT

A news automation service: collects fresh news for `TARGET_TOPIC`, translates it, generates a short summary, and publishes to Telegram and/or VK on schedule.

Russian version: [README.ru.md](README.ru.md)

## Quick start

### 1. Clone the repo

```bash
git clone https://github.com/ivst/news-bot.git
cd news-bot
```

### 2. Pick a method

**Docker** — just clone and run:
```bash
cp .env.example .env
# edit .env with your tokens, then:
docker compose up -d --build
docker compose logs -f
```

**Python** — install dependencies first:
```bash
sudo apt install -y git python3 python3-venv python3-pip  # Debian/Ubuntu
```
then:
```bash
cp .env.example .env
# edit .env with your tokens, then:
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python main.py
```

**systemd** — install dependencies first:
```bash
sudo apt install -y git python3 python3-venv python3-pip  # Debian/Ubuntu
```
then:
```bash
sudo git clone https://github.com/ivst/news-bot.git /opt/news-bot
cd /opt/news-bot
sudo chmod +x scripts/install.sh
sudo ./scripts/install.sh  # creates .env from template — answer 'n' on start prompt
```
Now edit `/opt/news-bot/.env` with your tokens, then:
```bash
sudo systemctl enable --now news-bot
sudo journalctl -u news-bot -f
```

### Common `.env` tweaks

| Variable | What it does |
|----------|-------------|
| `TARGET_LANGUAGE` | Output language (default: `ru`) |
| `TIMEZONE` | Your timezone (default: `Europe/Moscow`) |
| `SCHEDULE_CRON` | When to post (default: `*/30 * * * *`) |
| `MAX_NEWS_PER_RUN` | Max posts per cycle (default: `3`) |
| `DIRECT_PUBLISH_ENABLED` | Post immediately or draft first (default: `true`) |

Advanced settings (LLM, VK drafts, dedup, etc.) → [docs/config.md](docs/config.md).

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

Auto-detects all running `news-bot@*.service` instances, runs `git pull` + `pip install`, and restarts them.

### Multiple instances

```bash
sudo SERVICE='news-bot@main' ./scripts/install.sh  # installs template
sudo cp /opt/news-bot/.env /opt/news-bot/.env.main  # separate config
sudo systemctl enable --now news-bot@main
sudo journalctl -u news-bot@main -f
```

Each instance needs its own `.env.{name}` with distinct `TELEGRAM_CHAT_ID`, `TARGET_TOPIC`, and `DATABASE_PATH`.

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
- **Rejected (similar)**: `sqlite3 data/news.db "SELECT channel,similarity,link,created_at FROM post_attempts WHERE status='rejected_similar' ORDER BY id DESC LIMIT 30;"`
- **Empty RSS_URLS**: the service runs but publishes nothing.

## License

MIT. See [LICENSE](LICENSE).
