from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, List

from dotenv import load_dotenv


@dataclass(frozen=True)
class NewsStream:
    """Per-topic input and delivery settings for one logical news stream."""

    stream_id: str
    name: str
    rss_urls: List[str]
    target_topic: str
    max_news_per_run: int
    schedule_cron: str | None
    channels: List[str]


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
    telegram_show_source: bool
    vk_group_id: str | None
    vk_access_token: str | None
    vk_active_hours: str | None
    vk_show_source: bool
    vk_photo_upload_enabled: bool
    vk_photo_upload_retries: int
    vk_photo_upload_retry_backoff_seconds: float
    vk_draft_mode: bool
    vk_draft_delay_minutes: int
    vk_daily_post_limit: int
    bitrix24_webhook_url: str | None
    bitrix24_destination: List[str]
    bitrix24_tags: str
    bitrix24_show_source: bool
    bitrix24_image_upload_enabled: bool
    bitrix24_timeout_seconds: int
    llm_enabled: bool
    llm_api_key: str | None
    llm_model: str
    llm_base_url: str
    llm_summary_prompt: str
    llm_rewrite_enabled: bool
    llm_rewrite_prompt: str
    llm_rewrite_max_tokens: int
    llm_rewrite_max_chars: int
    llm_translation_max_tokens: int
    llm_summary_max_tokens: int
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
    dedup_recent_published_limit: int
    similar_dedup_threshold: float
    similar_dedup_token_threshold: float
    similar_dedup_min_overlap_tokens: int
    hub_enabled: bool
    hub_base_url: str | None
    hub_api_key: str | None
    hub_channels: List[str]
    hub_timeout_seconds: int
    hub_create_jobs: bool
    hub_send_duplicates: bool
    direct_publish_enabled: bool
    enrichment_enabled: bool
    enrichment_mode: str
    enrichment_search_provider: str
    enrichment_search_endpoint: str
    enrichment_search_api_key: str | None
    enrichment_timeout_seconds: int
    enrichment_max_sources: int
    streams: List[NewsStream]


def _to_bool(value: str | None, default: bool = False) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "y", "on"}


def _parse_channels(value: str | None) -> List[str]:
    allowed = {"telegram", "vk", "bitrix24"}
    channels: List[str] = []
    for channel in (value or "telegram,vk").split(","):
        normalized = channel.strip().lower()
        if normalized in allowed and normalized not in channels:
            channels.append(normalized)
    return channels


def _parse_stream_channels(value: Any) -> List[str]:
    if value is None:
        return []
    if isinstance(value, str):
        raw_channels = value.split(",")
    elif isinstance(value, list):
        raw_channels = value
    else:
        raise ValueError("stream channels must be a comma-separated string or an array")

    allowed = {"telegram", "vk", "bitrix24"}
    channels: List[str] = []
    unknown: List[str] = []
    for channel in raw_channels:
        normalized = str(channel).strip().lower()
        if not normalized:
            continue
        if normalized not in allowed:
            unknown.append(normalized)
        elif normalized not in channels:
            channels.append(normalized)
    if unknown:
        raise ValueError(f"unsupported stream channel(s): {', '.join(unknown)}")
    return channels


def _parse_stream_urls(value: Any) -> List[str]:
    if isinstance(value, str):
        return [url.strip() for url in value.split(",") if url.strip()]
    if isinstance(value, list):
        return [str(url).strip() for url in value if str(url).strip()]
    if value is None:
        return []
    raise ValueError("stream rss_urls must be a comma-separated string or an array")


def _normalize_stream_id(value: Any, index: int) -> str:
    stream_id = re.sub(r"[^a-zA-Z0-9_.-]+", "-", str(value or "").strip()).strip("-._")
    return stream_id or f"stream-{index + 1}"


