from __future__ import annotations

import logging
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


def build_message(title: str, summary: str, link: str) -> str:
    msg = (
        f"{title}\n\n"
        f"{summary}\n\n"
        f"Источник: {link}"
    )
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
        title = strip_ui_noise(title)
        publish_link = item.link
        if settings.short_links_enabled:
            publish_link = shorten_url(item.link, settings.shortener_provider)

        message = build_message(title, summary, publish_link)
        message = strip_ui_noise(message)

        item_has_success = False
        published_at = item.published_at.astimezone(timezone.utc).isoformat()
        for channel_name, publisher in channels:
            try:
                if channel_name == "vk":
                    publisher.publish(message, attachment_link=item.link)
                else:
                    publisher.publish(message)
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
