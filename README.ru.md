# NEWS BOT

Сервис автоматизации новостей: собирает свежие новости по теме, переводит, делает короткое саммари и публикует в Telegram и/или VK по расписанию.

English version: [README.md](README.md)

## Быстрый старт

### 1. Клонируйте репозиторий

```bash
git clone https://github.com/ivst/news-bot.git
cd news-bot
```

### 2. Выберите способ

**Docker** — просто клонируйте и запускайте:
```bash
cp .env.example .env
# заполните .env токенами, затем:
docker compose up -d --build
docker compose logs -f
```

**Python** — установите зависимости:
```bash
sudo apt install -y git python3 python3-venv python3-pip  # Debian/Ubuntu
```
затем:
```bash
cp .env.example .env
# заполните .env токенами, затем:
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python main.py
```

**systemd** — установите зависимости:
```bash
sudo apt install -y git python3 python3-venv python3-pip  # Debian/Ubuntu
```
затем:
```bash
sudo git clone https://github.com/ivst/news-bot.git /opt/news-bot
cd /opt/news-bot
sudo chmod +x scripts/install.sh
sudo ./scripts/install.sh  # создаёт .env из шаблона — ответьте 'n' на предложение запуска
```
Теперь отредактируйте `/opt/news-bot/.env` со своими токенами, затем:
```bash
sudo systemctl enable --now news-bot
sudo journalctl -u news-bot -f
```

### Частые настройки `.env`

| Переменная | Что делает |
|-----------|-----------|
| `TARGET_LANGUAGE` | Язык вывода (по умолч.: `ru`) |
| `TIMEZONE` | Часовой пояс (по умолч.: `Europe/Moscow`) |
| `SCHEDULE_CRON` | Расписание публикаций (по умолч.: `*/30 * * * *`) |
| `MAX_NEWS_PER_RUN` | Постов за цикл (по умолч.: `3`) |
| `DIRECT_PUBLISH_ENABLED` | Публиковать сразу или в черновик (по умолч.: `true`) |

Расширенные параметры (LLM, черновики VK, дедупликация и т.д.) → [docs/config.md](docs/config.md).

---

## Production (systemd)

### Полная установка

```bash
sudo git clone https://github.com/ivst/news-bot.git /opt/news-bot
cd /opt/news-bot
sudo chmod +x scripts/install.sh
sudo ./scripts/install.sh
```

Скрипт создаёт пользователя `news-bot`, venv, устанавливает зависимости, копирует `.env.example` → `.env` и ставит systemd-юнит.

### Обновление

```bash
sudo ./scripts/update_service.sh
```

Автоматически находит все запущенные `news-bot@*.service`, делает `git pull` + `pip install` и перезапускает их.

### Несколько инстансов

```bash
sudo SERVICE='news-bot@main' ./scripts/install.sh  # установка шаблона
sudo cp /opt/news-bot/.env /opt/news-bot/.env.main  # отдельный конфиг
sudo systemctl enable --now news-bot@main
sudo journalctl -u news-bot@main -f
```

Для каждого инстанса нужен свой `.env.{name}` с уникальными `TELEGRAM_CHAT_ID`, `TARGET_TOPIC` и `DATABASE_PATH`.

---

## Docker

```bash
cp .env.example .env
# заполните .env токенами, затем:
docker compose up -d --build
docker compose logs -f
```

Данные сохраняются в `./data/`.

---

## Прочее

- **База данных**: опубликованные ссылки хранятся в `data/news.db` (SQLite).
- **История публикаций**: `sqlite3 data/news.db "SELECT channel,status,similarity,substr(title,1,90),created_at FROM post_attempts ORDER BY id DESC LIMIT 30;"`
- **Отказы по похожести**: `sqlite3 data/news.db "SELECT channel,similarity,link,created_at FROM post_attempts WHERE status='rejected_similar' ORDER BY id DESC LIMIT 30;"`
- **Пустой RSS_URLS**: сервис работает, но ничего не публикует.

## Лицензия

MIT. См. [LICENSE](LICENSE).
