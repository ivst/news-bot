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

- Укажите в `RSS_URLS` один или несколько URL RSS-лент через запятую.
- Укажите в `TARGET_TOPIC` ключевые слова через запятую либо оставьте значение пустым, чтобы отключить фильтрацию по теме.
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

Расширенные параметры LLM, интеграции с Hub, дедупликации и других функций описаны в [полном справочнике по конфигурации](docs/config.md) (на английском).

Доступ к LLM необязателен. Без него сервис использует Google Translate как резервный переводчик и формирует простые резюме локально.

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
