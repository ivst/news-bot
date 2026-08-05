import unittest
from datetime import datetime, timezone
from unittest.mock import patch

import requests

from src.enrichment import enrich_news_item
from src.feeds import NewsItem


class FakeResponse:
    def __init__(self, *, text="", content_type="text/html", payload=None):
        self.text = text
        self.headers = {"content-type": content_type}
        self._payload = payload

    def raise_for_status(self):
        return None

    def json(self):
        return self._payload


def make_item():
    return NewsItem(
        title="Important event",
        link="https://origin.example/news/1",
        source="Example source",
        published_at=datetime.now(timezone.utc),
        content="RSS summary",
        image_url=None,
    )


class EnrichmentTests(unittest.TestCase):
    @patch("src.enrichment.requests.get")
    def test_original_article_is_used_before_search(self, get):
        get.return_value = FakeResponse(
            text="<html><head><title>Article</title></head><body><article>"
            + "<p>" + ("A useful article paragraph. " * 20) + "</p>"
            + "</article></body></html>"
        )

        result = enrich_news_item(make_item(), enabled=True, search_api_key="key")

        self.assertEqual("source_fetched", result.status)
        self.assertEqual(1, get.call_count)
        self.assertIn("useful article", result.text)
        self.assertEqual("source", result.documents[0]["kind"])

    @patch("src.enrichment.requests.get")
    def test_search_fallback_fetches_a_real_result_page(self, get):
        search_payload = {"web": {"results": [{"url": "https://search.example/result", "title": "Result"}]}}
        article_html = "<html><body><article><p>" + ("Confirmed result text. " * 20) + "</p></article></body></html>"
        get.side_effect = [
            requests.RequestException("origin unavailable"),
            FakeResponse(content_type="application/json", payload=search_payload),
            FakeResponse(text=article_html),
        ]

        result = enrich_news_item(make_item(), enabled=True, search_api_key="key")

        self.assertEqual("search_fetched", result.status)
        self.assertEqual("https://search.example/result", result.documents[0]["url"])
        self.assertIn("Confirmed result text", result.text)

    def test_disabled_enrichment_keeps_rss_text(self):
        result = enrich_news_item(make_item(), enabled=False)

        self.assertEqual("disabled", result.status)
        self.assertEqual("RSS summary", result.text)


if __name__ == "__main__":
    unittest.main()
