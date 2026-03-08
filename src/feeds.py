from __future__ import annotations

import html
import re
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from typing import List, Optional
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

import feedparser
import requests
from bs4 import BeautifulSoup


@dataclass
class NewsItem:
    title: str
    link: str
    source: str
    published_at: datetime
    content: str
    image_url: Optional[str]


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
    text = html.unescape(raw).strip()
    # Avoid BeautifulSoup warnings on plain text that looks like a path/filename.
    if "<" not in text or ">" not in text:
        return " ".join(text.split())
    soup = BeautifulSoup(text, "html.parser")
    return " ".join(soup.get_text(" ", strip=True).split())


def _normalize_image_url(url: str) -> str:
    if not url:
        return ""
    url = html.unescape(url.strip()).replace(";=", "=")
    parts = urlsplit(url)
    scheme = parts.scheme.lower() or "https"
    if scheme == "http":
        scheme = "https"
    return urlunsplit((scheme, parts.netloc.lower(), parts.path, parts.query, ""))


def _with_bing_image_size(url: str, entry) -> str:
    parts = urlsplit(url)
    if not parts.netloc.lower().endswith("bing.com") or parts.path.lower() != "/th":
        return url

    max_w = entry.get("news_imagemaxwidth")
    max_h = entry.get("news_imagemaxheight")
    if not max_w or not max_h:
        return url

    try:
        width = int(str(max_w))
        height = int(str(max_h))
    except (TypeError, ValueError):
        return url
    if width <= 0 or height <= 0:
        return url

    params = dict(parse_qsl(parts.query, keep_blank_values=True))
    params["w"] = str(width)
    params["h"] = str(height)

    template = str(entry.get("news_imagesize") or "")
    template = html.unescape(template).replace(";=", "=")
    match = re.search(r"(?:^|&)c=(\d+)(?:&|$)", template)
    if match:
        params["c"] = match.group(1)

    return urlunsplit((parts.scheme, parts.netloc, parts.path, urlencode(params, doseq=True), ""))


def _extract_image_from_article(link: str) -> Optional[str]:
    if not link:
        return None
    try:
        resp = requests.get(
            link,
            timeout=12,
            headers={"User-Agent": "Mozilla/5.0 (compatible; NewsBot/1.0)"},
        )
        resp.raise_for_status()
        content_type = (resp.headers.get("content-type") or "").lower()
        if "html" not in content_type:
            return None
        soup = BeautifulSoup(resp.text, "html.parser")
        selectors = [
            ("property", "og:image"),
            ("property", "og:image:url"),
            ("name", "twitter:image"),
            ("itemprop", "image"),
        ]
        for attr, value in selectors:
            node = soup.find("meta", attrs={attr: value})
            if node and node.get("content"):
                url = _normalize_image_url(str(node.get("content")))
                if url:
                    return url
    except requests.RequestException:
        return None
    return None


def _extract_image_url(entry, article_link: str = "") -> Optional[str]:
    # Yahoo RSS often provides preview image in the <image> tag.
    entry_image = entry.get("image")
    if isinstance(entry_image, str):
        url = _with_bing_image_size(_normalize_image_url(entry_image), entry)
        if url:
            return url
    elif isinstance(entry_image, dict):
        url = _with_bing_image_size(
            _normalize_image_url(str(entry_image.get("href") or entry_image.get("url") or "")),
            entry,
        )
        if url:
            return url

    # Bing News namespace can be exposed as entry["news_image"].
    news_image = entry.get("news_image")
    if isinstance(news_image, str):
        url = _with_bing_image_size(_normalize_image_url(news_image), entry)
        if url:
            return url
    elif isinstance(news_image, dict):
        url = _with_bing_image_size(
            _normalize_image_url(str(news_image.get("href") or news_image.get("url") or "")),
            entry,
        )
        if url:
            return url

    media_content = entry.get("media_content") or []
    for item in media_content:
        url = _normalize_image_url(str(item.get("url") or ""))
        if url:
            return url

    media_thumb = entry.get("media_thumbnail") or []
    for item in media_thumb:
        url = _normalize_image_url(str(item.get("url") or ""))
        if url:
            return url

    links = entry.get("links") or []
    for item in links:
        if str(item.get("type") or "").startswith("image/"):
            url = _normalize_image_url(str(item.get("href") or ""))
            if url:
                return url

    summary_html = entry.get("summary") or ""
    if summary_html:
        summary_html = html.unescape(summary_html).strip()
        if "<img" not in summary_html.lower():
            return _extract_image_from_article(article_link)
        soup = BeautifulSoup(summary_html, "html.parser")
        img = soup.find("img")
        if img and img.get("src"):
            url = _normalize_image_url(str(img.get("src")))
            if url:
                return url

    return _extract_image_from_article(article_link)


def _normalize_link(link: str) -> str:
    if not link:
        return ""

    parts = urlsplit(link.strip())

    # Unwrap Bing redirect URLs to the actual article URL.
    if parts.netloc.lower().endswith("bing.com") and parts.path.lower().startswith("/news/apiclick"):
        query = dict(parse_qsl(parts.query, keep_blank_values=True))
        target = (query.get("url") or "").strip()
        if target:
            parts = urlsplit(target)

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

    scheme = parts.scheme.lower() or "https"
    if scheme == "http":
        scheme = "https"
    return urlunsplit((scheme, parts.netloc.lower(), parts.path, normalized_query, ""))


def fetch_news(rss_urls: List[str], topic: str, limit: int, max_age_days: int = 1) -> List[NewsItem]:
    topic_lower = topic.lower()
    collected: List[NewsItem] = []
    cutoff = datetime.now(tz=timezone.utc) - timedelta(days=max(1, max_age_days))

    for url in rss_urls:
        feed = feedparser.parse(url)
        source = feed.feed.get("title", "Unknown source")
        for entry in feed.entries:
            published_at = _to_datetime(entry)
            if published_at < cutoff:
                continue

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
                    published_at=published_at,
                    content=summary,
                    image_url=_extract_image_url(entry, link),
                )
            )

    collected.sort(key=lambda x: x.published_at, reverse=True)

    dedup: dict[str, NewsItem] = {}
    for item in collected:
        dedup[item.link] = item

    return list(dedup.values())[:limit]
