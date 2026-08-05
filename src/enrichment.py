from __future__ import annotations

import html
import logging
import re
from dataclasses import dataclass, field
from typing import Optional
from urllib.parse import urlsplit

import requests
from bs4 import BeautifulSoup

from src.feeds import NewsItem
from src.text_cleaner import strip_ui_noise

logger = logging.getLogger("news-bot.enrichment")


@dataclass
class EnrichmentResult:
    text: str
    documents: list[dict] = field(default_factory=list)
    status: str = "rss_only"
    query: Optional[str] = None


def _valid_url(value: str) -> bool:
    parts = urlsplit(value.strip())
    return parts.scheme in {"http", "https"} and bool(parts.netloc)


def _clean_text(value: str) -> str:
    value = html.unescape(value or "")
    value = strip_ui_noise(value)
    return re.sub(r"\n{3,}", "\n\n", value).strip()


def _extract_article(response: requests.Response, url: str) -> Optional[dict]:
    content_type = (response.headers.get("content-type") or "").lower()
    if "html" not in content_type and not response.text.lstrip().startswith("<"):
        return None

    # Protect the worker from accidentally processing very large pages.
    raw_html = response.text[:2_000_000]
    soup = BeautifulSoup(raw_html, "html.parser")
    for node in soup(["script", "style", "noscript", "nav", "footer", "header", "form", "aside"]):
        node.decompose()

    title = ""
    title_node = soup.find("meta", attrs={"property": "og:title"})
    if title_node and title_node.get("content"):
        title = str(title_node.get("content"))
    if not title and soup.title:
        title = soup.title.get_text(" ", strip=True)

    container = soup.find("article") or soup.find("main") or soup.body or soup
    paragraphs = []
    for paragraph in container.find_all(["p", "h1", "h2", "li"]):
        text = _clean_text(paragraph.get_text(" ", strip=True))
        if len(text) >= 40:
            paragraphs.append(text)

    text = "\n\n".join(paragraphs)
    if len(text) < 200:
        text = _clean_text(container.get_text(" ", strip=True))
    text = text[:18_000].strip()
    if len(text) < 200:
        return None

    return {
        "url": url,
        "title": _clean_text(title)[:500],
        "kind": "source",
        "text": text,
        "text_length": len(text),
    }


def _fetch_document(url: str, timeout_seconds: int, user_agent: str) -> Optional[dict]:
    if not _valid_url(url):
        return None
    try:
        response = requests.get(
            url,
            timeout=max(3, timeout_seconds),
            headers={"User-Agent": user_agent},
        )
        response.raise_for_status()
        return _extract_article(response, url)
    except (requests.RequestException, UnicodeError) as ex:
        logger.info("Source fetch failed url=%s error=%s", url, ex)
        return None


def _search_urls(
    *,
    query: str,
    endpoint: str,
    api_key: Optional[str],
    timeout_seconds: int,
    user_agent: str,
) -> list[dict]:
    if not api_key or not endpoint:
        return []
    try:
        response = requests.get(
            endpoint,
            params={"q": query, "count": 5, "search_lang": "en"},
            headers={
                "Accept": "application/json",
                "X-Subscription-Token": api_key,
                "User-Agent": user_agent,
            },
            timeout=max(3, timeout_seconds),
        )
        response.raise_for_status()
        payload = response.json()
    except (requests.RequestException, ValueError) as ex:
        logger.info("Search fallback failed query=%s error=%s", query, ex)
        return []

    results = payload.get("web", {}).get("results", []) if isinstance(payload, dict) else []
    found: list[dict] = []
    for result in results if isinstance(results, list) else []:
        if not isinstance(result, dict):
            continue
        url = str(result.get("url") or "").strip()
        if _valid_url(url):
            found.append({"url": url, "title": str(result.get("title") or "")[:500], "kind": "search_result"})
    return found


def enrich_news_item(
    item: NewsItem,
    *,
    enabled: bool,
    mode: str = "source_then_search",
    search_provider: str = "brave",
    search_endpoint: str = "https://api.search.brave.com/res/v1/web/search",
    search_api_key: Optional[str] = None,
    timeout_seconds: int = 15,
    max_sources: int = 3,
    user_agent: str = "news-bot/1.0 (+source-enrichment)",
) -> EnrichmentResult:
    rss_text = _clean_text(item.content or item.title)
    if not enabled or mode == "disabled":
        return EnrichmentResult(text=rss_text, status="disabled")

    documents: list[dict] = []
    primary = None if mode == "search_only" else _fetch_document(item.link, timeout_seconds, user_agent)
    if primary:
        documents.append(primary)
        return EnrichmentResult(
            text=primary["text"],
            documents=[{k: v for k, v in primary.items() if k != "text"}],
            status="source_fetched",
        )

    if mode not in {"source_then_search", "search_only"} or search_provider != "brave":
        return EnrichmentResult(text=rss_text, status="source_unavailable")

    query = " ".join(part for part in [item.title, item.source] if part).strip()
    search_results = _search_urls(
        query=query,
        endpoint=search_endpoint,
        api_key=search_api_key,
        timeout_seconds=timeout_seconds,
        user_agent=user_agent,
    )
    for result in search_results:
        if len(documents) >= max(1, max_sources):
            break
        if result["url"] == item.link or any(doc["url"] == result["url"] for doc in documents):
            continue
        document = _fetch_document(result["url"], timeout_seconds, user_agent)
        if not document:
            continue
        document["kind"] = "search_source"
        documents.append(document)

    if not documents:
        return EnrichmentResult(text=rss_text, status="source_unavailable", query=query)

    # Keep the full text for processing, but send only compact provenance to Hub.
    text_parts = [doc["text"] for doc in documents]
    enriched_text = "\n\n".join(text_parts)[:30_000]
    provenance = [{k: v for k, v in doc.items() if k != "text"} for doc in documents]
    return EnrichmentResult(text=enriched_text, documents=provenance, status="search_fetched", query=query)
