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
    database_path: Path
    rss_urls: List[str]
    telegram_bot_token: str | None
    telegram_chat_id: str | None
    vk_group_id: str | None
    vk_access_token: str | None
    llm_api_key: str | None
    llm_model: str
    llm_base_url: str
    llm_translation_enabled: bool
    short_links_enabled: bool
    shortener_provider: str


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
        database_path=db_path,
        rss_urls=rss_urls,
        telegram_bot_token=os.getenv("TELEGRAM_BOT_TOKEN") or None,
        telegram_chat_id=os.getenv("TELEGRAM_CHAT_ID") or None,
        vk_group_id=os.getenv("VK_GROUP_ID") or None,
        vk_access_token=os.getenv("VK_ACCESS_TOKEN") or None,
        llm_api_key=(os.getenv("LLM_API_KEY") or os.getenv("OPENAI_API_KEY") or None),
        llm_model=os.getenv("LLM_MODEL", os.getenv("OPENAI_MODEL", "gpt-4.1-mini")),
        llm_base_url=os.getenv("LLM_BASE_URL", "https://api.openai.com/v1").rstrip("/"),
        llm_translation_enabled=_to_bool(os.getenv("LLM_TRANSLATION_ENABLED"), default=False),
        short_links_enabled=_to_bool(os.getenv("SHORT_LINKS_ENABLED"), default=False),
        shortener_provider=os.getenv("SHORTENER_PROVIDER", "isgd").strip().lower(),
    )
