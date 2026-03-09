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
- `TELEGRAM_ACTIVE_HOURS=` - окно публикации Telegram в локальной `TIMEZONE` (`HH-HH`, например `10-18`; по умолчанию пусто = 24/7).
- `TELEGRAM_SHOW_SOURCE=true` - добавлять строку/ссылку на источник в пост Telegram.
- `VK_GROUP_ID`, `VK_ACCESS_TOKEN` для VK.
- `VK_ACTIVE_HOURS=` - окно публикации VK в локальной `TIMEZONE` (`HH-HH`, например `10-18`; по умолчанию пусто = 24/7).
- `VK_SHOW_SOURCE=true` - добавлять маркер/ссылку источника в текст поста VK.
- `VK_PHOTO_UPLOAD_ENABLED=true` - загружать фото в VK через API (нужен user token с правом `photos`).
- `VK_DRAFT_MODE=false` - создавать отложенные посты VK вместо немедленной публикации.
- `VK_DRAFT_DELAY_MINUTES=43200` - задержка отложенной публикации в минутах (по умолчанию 30 дней).
- `VK_DAILY_POST_LIMIT=0` - лимит постов VK в сутки по локальной `TIMEZONE` (`0` = без лимита, `100`/`200` = жесткий лимит на стороне приложения).
- `TARGET_LANGUAGE=ru` или другой код языка.
- `SCHEDULE_CRON` в формате cron (по умолчанию каждые 30 минут).
- `NEWS_MAX_AGE_DAYS=1` - учитывать только новости не старше N дней.
- `SHORT_LINKS_ENABLED=false` - сокращать ссылку перед публикацией.
- `SHORTENER_PROVIDER=isgd` или `tinyurl`.
- `DEDUP_CLEANUP_ENABLED=true` - автоочистка дедуп-записей на каждом запуске.
- `DEDUP_RETENTION_DAYS=90` - хранить дедуп-записи за последние N дней.
- `POST_ATTEMPTS_RETENTION_DAYS=30` - хранить историю попыток публикации/отказов за последние N дней.
- `REQUIRE_IMAGE_FOR_PUBLISH=false` - публиковать только новости, у которых удалось извлечь URL изображения.
- `DUPLICATE_ACTION=skip` - режим обработки дублей: `skip` или `draft` (для дублей в VK).
- `EVENT_TAG_DEDUP_ENABLED=false` - отклонять посты с одинаковым event key, собранным из нормализованных тегов.
- `EVENT_TAG_DEDUP_WINDOW_DAYS=1` - сравнивать event key с опубликованными постами за последние N дней.
- `EVENT_TAG_DEDUP_MIN_TOKENS=4` - минимальное число значимых токенов для формирования event key.
- `SIMILAR_DEDUP_ENABLED=true` - отклонять слишком похожие недавние посты.
- `SIMILAR_DEDUP_WINDOW=15` - сравнивать с последними N опубликованными постами по каналу.
- `SIMILAR_DEDUP_THRESHOLD=0.90` - порог похожести (0..1).
- `SIMILAR_DEDUP_TOKEN_THRESHOLD=0.72` - порог токенного Jaccard-сходства (0..1) для поиска близких дублей.
- `SIMILAR_DEDUP_MIN_OVERLAP_TOKENS=6` - минимальное число общих токенов для токенного дедупа.
- `HUB_ENABLED=false`, `HUB_BASE_URL`, `HUB_API_KEY`, `HUB_TIMEOUT_SECONDS=15`, `HUB_CREATE_JOBS=true` - отправлять подготовленные материалы и задания каналов во внешний `news-hub` API.
- `DIRECT_PUBLISH_ENABLED=true` - сохранять прямую публикацию в Telegram/VK. Установите `false`, чтобы работать в режиме `hub-only` (доставка только через `news-hub`).

### LLM (OpenAI или DeepSeek)
- `LLM_API_KEY` - ключ провайдера.
- `LLM_MODEL` - модель (например `gpt-4.1-mini` или `deepseek-chat`).
- `LLM_BASE_URL` - базовый URL API.
- `LLM_TRANSLATION_ENABLED=true` - включить перевод через LLM.
- `SUMMARY_MAX_LINES=3` - количество строк в итоговом summary.
- `LLM_SUMMARY_PROMPT` - кастомный шаблон промпта summary (поддерживает плейсхолдеры `{target_language}` и `{summary_max_lines}`).

Если `LLM_API_KEY` пустой, summary делается локальным fallback, а перевод - через `deep-translator`.

Пример для DeepSeek:
```env
LLM_API_KEY=your_deepseek_key
LLM_MODEL=deepseek-chat
LLM_BASE_URL=https://api.deepseek.com/v1
LLM_TRANSLATION_ENABLED=true
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
