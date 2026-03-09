from __future__ import annotations

import hashlib
import html
import logging
import re
import time
import unicodedata
from difflib import SequenceMatcher
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger

from src.config import load_settings
from src.feeds import fetch_news
from src.link_shortener import shorten_url
from src.publishers.telegram import TelegramPublisher
from src.publishers.vk import VKDailyPostLimitError, VKPublisher
from src.storage import SeenNewsStore
from src.summarizer import summarize_text
from src.text_cleaner import strip_ui_noise
from src.translator import translate_text

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("news-bot")

_EVENT_STOPWORDS = {
    "the",
    "and",
    "for",
    "with",
    "from",
    "that",
    "this",
    "will",
    "into",
    "about",
    "news",
    "источник",
    "это",
    "как",
    "что",
    "или",
    "для",
    "при",
    "без",
    "после",
    "before",
    "after",
    "over",
    "under",
    "если",
    "also",
}


def _normalize_title(title: str) -> str:
    out = " ".join(title.split())
    # Remove common publisher tails from translated headlines.
    out = re.sub(r"\s*[—\-|:]\s*(livedoor news|yahoo!ニュース|bing news|google news)\s*$", "", out, flags=re.IGNORECASE)
    return out


def _normalize_summary(summary: str, max_lines: int) -> str:
    lines = [ln.strip() for ln in summary.splitlines() if ln.strip()]
    if not lines:
        return ""
    normalized: list[str] = []
    for ln in lines:
        normalized.append(ln if ln.startswith("• ") else f"• {ln.lstrip('•').strip()}")
    return "\n".join(normalized[: max(1, max_lines)])


def _normalize_for_similarity(text: str) -> str:
    text = text.lower()
    text = unicodedata.normalize("NFKC", text)
    text = re.sub(r"https?://\S+", " ", text)
    text = re.sub(r"[^0-9a-zа-яё\s]", " ", text, flags=re.IGNORECASE)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _text_norm_for_similarity(title: str, summary: str) -> str:
    title_norm = _normalize_for_similarity(title)
    summary_norm = _normalize_for_similarity(summary)

    # Use summary as the primary semantic signal. Headline rewrites are noisy
    # and can hide duplicates when compared together with the summary.
    if summary_norm and len(summary_norm.split()) >= 8:
        return summary_norm
    if summary_norm and title_norm:
        return f"{summary_norm} {title_norm}"
    return summary_norm or title_norm


def _event_tokens(text: str) -> list[str]:
    tokens: list[str] = []
    for tok in text.split():
        if len(tok) < 3 and not any(ch.isdigit() for ch in tok):
            continue
        if tok in _EVENT_STOPWORDS:
            continue
        tokens.append(tok)
    return tokens


def _event_key(title: str, summary: str, min_tokens: int) -> str:
    base = _normalize_for_similarity(f"{title} {summary}")
    if not base:
        return ""
    uniq = sorted(set(_event_tokens(base)))
    if len(uniq) < max(2, min_tokens):
        return ""
    digest = hashlib.sha1(" ".join(uniq).encode("utf-8")).hexdigest()
    return digest[:16]


def _similarity_ratio(a: str, b: str) -> float:
    if not a or not b:
        return 0.0
    return SequenceMatcher(None, a, b).ratio()


def _token_set(text: str) -> set[str]:
    return {tok for tok in text.split() if len(tok) >= 3}


def _token_jaccard(a_tokens: set[str], b_tokens: set[str]) -> tuple[float, int]:
    if not a_tokens or not b_tokens:
        return 0.0, 0
    overlap = len(a_tokens & b_tokens)
    union = len(a_tokens | b_tokens)
    if union == 0:
        return 0.0, overlap
    return overlap / union, overlap


def _find_similar_recent(
    store: SeenNewsStore,
    *,
    channel: str,
    text_norm: str,
    window: int,
    threshold: float,
    token_threshold: float,
    min_overlap_tokens: int,
) -> tuple[bool, float, str | None, str]:
    best_score = 0.0
    best_link = None
    best_reason = ""
    curr_tokens = _token_set(text_norm)
    for old_text_norm, old_link in store.get_recent_published_texts(channel, window):
        seq_score = _similarity_ratio(text_norm, old_text_norm)
        old_tokens = _token_set(old_text_norm)
        token_score, overlap = _token_jaccard(curr_tokens, old_tokens)

        is_seq_match = seq_score >= threshold
        is_token_match = token_score >= token_threshold and overlap >= min_overlap_tokens
        score = max(seq_score, token_score)

        if score > best_score:
            best_score = score
            best_link = old_link
            if is_seq_match:
                best_reason = f"sequence:{seq_score:.3f}"
            elif is_token_match:
                best_reason = f"token_jaccard:{token_score:.3f},overlap:{overlap}"
            else:
                best_reason = f"best_non_match:sequence:{seq_score:.3f},token_jaccard:{token_score:.3f},overlap:{overlap}"

        if is_seq_match or is_token_match:
            return True, score, old_link, best_reason

    return False, best_score, best_link, best_reason


