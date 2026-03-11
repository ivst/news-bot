# Configuration Reference

This document lists all supported `.env` variables.
For a minimal startup config, see `.env.example` and README.

## Required For Real Use

- `TARGET_TOPIC` - topic keywords (comma-separated). Empty value disables topic filtering.
- `RSS_URLS` - comma-separated RSS URLs.
- One delivery channel:
  - Telegram: `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`
  - VK: `VK_GROUP_ID`, `VK_ACCESS_TOKEN`

## Core

- `TARGET_LANGUAGE` (default: `ru`) - output language.
- `SCHEDULE_CRON` (default: `*/30 * * * *`) - run schedule.
- `TIMEZONE` (default: `Europe/Moscow`) - scheduler and active-hours timezone.
- `MAX_NEWS_PER_RUN` (default: `3`) - maximum successful items per run.
- `NEWS_MAX_AGE_DAYS` (default: `1`) - max source item age in days.
- `DATABASE_PATH` (default: `./data/news.db`) - SQLite database path.

## Telegram

- `TELEGRAM_BOT_TOKEN` (default: empty) - bot token.
- `TELEGRAM_CHAT_ID` (default: empty) - target chat/channel ID.
- `TELEGRAM_ACTIVE_HOURS` (default: empty) - active window `HH-HH`; empty means 24/7.
- `TELEGRAM_SHOW_SOURCE` (default: `true`) - include source marker/link in Telegram text.

## VK

- `VK_GROUP_ID` (default: empty) - VK group ID.
- `VK_ACCESS_TOKEN` (default: empty) - VK access token.
- `VK_ACTIVE_HOURS` (default: empty) - active window `HH-HH`; empty means 24/7.
- `VK_SHOW_SOURCE` (default: `true`) - include source marker/link in VK text.
- `VK_PHOTO_UPLOAD_ENABLED` (default: `true`) - upload/expose image attachments in VK.
- `VK_DRAFT_MODE` (default: `false`) - publish as postponed draft posts.
- `VK_DRAFT_DELAY_MINUTES` (default: `43200`) - draft delay in minutes.
- `VK_DAILY_POST_LIMIT` (default: `0`) - per-day VK cap (`0` means unlimited).

## LLM (OpenAI-Compatible API)

- `LLM_ENABLED` (default: `false`) - global switch for all LLM calls.
- `LLM_API_KEY` (default: empty) - API key for provider.
- `LLM_MODEL` (default: `gpt-4.1-mini`) - model name.
- `LLM_BASE_URL` (default: `https://api.openai.com/v1`) - API base URL.
- `SUMMARY_MAX_LINES` (default: `3`) - number of summary lines.
- `LLM_SUMMARY_PROMPT` - summary prompt template with `{target_language}` and `{summary_max_lines}` placeholders.

Behavior:
- If `LLM_ENABLED=false`, no LLM calls are made.
- If `LLM_ENABLED=true` but `LLM_API_KEY` is empty, local fallback is used.

## Links

- `SHORT_LINKS_ENABLED` (default: `false`) - shorten links before posting.
- `SHORTENER_PROVIDER` (default: `isgd`) - shortener (`isgd` or `tinyurl`).

## Dedup, Retention, Safety

- `DEDUP_CLEANUP_ENABLED` (default: `true`) - cleanup dedup records on each run.
- `DEDUP_RETENTION_DAYS` (default: `90`) - dedup retention window.
- `POST_ATTEMPTS_RETENTION_DAYS` (default: `30`) - attempts retention window.
- `REQUIRE_IMAGE_FOR_PUBLISH` (default: `false`) - reject items without extracted image.
- `DUPLICATE_ACTION` (default: `skip`) - duplicate handling mode (`skip` or `draft` for VK).

Event-tag dedup:
- `EVENT_TAG_DEDUP_ENABLED` (default: `false`)
- `EVENT_TAG_DEDUP_WINDOW_DAYS` (default: `1`)
- `EVENT_TAG_DEDUP_MIN_TOKENS` (default: `4`)

Similarity dedup:
- `SIMILAR_DEDUP_ENABLED` (default: `true`)
- `SIMILAR_DEDUP_WINDOW` (default: `15`)
- `SIMILAR_DEDUP_THRESHOLD` (default: `0.90`)
- `SIMILAR_DEDUP_TOKEN_THRESHOLD` (default: `0.72`)
- `SIMILAR_DEDUP_MIN_OVERLAP_TOKENS` (default: `6`)

## Hub Integration

- `HUB_ENABLED` (default: `false`) - enable external `news-hub` delivery.
- `HUB_BASE_URL` (default: empty) - hub API base URL.
- `HUB_API_KEY` (default: empty) - hub API key.
- `HUB_TIMEOUT_SECONDS` (default: `15`) - hub request timeout.
- `HUB_CREATE_JOBS` (default: `true`) - create per-channel jobs in hub.
- `HUB_SEND_DUPLICATES` (default: `false`) - send duplicate items/jobs to hub.
- `DIRECT_PUBLISH_ENABLED` (default: `true`) - direct channel publishing switch.