def _load_streams_config(
    *,
    path_value: str | None,
    json_value: str | None,
    default_topic: str,
    default_max_news_per_run: int,
    default_schedule_cron: str,
) -> List[NewsStream]:
    raw_config: Any = None
    config_source = ""
    if json_value and json_value.strip():
        config_source = "STREAMS_CONFIG_JSON"
        try:
            raw_config = json.loads(json_value)
        except json.JSONDecodeError as ex:
            raise ValueError(f"invalid STREAMS_CONFIG_JSON: {ex}") from ex
    elif path_value and path_value.strip():
        config_path = Path(path_value).expanduser()
        config_source = str(config_path)
        try:
            raw_config = json.loads(config_path.read_text(encoding="utf-8"))
        except OSError as ex:
            raise ValueError(f"cannot read streams config {config_path}: {ex}") from ex
        except json.JSONDecodeError as ex:
            raise ValueError(f"invalid streams config {config_path}: {ex}") from ex
    else:
        return []

    if isinstance(raw_config, dict):
        raw_streams = raw_config.get("streams")
    else:
        raw_streams = raw_config
    if not isinstance(raw_streams, list):
        raise ValueError(f"{config_source} must contain an array of streams")

    streams: List[NewsStream] = []
    stream_ids: set[str] = set()
    for index, raw_stream in enumerate(raw_streams):
        if not isinstance(raw_stream, dict):
            raise ValueError(f"stream #{index + 1} must be an object")
        stream_id = _normalize_stream_id(raw_stream.get("id"), index)
        if stream_id in stream_ids:
            raise ValueError(f"duplicate stream id: {stream_id}")
        stream_ids.add(stream_id)

        rss_urls = _parse_stream_urls(raw_stream.get("rss_urls", raw_stream.get("rss_url")))
        if not rss_urls:
            raise ValueError(f"stream {stream_id} must define rss_urls")
        try:
            max_news_per_run = max(
                1,
                int(raw_stream.get("max_news_per_run", default_max_news_per_run)),
            )
        except (TypeError, ValueError) as ex:
            raise ValueError(f"stream {stream_id} has invalid max_news_per_run") from ex

        schedule_cron = str(raw_stream.get("schedule_cron") or "").strip() or default_schedule_cron
        target_topic = str(raw_stream.get("target_topic", default_topic) or "").strip()
        name = str(raw_stream.get("name") or stream_id).strip() or stream_id
        streams.append(
            NewsStream(
                stream_id=stream_id,
                name=name,
                rss_urls=rss_urls,
                target_topic=target_topic,
                max_news_per_run=max_news_per_run,
                schedule_cron=schedule_cron,
                channels=_parse_stream_channels(raw_stream.get("channels")),
            )
        )
    return streams


