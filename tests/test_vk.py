import unittest
from unittest.mock import patch

from src.publishers.vk import VKPublisher


class FakeResponse:
    def __init__(self, body=None, *, status_code=200, headers=None, content=b""):
        self._body = body or {}
        self.status_code = status_code
        self.headers = headers or {}
        self.content = content
        self.url = "https://example.com/article"
        self.text = ""

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")

    def json(self):
        return self._body


class VKPhotoUploadTests(unittest.TestCase):
    def test_retries_with_fresh_upload_server_after_empty_photo_payload(self):
        publisher = VKPublisher(
            "123",
            "token",
            photo_upload_enabled=True,
            photo_upload_retries=3,
            photo_upload_retry_backoff_seconds=1,
        )
        upload_server_calls = []
        upload_calls = []

        def post(url, **kwargs):
            if url.endswith("/photos.getWallUploadServer"):
                upload_server_calls.append(url)
                attempt = len(upload_server_calls)
                return FakeResponse(
                    {"response": {"upload_url": f"https://upload.example/{attempt}"}}
                )
            if url.startswith("https://upload.example/"):
                upload_calls.append(url)
                if len(upload_calls) < 3:
                    return FakeResponse({"photo": ""})
                return FakeResponse({"photo": "photo-payload", "server": 1, "hash": "hash"})
            if url.endswith("/photos.saveWallPhoto"):
                return FakeResponse({"response": [{"owner_id": -123, "id": 99}]})
            raise AssertionError(f"Unexpected POST URL: {url}")

        with patch("src.publishers.vk.requests.post", side_effect=post) as post_mock, \
            patch(
                "src.publishers.vk.requests.get",
                return_value=FakeResponse(
                    status_code=200,
                    headers={"Content-Type": "image/jpeg"},
                    content=b"image-bytes",
                ),
            ), \
            patch.object(VKPublisher, "_to_safe_jpeg", return_value=b"safe-jpeg"), \
            patch("src.publishers.vk.time.sleep") as sleep_mock:
            attachment = publisher._upload_wall_photo("https://example.com/image.jpg")

        self.assertEqual("photo-123_99", attachment)
        self.assertEqual(3, len(upload_server_calls))
        self.assertEqual(
            ["https://upload.example/1", "https://upload.example/2", "https://upload.example/3"],
            upload_calls,
        )
        self.assertEqual(7, post_mock.call_count)  # 3 upload servers + 3 uploads + save
        self.assertEqual(2, sleep_mock.call_count)
        self.assertEqual([1.0, 2.0], [call.args[0] for call in sleep_mock.call_args_list])

    def test_exhausted_retries_raise_upload_error(self):
        publisher = VKPublisher(
            "123",
            "token",
            photo_upload_retries=2,
            photo_upload_retry_backoff_seconds=0,
        )

        def post(url, **kwargs):
            if url.endswith("/photos.getWallUploadServer"):
                return FakeResponse({"response": {"upload_url": "https://upload.example/photo"}})
            if url == "https://upload.example/photo":
                return FakeResponse({"photo": ""})
            raise AssertionError(f"Unexpected POST URL: {url}")

        with patch("src.publishers.vk.requests.post", side_effect=post), \
            patch(
                "src.publishers.vk.requests.get",
                return_value=FakeResponse(
                    status_code=200,
                    headers={"Content-Type": "image/jpeg"},
                    content=b"image-bytes",
                ),
            ), \
            patch.object(VKPublisher, "_to_safe_jpeg", return_value=b"safe-jpeg"), \
            patch("src.publishers.vk.time.sleep"):
            with self.assertRaisesRegex(RuntimeError, "2 attempt"):
                publisher._upload_wall_photo("https://example.com/image.jpg")


if __name__ == "__main__":
    unittest.main()
