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
Скопируйте `.env.example` в `.env` и заполните:
- `TARGET_TOPIC` - тема материалов (например `world news`, `AI`, `fintech`).
- `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID` для Telegram.
- `VK_GROUP_ID`, `VK_ACCESS_TOKEN` для VK.
- `TARGET_LANGUAGE=ru` или другой код языка.
- `SCHEDULE_CRON` в формате cron (по умолчанию каждые 30 минут).
- `NEWS_MAX_AGE_DAYS=1` - учитывать только новости не старше N дней.
- `SHORT_LINKS_ENABLED=false` - сокращать ссылку перед публикацией.
- `SHORTENER_PROVIDER=isgd` или `tinyurl`.
- `DEDUP_CLEANUP_ENABLED=true` - автоочистка дедуп-записей на каждом запуске.
- `DEDUP_RETENTION_DAYS=90` - хранить дедуп-записи за последние N дней.

### LLM (OpenAI или DeepSeek)
- `LLM_API_KEY` - ключ провайдера.
- `LLM_MODEL` - модель (например `gpt-4.1-mini` или `deepseek-chat`).
- `LLM_BASE_URL` - базовый URL API.
- `LLM_TRANSLATION_ENABLED=true` - включить перевод через LLM.
- `LLM_SUMMARY_PROMPT` - кастомный шаблон промпта summary (поддерживает плейсхолдер `{target_language}`).

Если `LLM_API_KEY` пустой, summary делается локальным fallback, а перевод - через `deep-translator`.

Пример для DeepSeek:
```env
LLM_API_KEY=your_deepseek_key
LLM_MODEL=deepseek-chat
LLM_BASE_URL=https://api.deepseek.com/v1
LLM_TRANSLATION_ENABLED=true
LLM_SUMMARY_PROMPT=You are an editor for Telegram and VK digest posts. Write in '{target_language}'. Return exactly 2 lines, each line starts with '• '.
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

### Обновление запущенного systemd-сервиса
Можно обновить код, зависимости и перезапустить сервис одним скриптом:

```bash
chmod +x scripts/update_service.sh
./scripts/update_service.sh
```

Опциональные переопределения через переменные окружения:
```bash
APP_DIR=/opt/news-bot APP_USER=news-bot SERVICE=news-bot BRANCH=master ./scripts/update_service.sh
```

## Примечания
- Для публикации только в одну платформу можно заполнить только соответствующие переменные.
- База опубликованных ссылок: `data/news.db`.
- При пустом `RSS_URLS` сервис ничего не публикует.