def load_settings() -> Settings:
    load_dotenv()

    rss_urls = [url.strip() for url in os.getenv("RSS_URLS", "").split(",") if url.strip()]
    db_path = Path(os.getenv("DATABASE_PATH", "./data/news.db")).expanduser()
    target_topic = os.getenv("TARGET_TOPIC", "news")
    schedule_cron = os.getenv("SCHEDULE_CRON", "*/30 * * * *")
    max_news_per_run = int(os.getenv("MAX_NEWS_PER_RUN", "3"))
    streams = _load_streams_config(
        path_value=os.getenv("STREAMS_CONFIG_PATH"),
        json_value=os.getenv("STREAMS_CONFIG_JSON"),
        default_topic=target_topic,
        default_max_news_per_run=max_news_per_run,
        default_schedule_cron=schedule_cron,
    )

    return Settings(
        target_topic=target_topic,
        target_language=os.getenv("TARGET_LANGUAGE", "ru"),
        schedule_cron=schedule_cron,
        timezone=os.getenv("TIMEZONE", "Europe/Moscow"),
        max_news_per_run=max_news_per_run,
        news_max_age_days=max(1, int(os.getenv("NEWS_MAX_AGE_DAYS", "1"))),
        database_path=db_path,
        rss_urls=rss_urls,
        telegram_bot_token=os.getenv("TELEGRAM_BOT_TOKEN") or None,
        telegram_chat_id=os.getenv("TELEGRAM_CHAT_ID") or None,
        telegram_active_hours=(os.getenv("TELEGRAM_ACTIVE_HOURS") or "").strip() or None,
        telegram_show_source=_to_bool(os.getenv("TELEGRAM_SHOW_SOURCE"), default=True),
        vk_group_id=os.getenv("VK_GROUP_ID") or None,
        vk_access_token=os.getenv("VK_ACCESS_TOKEN") or None,
        vk_active_hours=(os.getenv("VK_ACTIVE_HOURS") or "").strip() or None,
        vk_show_source=_to_bool(os.getenv("VK_SHOW_SOURCE"), default=True),
        vk_photo_upload_enabled=_to_bool(os.getenv("VK_PHOTO_UPLOAD_ENABLED"), default=True),
        vk_photo_upload_retries=max(1, int(os.getenv("VK_PHOTO_UPLOAD_RETRIES", "3"))),
        vk_photo_upload_retry_backoff_seconds=max(
            0.0,
            float(os.getenv("VK_PHOTO_UPLOAD_RETRY_BACKOFF_SECONDS", "1")),
        ),
        vk_draft_mode=_to_bool(os.getenv("VK_DRAFT_MODE"), default=False),
        vk_draft_delay_minutes=max(10, int(os.getenv("VK_DRAFT_DELAY_MINUTES", "43200"))),
        vk_daily_post_limit=max(0, int(os.getenv("VK_DAILY_POST_LIMIT", "0"))),
        bitrix24_webhook_url=(os.getenv("BITRIX24_WEBHOOK_URL") or "").strip() or None,
        bitrix24_destination=[
            destination.strip()
            for destination in os.getenv("BITRIX24_DESTINATION", "UA").split(",")
            if destination.strip()
        ],
        bitrix24_tags=(os.getenv("BITRIX24_TAGS") or "").strip(),
        bitrix24_show_source=_to_bool(os.getenv("BITRIX24_SHOW_SOURCE"), default=True),
        bitrix24_image_upload_enabled=_to_bool(os.getenv("BITRIX24_IMAGE_UPLOAD_ENABLED"), default=True),
        bitrix24_timeout_seconds=max(3, int(os.getenv("BITRIX24_TIMEOUT_SECONDS", "30"))),
        llm_enabled=_to_bool(os.getenv("LLM_ENABLED"), default=False),
        llm_api_key=os.getenv("LLM_API_KEY") or None,
        llm_model=os.getenv("LLM_MODEL", "gpt-4.1-mini"),
        llm_base_url=os.getenv("LLM_BASE_URL", "https://api.openai.com/v1").rstrip("/"),
        llm_summary_prompt=os.getenv(
            "LLM_SUMMARY_PROMPT",
            "You are an editor for Telegram and VK digest posts. Write in '{target_language}'. "
            "Return exactly {summary_max_lines} lines, each line starts with '• '. "
            "Keep it factual and concise, no hype, no markdown, no date/source/link repetition.",
        ),
        llm_translation_max_tokens=max(1, int(os.getenv("LLM_TRANSLATION_MAX_TOKENS", "4000"))),
        llm_summary_max_tokens=max(1, int(os.getenv("LLM_SUMMARY_MAX_TOKENS", "2000"))),
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
        dedup_recent_published_limit=max(
            1,
            int(os.getenv("DEDUP_RECENT_PUBLISHED_LIMIT", os.getenv("SIMILAR_DEDUP_WINDOW", "15"))),
        ),
        llm_rewrite_enabled=_to_bool(os.getenv("LLM_REWRITE_ENABLED"), default=False),
        llm_rewrite_prompt=os.getenv(
            "LLM_REWRITE_PROMPT",
            "You are a factual news editor. Rewrite the material in '{target_language}' "
            "as a ready-to-publish news post. Use only facts from the material, do not invent details, "
            "do not add a title, source, link, or editorial commentary. Keep it concise and within "
            "{rewrite_max_chars} characters. Return only the rewritten post.",
        ),
        llm_rewrite_max_tokens=max(1, int(os.getenv("LLM_REWRITE_MAX_TOKENS", "4000"))),
        llm_rewrite_max_chars=max(200, int(os.getenv("LLM_REWRITE_MAX_CHARS", "3000"))),
        similar_dedup_threshold=min(1.0, max(0.0, float(os.getenv("SIMILAR_DEDUP_THRESHOLD", "0.90")))),
        similar_dedup_token_threshold=min(
            1.0,
            max(0.0, float(os.getenv("SIMILAR_DEDUP_TOKEN_THRESHOLD", "0.72"))),
        ),
        similar_dedup_min_overlap_tokens=max(1, int(os.getenv("SIMILAR_DEDUP_MIN_OVERLAP_TOKENS", "6"))),
        hub_enabled=_to_bool(os.getenv("HUB_ENABLED"), default=False),
        hub_base_url=(os.getenv("HUB_BASE_URL") or "").strip().rstrip("/") or None,
        hub_api_key=(os.getenv("HUB_API_KEY") or "").strip() or None,
        hub_channels=_parse_channels(os.getenv("HUB_CHANNELS")),
        hub_timeout_seconds=max(3, int(os.getenv("HUB_TIMEOUT_SECONDS", "15"))),
        hub_create_jobs=_to_bool(os.getenv("HUB_CREATE_JOBS"), default=True),
        hub_send_duplicates=_to_bool(os.getenv("HUB_SEND_DUPLICATES"), default=False),
        direct_publish_enabled=_to_bool(os.getenv("DIRECT_PUBLISH_ENABLED"), default=True),
        # Keep existing standalone deployments behavior-compatible. Enrichment
        # is opt-in so an old .env does not suddenly add network requests or
        # change the publication text.
        enrichment_enabled=_to_bool(os.getenv("ENRICHMENT_ENABLED"), default=False),
        enrichment_mode=(os.getenv("ENRICHMENT_MODE", "source_then_search").strip().lower() or "source_then_search"),
        enrichment_search_provider=(os.getenv("ENRICHMENT_SEARCH_PROVIDER", "brave").strip().lower() or "brave"),
        enrichment_search_endpoint=(
            os.getenv("ENRICHMENT_SEARCH_ENDPOINT", "https://api.search.brave.com/res/v1/web/search").strip()
        ),
        enrichment_search_api_key=(os.getenv("ENRICHMENT_SEARCH_API_KEY") or "").strip() or None,
        enrichment_timeout_seconds=max(3, int(os.getenv("ENRICHMENT_TIMEOUT_SECONDS", "15"))),
        enrichment_max_sources=max(1, int(os.getenv("ENRICHMENT_MAX_SOURCES", "3"))),
        streams=streams,
    )


def effective_streams(settings: Settings) -> List[NewsStream]:
    """Return configured streams, or one legacy stream from the old .env keys."""

    if settings.streams:
        return settings.streams
    if not settings.rss_urls:
        return []
    return [
        NewsStream(
            stream_id="default",
            name="Default",
            rss_urls=settings.rss_urls,
            target_topic=settings.target_topic,
            max_news_per_run=settings.max_news_per_run,
            schedule_cron=settings.schedule_cron,
            channels=[],
        )
    ]
