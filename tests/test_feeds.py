import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

from src.feeds import fetch_news


class FakeResponse:
    def __init__(self, content: bytes):
        self.content = content

    def raise_for_status(self):
        return None


class FeedTests(unittest.TestCase):
    @patch("src.feeds._extract_image_from_article", return_value=None)
    @patch("src.feeds.requests.get")
    def test_fetch_filters_topic_normalizes_links_and_deduplicates(self, get, _extract_image):
        published = datetime.now(timezone.utc) - timedelta(minutes=5)
        date = published.strftime("%a, %d %b %Y %H:%M:%S +0000")
        feed = f"""
        <rss version="2.0"><channel><title>Test feed</title>
          <item><title>AI launch</title><link>http://Example.com/story?utm_source=rss</link>
            <pubDate>{date}</pubDate><description>AI company launches a product.</description></item>
          <item><title>Sports result</title><link>https://example.com/sports</link>
            <pubDate>{date}</pubDate><description>Football result.</description></item>
          <item><title>AI launch</title><link>https://example.com/story</link>
            <pubDate>{date}</pubDate><description>Second copy.</description></item>
        </channel></rss>
        """.encode()
        get.return_value = FakeResponse(feed)

        items = fetch_news(["https://feed.example/rss"], topic="AI", limit=10)

        self.assertEqual(1, len(items))
        self.assertEqual("https://example.com/story", items[0].link)
        self.assertEqual("AI launch", items[0].title)

    @patch("src.feeds.requests.get")
    def test_old_entries_are_not_returned(self, get):
        old = datetime.now(timezone.utc) - timedelta(days=3)
        date = old.strftime("%a, %d %b %Y %H:%M:%S +0000")
        feed = f"""<rss version="2.0"><channel><item>
            <title>Old AI news</title><link>https://example.com/old</link>
            <pubDate>{date}</pubDate><description>Old article.</description>
        </item></channel></rss>""".encode()
        get.return_value = FakeResponse(feed)

        self.assertEqual([], fetch_news(["https://feed.example/rss"], topic="AI", limit=10, max_age_days=1))


if __name__ == "__main__":
    unittest.main()
