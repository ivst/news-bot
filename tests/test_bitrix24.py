import base64
import unittest
from unittest.mock import patch

from src.publishers.bitrix24 import Bitrix24Publisher


class FakeResponse:
    status_code = 200

    def __init__(self, payload, *, headers=None, content=b""):
        self.payload = payload
        self.headers = headers or {}
        self.content = content

    def raise_for_status(self):
        return None

    def json(self):
        return self.payload


class Bitrix24PublisherTests(unittest.TestCase):
    @patch("src.publishers.bitrix24.requests.post")
    @patch("src.publishers.bitrix24.requests.get")
    def test_publishes_news_feed_post_with_image_and_source_preview(self, get, post):
        get.return_value = FakeResponse(
            {},
            headers={"Content-Type": "image/png"},
            content=b"image-bytes",
        )
        post.return_value = FakeResponse({"result": 217})
        publisher = Bitrix24Publisher(
            "https://portal.bitrix24.com/rest/1/webhook/log.blogpost.add.json",
            destination=["UA"],
            tags="news,ai",
        )

        result = publisher.publish(
            "Заголовок",
            "Текст новости",
            source_link="https://example.com/news/1",
            image_url="https://example.com/image.png",
        )

        self.assertEqual(217, result)
        payload = post.call_args.kwargs["json"]
        self.assertEqual("Заголовок", payload["POST_TITLE"])
        self.assertIn("Источник: https://example.com/news/1", payload["POST_MESSAGE"])
        self.assertEqual(["UA"], payload["DEST"])
        self.assertEqual("Y", payload["PARSE_PREVIEW"])
        self.assertEqual("news,ai", payload["TAGS"])
        self.assertEqual(["image.png", base64.b64encode(b"image-bytes").decode("ascii")], payload["FILES"][0])

    @patch("src.publishers.bitrix24.requests.post")
    @patch("src.publishers.bitrix24.requests.get", side_effect=RuntimeError("image unavailable"))
    def test_publishes_text_when_image_download_fails(self, _get, post):
        post.return_value = FakeResponse({"result": 218})
        publisher = Bitrix24Publisher("https://portal.bitrix24.com/rest/webhook")

        result = publisher.publish(
            "Заголовок",
            "Текст новости",
            source_link="https://example.com/news/1",
            image_url="https://example.com/image.png",
        )

        self.assertEqual(218, result)
        self.assertNotIn("FILES", post.call_args.kwargs["json"])


if __name__ == "__main__":
    unittest.main()
