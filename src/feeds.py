from __future__ import annotations

import html
from dataclasses import dataclass
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from typing import List
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

import feedparser
from bs4 import BeautifulSoup


@dataclass
class NewsItem:
    title: str
    link: str
    source: str
    published_at: datetime
    content: str


def _to_datetime(entry) -> datetime:
    if "published" in entry:
        try:
            dt = parsedate_to_datetime(entry.published)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt
        except Exception:
            pass
    return datetime.now(tz=timezone.utc)


def _extract_text(raw: str) -> str:
    if not raw:
        return ""
    soup = BeautifulSoup(html.unescape(raw), "html.parser")
    return " ".join(soup.get_text(" ", strip=True).split())


def _normalize_link(link: str) -> str:
    if not link:
        return ""

    parts = urlsplit(link.strip())
    drop_params = {
        "tid",
        "utm_source",
        "utm_medium",
        "utm_campaign",
        "utm_term",
        "utm_content",
        "utm_id",
        "gclid",
        "fbclid",
        "msclkid",
        "mc_cid",
        "mc_eid",
        "ref",
        "ref_src",
        "igshid",
        "yclid",
    }
    kept = [(k, v) for k, v in parse_qsl(parts.query, keep_blank_values=True) if k.lower() not in drop_params]
    normalized_query = urlencode(kept, doseq=True)

    return urlunsplit((parts.scheme.lower(), parts.netloc.lower(), parts.path, normalized_query, ""))


def fetch_news(rss_urls: List[str], topic: str, limit: int) -> List[NewsItem]:
    topic_lower = topic.lower()
    collected: List[NewsItem] = []

    for url in rss_urls:
        feed = feedparser.parse(url)
        source = feed.feed.get("title", "Unknown source")
        for entry in feed.entries:
            title = (entry.get("title") or "").strip()
            summary = _extract_text(entry.get("summary") or "")
            link = _normalize_link(entry.get("link") or "")

            searchable = f"{title} {summary}".lower()
            if topic_lower not in searchable:
                continue
            if not link:
                continue

            collected.append(
                NewsItem(
                    title=title,
                    link=link,
                    source=source,
                    published_at=_to_datetime(entry),
                    content=summary,
                )
            )

    collected.sort(key=lambda x: x.published_at, reverse=True)

    dedup: dict[str, NewsItem] = {}
    for item in collected:
        dedup[item.link] = item

    return list(dedup.values())[:limit]
