from __future__ import annotations

import html
import logging
import re
import time
from datetime import timezone

from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger

from src.config import load_settings
from src.feeds import fetch_news
from src.link_shortener import shorten_url
from src.publishers.telegram import TelegramPublisher
from src.publishers.vk import VKPublisher
from src.storage import SeenNewsStore
from src.summarizer import summarize_text
from src.text_cleaner import strip_ui_noise
from src.translator import translate_text

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("news-bot")


def _normalize_title(title: str) -> str:
    out = " ".join(title.split())
    # Remove common publisher tails from translated headlines.
    out = re.sub(r"\s*[—\-|:]\s*(livedoor news|yahoo!ニュース|bing news|google news)\s*$", "", out, flags=re.IGNORECASE)
    return out


def _normalize_summary(summary: str) -> str:
    lines = [ln.strip() for ln in summary.splitlines() if ln.strip()]
    if not lines:
        return ""
    normalized: list[str] = []
    for ln in lines:
        normalized.append(ln if ln.startswith("• ") else f"• {ln.lstrip('•').strip()}")
    return "\n".join(normalized[:2])


def build_telegram_message(title: str, summary: str, link: str) -> str:
    safe_title = html.escape(title)
    safe_summary = html.escape(summary)
    safe_link = html.escape(link, quote=True)
    msg = f"<b>{safe_title}</b>\n\n{safe_summary}\n\n<a href=\"{safe_link}\">Источник</a>"
    if len(msg) > 3900:
        msg = msg[:3890].rsplit(" ", 1)[0] + "..."
    return msg


def build_vk_message(title: str, summary: str) -> str:
    msg = f"{title}\n\n{summary}\n\nИсточник"
    if len(msg) > 3900:
        msg = msg[:3890].rsplit(" ", 1)[0] + "..."
    return msg


def job() -> None:
    settings = load_settings()

    if not settings.rss_urls:
        logger.error("RSS_URLS is empty. Nothing to fetch.")
        return

    store = SeenNewsStore(settings.database_path)
    if settings.dedup_cleanup_enabled:
        deleted = store.cleanup_older_than_days(settings.dedup_retention_days)
        if deleted > 0:
            logger.info(
                "Dedup cleanup removed %s row(s) older than %s day(s)",
                deleted,
                settings.dedup_retention_days,
            )
            store.vacuum()
    tg = TelegramPublisher(settings.telegram_bot_token, settings.telegram_chat_id)
    vk = VKPublisher(settings.vk_group_id, settings.vk_access_token)

    news = fetch_news(
        settings.rss_urls,
        settings.target_topic,
        settings.max_news_per_run * 5,
        max_age_days=settings.news_max_age_days,
    )
    logger.info("Fetched %s candidate news items", len(news))

    published_items = 0
    published_posts = 0
    for item in news:
        if published_items >= settings.max_news_per_run:
            break

        channels: list[tuple[str, object]] = []
        if tg.enabled and not store.is_seen("telegram", item.link):
            channels.append(("telegram", tg))
        if vk.enabled and not store.is_seen("vk", item.link):
            channels.append(("vk", vk))
        if not channels:
            continue

        source_text = item.content if item.content else item.title
        translated = translate_text(
            source_text,
            settings.target_language,
            llm_api_key=settings.llm_api_key,
            llm_model=settings.llm_model,
            llm_base_url=settings.llm_base_url,
            use_llm_translation=settings.llm_translation_enabled,
        )
        if not translated:
            logger.warning("Skipped (translation failed for body): %s", item.link)
            continue
        translated = strip_ui_noise(translated)
        summary = summarize_text(
            translated,
            target_language=settings.target_language,
            llm_api_key=settings.llm_api_key,
            llm_model=settings.llm_model,
            llm_base_url=settings.llm_base_url,
            prompt_template=settings.llm_summary_prompt,
        )
        summary = strip_ui_noise(summary)
        title = translate_text(
            item.title,
            settings.target_language,
            llm_api_key=settings.llm_api_key,
            llm_model=settings.llm_model,
            llm_base_url=settings.llm_base_url,
            use_llm_translation=settings.llm_translation_enabled,
        )
        if not title:
            logger.warning("Skipped (translation failed for title): %s", item.link)
            continue
        title = _normalize_title(strip_ui_noise(title))
        publish_link = item.link
        if settings.short_links_enabled:
            publish_link = shorten_url(item.link, settings.shortener_provider)
        summary = _normalize_summary(summary)
        tg_message = strip_ui_noise(build_telegram_message(title, summary, item.link))
        vk_message = strip_ui_noise(build_vk_message(title, summary))

        item_has_success = False
        published_at = item.published_at.astimezone(timezone.utc).isoformat()
        for channel_name, publisher in channels:
            try:
                if channel_name == "vk":
                    publisher.publish(
                        vk_message,
                        attachment_link=item.link,
                        source_link=publish_link,
                        image_url=item.image_url,
                    )
                else:
                    publisher.publish(tg_message)
                store.mark_seen(channel_name, item.link, published_at)
                published_posts += 1
                item_has_success = True
                logger.info("Published to %s: %s", channel_name, item.link)
                time.sleep(1)
            except Exception as ex:
                logger.exception("Publish failed for %s (%s): %s", item.link, channel_name, ex)

        if item_has_success:
            published_items += 1

    logger.info("Job finished. Published %s item(s), %s post(s)", published_items, published_posts)


def main() -> None:
    settings = load_settings()

    scheduler = BlockingScheduler(timezone=settings.timezone)
    trigger = CronTrigger.from_crontab(settings.schedule_cron, timezone=settings.timezone)
    scheduler.add_job(job, trigger=trigger, id="news-bot-job", replace_existing=True)

    logger.info("Service started. Schedule: %s (%s)", settings.schedule_cron, settings.timezone)
    job()
    scheduler.start()


if __name__ == "__main__":
    main()
