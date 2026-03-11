# NEWS BOT

English version: [README.md](README.md)

Сервис автоматизации новостей: собирает свежие новости по теме из `TARGET_TOPIC`, переводит, делает короткое саммари и публикует в Telegram и VK по расписанию. Работает локально, на сервере/VPS или в Docker.

## Что делает
- Читает RSS-источники (`RSS_URLS`).
- Фильтрует новости по `TARGET_TOPIC`.
- Переводит заголовок и текст на `TARGET_LANGUAGE`.
- Делает короткое summary.
- Публикует пост со ссылкой на источник в Telegram и/или VK.
- Не публикует повторно одну и ту же ссылку (SQLite).

## Полная установка (с Git)

### Требования
- Linux-сервер с `systemd`
- `git`, `python3`, `python3-venv`, `pip`

Ubuntu/Debian:
```bash
sudo apt update
sudo apt install -y git python3 python3-venv python3-pip
```

### Установка в `/opt/news-bot`
```bash
sudo useradd -r -s /usr/sbin/nologin news-bot || true
sudo git clone https://github.com/ivst/news-bot.git /opt/news-bot
sudo chown -R news-bot:news-bot /opt/news-bot
cd /opt/news-bot
sudo -u news-bot python3 -m venv .venv
sudo -u news-bot /opt/news-bot/.venv/bin/pip install -r /opt/news-bot/requirements.txt
sudo -u news-bot cp .env.example .env
# отредактируйте /opt/news-bot/.env
```

## Быстрый запуск (Python)

```bash
cd /opt/news-bot
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# заполните .env токенами
python main.py
```

## Запуск в Docker

```bash
cp .env.example .env
# заполните .env
docker compose up -d --build
```

Логи:
```bash
docker compose logs -f
```

## Настройка `.env`
Скопируйте `.env.example` в `.env`.

Минимально необходимые параметры:
- `TARGET_TOPIC`, `RSS_URLS`
- Либо Telegram (`TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`), либо VK (`VK_GROUP_ID`, `VK_ACCESS_TOKEN`)

Параметры, которые обычно меняют:
- `TARGET_LANGUAGE`, `TIMEZONE`, `SCHEDULE_CRON`, `MAX_NEWS_PER_RUN`, `NEWS_MAX_AGE_DAYS`
- `TELEGRAM_ACTIVE_HOURS` / `VK_ACTIVE_HOURS`
- `DIRECT_PUBLISH_ENABLED`

Расширенные параметры сгруппированы в `.env.example` по блокам:
- `LLM` (качество перевода/summary)
- `VK advanced` (драфты, дневной лимит, фото)
- `DEDUP / SAFETY` (дедуп и ретеншн)
- `HUB integration` (внешний delivery API)
- `LINKS` (shortener)

Расширенные переменные можно не указывать в `.env`: будут использованы дефолты из кода.

### LLM (OpenAI-compatible API)
- `LLM_ENABLED=false` - общий переключатель LLM-функций. При `false` вызовы LLM не выполняются даже если ключи указаны.
- `LLM_API_KEY` - ключ провайдера.
- `LLM_MODEL` - модель (например `gpt-4.1-mini` или `deepseek-chat`).
- `LLM_BASE_URL` - базовый URL API.
- `SUMMARY_MAX_LINES=3` - количество строк в итоговом summary.
- `LLM_SUMMARY_PROMPT` - кастомный шаблон промпта summary (поддерживает плейсхолдеры `{target_language}` и `{summary_max_lines}`).

Если `LLM_ENABLED=false` или `LLM_API_KEY` пустой, summary делается локальным fallback, а перевод - через `deep-translator`.

Пример OpenAI-compatible API:
```env
LLM_ENABLED=true
LLM_API_KEY=your_deepseek_key
LLM_MODEL=deepseek-chat
LLM_BASE_URL=https://api.deepseek.com/v1
SUMMARY_MAX_LINES=3
LLM_SUMMARY_PROMPT=You are an editor for Telegram and VK digest posts. Write in '{target_language}'. Return exactly {summary_max_lines} lines, each line starts with '• '.
```

## Запуск как systemd-сервис

1. Установите unit:
```bash
sudo cp deploy/news-bot.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable news-bot
sudo systemctl start news-bot
```
2. Логи:
```bash
sudo journalctl -u news-bot -f
```

### Запуск нескольких инстансов (systemd template)
Если нужно вести несколько каналов/тем параллельно, используйте шаблонный unit `news-bot@.service`.

1. Установите шаблонный unit:
```bash
sudo cp deploy/news-bot@.service /etc/systemd/system/
sudo systemctl daemon-reload
```
2. Создайте env-файлы для каждого инстанса:
```bash
cp /opt/news-bot/.env /opt/news-bot/.env.main
cp /opt/news-bot/.env /opt/news-bot/.env.pub2
```
3. В каждом файле задайте разные значения минимум для:
- `TELEGRAM_CHAT_ID` и/или `VK_GROUP_ID`
- `TARGET_TOPIC`
- `DATABASE_PATH` (например `./data/news_main.db`, `./data/news_pub2.db`)
4. Запустите инстансы:
```bash
sudo systemctl enable --now news-bot@main
sudo systemctl enable --now news-bot@pub2
```
5. Логи конкретного инстанса:
```bash
sudo journalctl -u news-bot@pub2 -f
```

### Обновление запущенного systemd-сервиса
Можно обновить код, зависимости и перезапустить сервис одним скриптом:

```bash
chmod +x scripts/update_service.sh
./scripts/update_service.sh
```

Поведение скрипта:
- если задан `SERVICE`, перезапускается только этот unit;
- если `SERVICE` пустой, скрипт автоматически находит и перезапускает все `news-bot@*.service`;
- если шаблонные unit'ы не найдены, перезапускается `news-bot`.

Опциональные переопределения через переменные окружения:
```bash
APP_DIR=/opt/news-bot APP_USER=news-bot SERVICE=news-bot BRANCH=master ./scripts/update_service.sh
```

Примеры для шаблонных инстансов:
```bash
SERVICE='news-bot@main' ./scripts/update_service.sh
SERVICE='news-bot@pub2' ./scripts/update_service.sh
```

## Примечания
- Для публикации только в одну платформу можно заполнить только соответствующие переменные.
- База опубликованных ссылок: `data/news.db`.
- При пустом `RSS_URLS` сервис ничего не публикует.

### Как проверить историю публикаций/отказов
```bash
sqlite3 /opt/news-bot/data/news.db "SELECT channel,status,similarity,substr(title,1,90),created_at FROM post_attempts ORDER BY id DESC LIMIT 30;"
```

Только отказы из-за похожести:
```bash
sqlite3 /opt/news-bot/data/news.db "SELECT channel,similarity,link,created_at FROM post_attempts WHERE status='rejected_similar' ORDER BY id DESC LIMIT 30;"
```

## Лицензия
Проект распространяется по лицензии MIT. См. [LICENSE](LICENSE).
