# NEWS BOT

Сервис автоматизации новостей: собирает свежие материалы из RSS по теме `TARGET_TOPIC`, переводит их, формирует краткие резюме и публикует в Telegram и/или VK по расписанию.

Версия на английском: [README.md](README.md)

## Быстрый старт

### 1. Клонируйте репозиторий

```bash
git clone https://github.com/ivst/news-bot.git
cd news-bot
```

### 2. Выберите способ запуска

**Docker:**

```bash
cp .env.example .env
# Настройте .env, как описано ниже, затем запустите:
docker compose up -d --build
docker compose logs -f
```

**Python** — установите зависимости:

```bash
sudo apt install -y python3 python3-venv python3-pip  # Debian/Ubuntu
```

Затем:

```bash
cp .env.example .env
# Настройте .env, как описано ниже, затем запустите:
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python main.py
```

**systemd** — установите зависимости:

```bash
sudo apt install -y git python3 python3-venv python3-pip  # Debian/Ubuntu
```

Затем:

```bash
sudo git clone https://github.com/ivst/news-bot.git /opt/news-bot
cd /opt/news-bot
sudo chmod +x scripts/install.sh
sudo ./scripts/install.sh  # На предложение запустить службу ответьте "n"
```

Установщик создаст `/opt/news-bot/.env` из шаблона. Настройте файл, затем запустите службу:

```bash
sudo systemctl enable --now news-bot
sudo journalctl -u news-bot -f
```

### 3. Настройте `.env`

Минимальная конфигурация:

- В обычном режиме укажите в `RSS_URLS` один или несколько URL RSS-лент через запятую и задайте ключевые слова в `TARGET_TOPIC`.
- Для нескольких потоков вместо этого используйте `STREAMS_CONFIG_PATH` или `STREAMS_CONFIG_JSON` (см. ниже).
- Настройте хотя бы один канал публикации:
    - Telegram: `TELEGRAM_BOT_TOKEN` и `TELEGRAM_CHAT_ID`.
    - VK: `VK_GROUP_ID` и `VK_ACCESS_TOKEN`.

Основные параметры:

| Переменная | Что делает |
|-----------|-----------|
| `TARGET_LANGUAGE` | Язык публикаций (по умолчанию: `ru`) |
| `TIMEZONE` | Часовой пояс планировщика и периодов активности (по умолчанию: `Europe/Moscow`) |
| `SCHEDULE_CRON` | Расписание публикаций (по умолчанию: `*/30 * * * *`) |
| `MAX_NEWS_PER_RUN` | Максимум успешно обработанных материалов за цикл (по умолчанию: `3`) |
| `VK_DRAFT_MODE` | Создавать отложенные записи VK вместо немедленной публикации (по умолчанию: `false`) |
| `DIRECT_PUBLISH_ENABLED` | Публиковать напрямую в настроенные каналы Telegram/VK (по умолчанию: `true`); если параметр отключён, настройте передачу через Hub |

### Несколько потоков в одном экземпляре

Для нескольких независимых тематик используйте `STREAMS_CONFIG_PATH` или `STREAMS_CONFIG_JSON`. Пример готовой конфигурации находится в `config/streams.example.json`.

Локальный запуск через файл:

```bash
cp config/streams.example.json config/streams.json
# при необходимости измените RSS URL, ключевые слова, расписание и каналы
STREAMS_CONFIG_PATH=./config/streams.json python main.py
```

В Docker задайте `STREAMS_CONFIG_PATH=/app/config/streams.json` и подключите файл в контейнер. Для Railway или другого PaaS можно передать JSON целиком через `STREAMS_CONFIG_JSON`.

Каждый поток может иметь свои `rss_urls`, ключевые слова `target_topic`, расписание `schedule_cron`, лимит `max_news_per_run` и каналы `telegram`/`vk`. Если `channels` не указан, используются глобальные каналы. Дедупликация остаётся общей для всех потоков, поэтому одна новость не будет повторно опубликована в одном канале, даже если пришла из разных RSS-поисков. Идентификатор потока сохраняется в истории попыток и передаётся в Hub.

Для прямой публикации в Ленту новостей Битрикс24 добавьте `bitrix24` в `channels` потока и настройте `BITRIX24_WEBHOOK_URL`. Webhook должен иметь право `log`; по умолчанию `BITRIX24_DESTINATION=UA` публикует запись всем авторизованным пользователям портала. При наличии изображения бот прикладывает его к записи, а ссылка на источник получает предпросмотр. В режиме Hub добавьте `bitrix24` в `HUB_CHANNELS`, а webhook настройте уже в `news-hub`.

Если `STREAMS_CONFIG_PATH` и `STREAMS_CONFIG_JSON` не заданы, полностью сохраняется старый режим через `RSS_URLS` и `TARGET_TOPIC`.

