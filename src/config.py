from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import List

from dotenv import load_dotenv


@dataclass
class Settings:
    target_topic: str
    target_language: str
    schedule_cron: str
    timezone: str
    max_news_per_run: int
    news_max_age_days: int
    database_path: Path
    rss_urls: List[str]
    telegram_bot_token: str | None
    telegram_chat_id: str | None
    telegram_active_hours: str | None
    vk_group_id: str | None
    vk_access_token: str | None
    vk_active_hours: str | None
    vk_photo_upload_enabled: bool
    vk_draft_mode: bool
    vk_draft_delay_minutes: int
    vk_daily_post_limit: int
    llm_api_key: str | None
    llm_model: str
    llm_base_url: str
    llm_translation_enabled: bool
    llm_summary_prompt: str
    summary_max_lines: int
    short_links_enabled: bool
    shortener_provider: str
    dedup_cleanup_enabled: bool
    dedup_retention_days: int
    post_attempts_retention_days: int
    require_image_for_publish: bool
    duplicate_action: str
    event_tag_dedup_enabled: bool
    event_tag_dedup_window_days: int
    event_tag_dedup_min_tokens: int
    similar_dedup_enabled: bool
    similar_dedup_window: int
    similar_dedup_threshold: float
    similar_dedup_token_threshold: float
    similar_dedup_min_overlap_tokens: int
    hub_enabled: bool
    hub_base_url: str | None
    hub_api_key: str | None
    hub_timeout_seconds: int
    hub_create_jobs: bool
    direct_publish_enabled: bool


def _to_bool(value: str | None, default: bool = False) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "y", "on"}


def load_settings() -> Settings:
    load_dotenv()

    rss_urls = [url.strip() for url in os.getenv("RSS_URLS", "").split(",") if url.strip()]
    db_path = Path(os.getenv("DATABASE_PATH", "./data/news.db")).expanduser()

    return Settings(
        target_topic=os.getenv("TARGET_TOPIC", "news"),
        target_language=os.getenv("TARGET_LANGUAGE", "ru"),
        schedule_cron=os.getenv("SCHEDULE_CRON", "*/30 * * * *"),
        timezone=os.getenv("TIMEZONE", "Europe/Moscow"),
        max_news_per_run=int(os.getenv("MAX_NEWS_PER_RUN", "3")),
        news_max_age_days=max(1, int(os.getenv("NEWS_MAX_AGE_DAYS", "1"))),
        database_path=db_path,
        rss_urls=rss_urls,
        telegram_bot_token=os.getenv("TELEGRAM_BOT_TOKEN") or None,
        telegram_chat_id=os.getenv("TELEGRAM_CHAT_ID") or None,
        telegram_active_hours=(os.getenv("TELEGRAM_ACTIVE_HOURS") or "").strip() or None,
        vk_group_id=os.getenv("VK_GROUP_ID") or None,
        vk_access_token=os.getenv("VK_ACCESS_TOKEN") or None,
        vk_active_hours=(os.getenv("VK_ACTIVE_HOURS") or "").strip() or None,
        vk_photo_upload_enabled=_to_bool(os.getenv("VK_PHOTO_UPLOAD_ENABLED"), default=True),
        vk_draft_mode=_to_bool(os.getenv("VK_DRAFT_MODE"), default=False),
        vk_draft_delay_minutes=max(10, int(os.getenv("VK_DRAFT_DELAY_MINUTES", "43200"))),
        vk_daily_post_limit=max(0, int(os.getenv("VK_DAILY_POST_LIMIT", "0"))),
        llm_api_key=(os.getenv("LLM_API_KEY") or os.getenv("OPENAI_API_KEY") or None),
        llm_model=os.getenv("LLM_MODEL", os.getenv("OPENAI_MODEL", "gpt-4.1-mini")),
        llm_base_url=os.getenv("LLM_BASE_URL", "https://api.openai.com/v1").rstrip("/"),
        llm_translation_enabled=_to_bool(os.getenv("LLM_TRANSLATION_ENABLED"), default=False),
        llm_summary_prompt=os.getenv(
            "LLM_SUMMARY_PROMPT",
            "You are an editor for Telegram and VK digest posts. Write in '{target_language}'. "
            "Return exactly {summary_max_lines} lines, each line starts with '• '. "
            "Keep it factual and concise, no hype, no markdown, no date/source/link repetition.",
        ),
        summary_max_lines=max(1, int(os.getenv("SUMMARY_MAX_LINES", "3"))),
        short_links_enabled=_to_bool(os.getenv("SHORT_LINKS_ENABLED"), default=False),
        shortener_provider=os.getenv("SHORTENER_PROVIDER", "isgd").strip().lower(),
        dedup_cleanup_enabled=_to_bool(os.getenv("DEDUP_CLEANUP_ENABLED"), default=True),
        dedup_retention_days=max(1, int(os.getenv("DEDUP_RETENTION_DAYS", "90"))),
        post_attempts_retention_days=max(1, int(os.getenv("POST_ATTEMPTS_RETENTION_DAYS", "30"))),
        require_image_for_publish=_to_bool(os.getenv("REQUIRE_IMAGE_FOR_PUBLISH"), default=False),
        duplicate_action=(os.getenv("DUPLICATE_ACTION", "skip").strip().lower() or "skip"),
        event_tag_dedup_enabled=_to_bool(os.getenv("EVENT_TAG_DEDUP_ENABLED"), default=False),
        event_tag_dedup_window_days=max(1, int(os.getenv("EVENT_TAG_DEDUP_WINDOW_DAYS", "1"))),
        event_tag_dedup_min_tokens=max(2, int(os.getenv("EVENT_TAG_DEDUP_MIN_TOKENS", "4"))),
        similar_dedup_enabled=_to_bool(os.getenv("SIMILAR_DEDUP_ENABLED"), default=True),
        similar_dedup_window=max(1, int(os.getenv("SIMILAR_DEDUP_WINDOW", "15"))),
        similar_dedup_threshold=min(1.0, max(0.0, float(os.getenv("SIMILAR_DEDUP_THRESHOLD", "0.90")))),
        similar_dedup_token_threshold=min(
            1.0,
            max(0.0, float(os.getenv("SIMILAR_DEDUP_TOKEN_THRESHOLD", "0.72"))),
        ),
        similar_dedup_min_overlap_tokens=max(1, int(os.getenv("SIMILAR_DEDUP_MIN_OVERLAP_TOKENS", "6"))),
        hub_enabled=_to_bool(os.getenv("HUB_ENABLED"), default=False),
        hub_base_url=(os.getenv("HUB_BASE_URL") or "").strip().rstrip("/") or None,
        hub_api_key=(os.getenv("HUB_API_KEY") or "").strip() or None,
        hub_timeout_seconds=max(3, int(os.getenv("HUB_TIMEOUT_SECONDS", "15"))),
        hub_create_jobs=_to_bool(os.getenv("HUB_CREATE_JOBS"), default=True),
        direct_publish_enabled=_to_bool(os.getenv("DIRECT_PUBLISH_ENABLED"), default=True),
    )