def _find_event_duplicate_recent(
    store: SeenNewsStore,
    *,
    channel: str,
    title: str,
    summary: str,
    window_days: int,
    min_tokens: int,
) -> tuple[bool, str | None, str]:
    curr_key = _event_key(title, summary, min_tokens)
    if not curr_key:
        return False, None, ""
    for old_title, old_summary, old_link in store.get_published_attempts_since(channel, window_days):
        old_key = _event_key(old_title, old_summary, min_tokens)
        if old_key and old_key == curr_key:
            return True, old_link, curr_key
    return False, None, curr_key


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


def _is_channel_active(active_hours: str | None, now_local: datetime) -> bool:
    if not active_hours:
        return True
    raw = active_hours.strip()
    m = re.fullmatch(r"([01]?\d|2[0-3])\s*-\s*([01]?\d|2[0-3])", raw)
    if not m:
        logger.warning("Invalid active hours format '%s'. Expected HH-HH (e.g. 10-18). Channel stays active.", raw)
        return True
    start = int(m.group(1))
    end = int(m.group(2))
    hour = now_local.hour
    if start == end:
        return True
    if start < end:
        return start <= hour < end
    return hour >= start or hour < end


def job() -> None:
    settings = load_settings()
    duplicate_action = settings.duplicate_action if settings.duplicate_action in {"skip", "draft"} else "skip"
    now_local = datetime.now(ZoneInfo(settings.timezone))
    tg_active = _is_channel_active(settings.telegram_active_hours, now_local)
    vk_active = _is_channel_active(settings.vk_active_hours, now_local)

    if not settings.rss_urls:
        logger.error("RSS_URLS is empty. Nothing to fetch.")
        return

    store = SeenNewsStore(settings.database_path)
    if settings.dedup_cleanup_enabled:
        deleted_links = store.cleanup_older_than_days(settings.dedup_retention_days)
        deleted_attempts = store.cleanup_attempts_older_than_days(settings.post_attempts_retention_days)
        if deleted_links > 0:
            logger.info(
                "Dedup cleanup removed %s row(s) older than %s day(s)",
                deleted_links,
                settings.dedup_retention_days,
            )
        if deleted_attempts > 0:
            logger.info(
                "Attempts cleanup removed %s row(s) older than %s day(s)",
                deleted_attempts,
                settings.post_attempts_retention_days,
            )
        if deleted_links > 0 or deleted_attempts > 0:
            store.vacuum()
    tg = TelegramPublisher(settings.telegram_bot_token, settings.telegram_chat_id)
    vk = VKPublisher(
        settings.vk_group_id,
        settings.vk_access_token,
        photo_upload_enabled=settings.vk_photo_upload_enabled,
        draft_mode=settings.vk_draft_mode,
        draft_delay_minutes=settings.vk_draft_delay_minutes,
    )
    if tg.enabled and not tg_active:
        logger.info(
            "Telegram publishing is outside active hours (%s). Current time: %02d:%02d",
            settings.telegram_active_hours,
            now_local.hour,
            now_local.minute,
        )
    if vk.enabled and not vk_active:
        logger.info(
            "VK publishing is outside active hours (%s). Current time: %02d:%02d",
            settings.vk_active_hours,
            now_local.hour,
            now_local.minute,
        )

    news = fetch_news(
        settings.rss_urls,
        settings.target_topic,
        settings.max_news_per_run * 5,
        max_age_days=settings.news_max_age_days,
    )
    logger.info("Fetched %s candidate news items", len(news))

    published_items = 0
    published_posts = 0
    vk_daily_limit_reached = False
    vk_daily_post_limit = max(0, settings.vk_daily_post_limit)
    vk_published_today = 0
    if vk_daily_post_limit > 0:
        day_start_local = now_local.replace(hour=0, minute=0, second=0, microsecond=0)
        day_start_utc = day_start_local.astimezone(timezone.utc)
        vk_published_today = store.count_published_attempts_since("vk", day_start_utc.isoformat())
        if vk.enabled and vk_active and vk_published_today >= vk_daily_post_limit:
            vk_daily_limit_reached = True
            logger.info(
                "Configured VK daily post limit already reached (%s/%s). VK publishing disabled until next run.",
                vk_published_today,
                vk_daily_post_limit,
            )
    for item in news:
        if published_items >= settings.max_news_per_run:
            break

        channels: list[tuple[str, object]] = []
        if tg.enabled and tg_active and not store.is_seen("telegram", item.link):
            channels.append(("telegram", tg))
        if vk.enabled and vk_active and not vk_daily_limit_reached and not store.is_seen("vk", item.link):
            channels.append(("vk", vk))
        if not channels:
            continue

        if settings.require_image_for_publish and not item.image_url:
            logger.info("Skipped (image required but missing): %s", item.link)
            published_at = item.published_at.astimezone(timezone.utc).isoformat()
            for channel_name, _ in channels:
                store.record_attempt(
                    channel=channel_name,
                    link=item.link,
                    title=item.title,
                    summary="",
                    text_norm="",
                    status="rejected_no_image",
                    reason="image_required",
                )
                store.mark_seen(channel_name, item.link, published_at)
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
            for channel_name, _ in channels:
                store.record_attempt(
                    channel=channel_name,
                    link=item.link,
                    title=item.title,
                    summary="",
                    text_norm="",
                    status="rejected_translation_failed",
                    reason="body_translation_failed",
                )
            continue
        translated = strip_ui_noise(translated)
        summary = summarize_text(
            translated,
            target_language=settings.target_language,
            llm_api_key=settings.llm_api_key,
            llm_model=settings.llm_model,
            llm_base_url=settings.llm_base_url,
            prompt_template=settings.llm_summary_prompt,
            summary_max_lines=settings.summary_max_lines,
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
            for channel_name, _ in channels:
                store.record_attempt(
                    channel=channel_name,
                    link=item.link,
                    title=item.title,
                    summary=summary,
                    text_norm="",
                    status="rejected_translation_failed",
                    reason="title_translation_failed",
                )
            continue
        title = _normalize_title(strip_ui_noise(title))
        publish_link = item.link
        if settings.short_links_enabled:
            publish_link = shorten_url(item.link, settings.shortener_provider)
        summary = _normalize_summary(summary, settings.summary_max_lines)
        tg_message = strip_ui_noise(build_telegram_message(title, summary, item.link))
        vk_message = strip_ui_noise(build_vk_message(title, summary))
        text_norm = _text_norm_for_similarity(title, summary)

        item_has_success = False
        published_at = item.published_at.astimezone(timezone.utc).isoformat()
        for channel_name, publisher in channels:
            try:
                if settings.event_tag_dedup_enabled:
                    is_event_dup, match_link, event_key = _find_event_duplicate_recent(
                        store,
                        channel=channel_name,
                        title=title,
                        summary=summary,
                        window_days=settings.event_tag_dedup_window_days,
                        min_tokens=settings.event_tag_dedup_min_tokens,
                    )
                    if is_event_dup:
                        if duplicate_action == "draft" and channel_name == "vk":
                            logger.info(
                                "Drafted as event-duplicate for %s: %s (matched=%s, event_key=%s)",
                                channel_name,
                                item.link,
                                match_link or "-",
                                event_key or "-",
                            )
                            publisher.publish(
                                vk_message,
                                attachment_link=item.link,
                                source_link=publish_link,
                                image_url=item.image_url,
                                force_draft=True,
                            )
                            store.mark_seen(channel_name, item.link, published_at)
                            store.record_attempt(
                                channel=channel_name,
                                link=item.link,
                                title=title,
                                summary=summary,
                                text_norm=text_norm,
                                status="published_draft_duplicate",
                                reason=f"event_duplicate;matched:{match_link or ''};event_key:{event_key}",
                            )
                            published_posts += 1
                            if channel_name == "vk" and vk_daily_post_limit > 0:
                                vk_published_today += 1
                                if vk_published_today >= vk_daily_post_limit:
                                    vk_daily_limit_reached = True
                                    logger.info(
                                        "Configured VK daily post limit reached (%s/%s). "
                                        "VK publishing is disabled until next run.",
                                        vk_published_today,
                                        vk_daily_post_limit,
                                    )
                            item_has_success = True
                            time.sleep(1)
                            continue
                        logger.info(
                            "Rejected as event-duplicate for %s: %s (matched=%s, event_key=%s)",
                            channel_name,
                            item.link,
                            match_link or "-",
                            event_key or "-",
                        )
                        store.record_attempt(
                            channel=channel_name,
                            link=item.link,
                            title=title,
                            summary=summary,
                            text_norm=text_norm,
                            status="rejected_event_duplicate",
                            reason=f"matched:{match_link or ''};event_key:{event_key}",
                        )
                        store.mark_seen(channel_name, item.link, published_at)
                        continue

                if settings.similar_dedup_enabled:
                    is_similar, score, match_link, similarity_reason = _find_similar_recent(
                        store,
                        channel=channel_name,
                        text_norm=text_norm,
                        window=settings.similar_dedup_window,
                        threshold=settings.similar_dedup_threshold,
                        token_threshold=settings.similar_dedup_token_threshold,
                        min_overlap_tokens=settings.similar_dedup_min_overlap_tokens,
                    )
                    if is_similar:
                        if duplicate_action == "draft" and channel_name == "vk":
                            logger.info(
                                "Drafted as similar for %s: %s (score=%.3f, matched=%s, reason=%s)",
                                channel_name,
                                item.link,
                                score,
                                match_link or "-",
                                similarity_reason or "-",
                            )
                            publisher.publish(
                                vk_message,
                                attachment_link=item.link,
                                source_link=publish_link,
                                image_url=item.image_url,
                                force_draft=True,
                            )
                            store.mark_seen(channel_name, item.link, published_at)
                            store.record_attempt(
                                channel=channel_name,
                                link=item.link,
                                title=title,
                                summary=summary,
                                text_norm=text_norm,
                                status="published_draft_duplicate",
                                reason=f"similar_duplicate;matched:{match_link or ''};{similarity_reason}",
                                similarity=score,
                            )
                            published_posts += 1
                            if channel_name == "vk" and vk_daily_post_limit > 0:
                                vk_published_today += 1
                                if vk_published_today >= vk_daily_post_limit:
                                    vk_daily_limit_reached = True
                                    logger.info(
                                        "Configured VK daily post limit reached (%s/%s). "
                                        "VK publishing is disabled until next run.",
                                        vk_published_today,
                                        vk_daily_post_limit,
                                    )
                            item_has_success = True
                            time.sleep(1)
                            continue
                        logger.info(
                            "Rejected as similar for %s: %s (score=%.3f, matched=%s, reason=%s)",
                            channel_name,
                            item.link,
                            score,
                            match_link or "-",
                            similarity_reason or "-",
                        )
                        store.record_attempt(
                            channel=channel_name,
                            link=item.link,
                            title=title,
                            summary=summary,
                            text_norm=text_norm,
                            status="rejected_similar",
                            reason=f"matched:{match_link or ''};{similarity_reason}",
                            similarity=score,
                        )
                        store.mark_seen(channel_name, item.link, published_at)
                        continue

                if channel_name == "vk":
                    publisher.publish(
                        vk_message,
                        attachment_link=item.link,
                        source_link=publish_link,
                        image_url=item.image_url,
                    )
                else:
                    publisher.publish(tg_message, image_url=item.image_url)
                store.mark_seen(channel_name, item.link, published_at)
                store.record_attempt(
                    channel=channel_name,
                    link=item.link,
                    title=title,
                    summary=summary,
                    text_norm=text_norm,
                    status="published",
                )
                published_posts += 1
                if channel_name == "vk" and vk_daily_post_limit > 0:
                    vk_published_today += 1
                    if vk_published_today >= vk_daily_post_limit:
                        vk_daily_limit_reached = True
                        logger.info(
                            "Configured VK daily post limit reached (%s/%s). "
                            "VK publishing is disabled until next run.",
                            vk_published_today,
                            vk_daily_post_limit,
                        )
                item_has_success = True
                logger.info("Published to %s: %s", channel_name, item.link)
                time.sleep(1)
            except VKDailyPostLimitError as ex:
                logger.warning(
                    "VK daily post limit reached (error_code=214). VK publishing is disabled until next run. Link: %s",
                    item.link,
                )
                vk_daily_limit_reached = True
                store.record_attempt(
                    channel=channel_name,
                    link=item.link,
                    title=title,
                    summary=summary,
                    text_norm=text_norm,
                    status="publish_deferred_daily_limit",
                    reason=str(ex)[:500],
                )
            except Exception as ex:
                logger.exception("Publish failed for %s (%s): %s", item.link, channel_name, ex)
                store.record_attempt(
                    channel=channel_name,
                    link=item.link,
                    title=title,
                    summary=summary,
                    text_norm=text_norm,
                    status="publish_failed",
                    reason=str(ex)[:500],
                )

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