Расширенные параметры LLM, интеграции с Hub, дедупликации и других функций описаны в [полном справочнике по конфигурации](docs/config.md) (на английском).

Доступ к LLM необязателен. Без него сервис использует Google Translate как резервный переводчик и формирует простые резюме локально.

## Режимы работы

По умолчанию `news-bot` работает автономно и публикует материалы напрямую в Telegram/VK. Чтобы использовать Hub для хранения, модерации, дедупликации и публикации, настройте:

```env
HUB_ENABLED=true
DIRECT_PUBLISH_ENABLED=false
HUB_CREATE_JOBS=true
HUB_BASE_URL=https://your-hub.example
HUB_API_KEY=your-api-key
```

В режиме Hub бот передаёт исходный текст, перевод, статус обогащения, сведения об источниках и метаданные дедупликации. Hub выполняет финальную проверку дублей перед созданием задачи публикации.

## Обогащение источника и дедупликация

Обогащение источника по умолчанию отключено для совместимости с существующими установками. Включите его явно через `ENRICHMENT_ENABLED=true`. Используйте `ENRICHMENT_MODE=source_only`, если нужно загружать только исходную статью без Search API. При `ENRICHMENT_MODE=source_then_search`, если исходная страница недоступна, используется настроенный Search API. Результаты поиска загружаются как полноценные страницы источников; snippets поисковой выдачи не используются как текст новости.

Чтобы публиковать переработанный нейросетью пост по обогащенной статье, включите `LLM_REWRITE_ENABLED=true` вместе с `LLM_ENABLED=true`. Текст формируется по настройке `LLM_REWRITE_PROMPT`; без этой настройки бот публикует существующее краткое резюме. Обрезанные ответы LLM не публикуются.

Автономная дедупликация проверяет заданное количество последних опубликованных материалов по нормализованным ссылкам, заголовкам, текстовой похожести, character n-grams и event tokens. Количество проверяемых публикаций задаётся через `DEDUP_RECENT_PUBLISHED_LIMIT`; старый параметр `SIMILAR_DEDUP_WINDOW` также поддерживается.

Загрузка изображения в VK повторяется с новым upload server и нормализованным JPEG на каждой попытке. Число попыток и задержка задаются через `VK_PHOTO_UPLOAD_RETRIES` и `VK_PHOTO_UPLOAD_RETRY_BACKOFF_SECONDS`; если все попытки неудачны, пост публикуется без изображения.

## Тесты

Запуск тестов бота:

```bash
python -m unittest discover -s tests -p 'test_*.py'
```

---

## Развёртывание с systemd

### Полная установка

```bash
sudo git clone https://github.com/ivst/news-bot.git /opt/news-bot
cd /opt/news-bot
sudo chmod +x scripts/install.sh
sudo ./scripts/install.sh
```

Скрипт создаёт пользователя `news-bot` и виртуальное окружение, устанавливает зависимости, копирует `.env.example` в `.env` и устанавливает службу systemd.

### Обновление

```bash
sudo ./scripts/update_service.sh
```

Скрипт выполняет `git pull` и `pip install`, затем перезапускает все загруженные экземпляры `news-bot@*.service`, включая неактивные. Если экземпляры шаблонной службы не найдены, он перезапускает `news-bot.service`. Чтобы обновить только одну службу, укажите `SERVICE`, например:

```bash
sudo SERVICE='news-bot@main' ./scripts/update_service.sh
```

### Несколько экземпляров

```bash
sudo SERVICE='news-bot@main' ./scripts/install.sh  # установка шаблонной службы
sudo cp /opt/news-bot/.env /opt/news-bot/.env.main  # отдельная конфигурация
sudo systemctl enable --now news-bot@main
sudo journalctl -u news-bot@main -f
```

Каждому экземпляру нужен отдельный файл `.env.{name}`. Настройте в нём идентификаторы каналов, тему и путь к базе данных. Используйте разные значения `DATABASE_PATH`, если истории публикаций и дедупликации должны быть изолированы.

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

## Примечания

- **База данных**: опубликованные ссылки хранятся в `data/news.db` (SQLite).
- **История публикаций**: `sqlite3 data/news.db "SELECT channel,status,similarity,substr(title,1,90),created_at FROM post_attempts ORDER BY id DESC LIMIT 30;"`
- **Отклонённые как похожие**: `sqlite3 data/news.db "SELECT channel,similarity,link,created_at FROM post_attempts WHERE status='rejected_similar' ORDER BY id DESC LIMIT 30;"`
- **Консольная утилита SQLite**: для диагностических команд выше нужен необязательный пакет `sqlite3` (`sudo apt install sqlite3` в Debian/Ubuntu).
- **Пустой `RSS_URLS`**: сервис продолжает работать, но ему нечего загружать и публиковать.

## Лицензия

MIT. См. [LICENSE](LICENSE).
