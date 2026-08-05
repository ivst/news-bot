import unittest
from unittest.mock import patch

import requests

from src.hub_client import HubClient


class FakeResponse:
    status_code = 201

    def __init__(self, payload):
        self.payload = payload

    def raise_for_status(self):
        return None

    def json(self):
        return self.payload


class HubClientTests(unittest.TestCase):
    @patch("src.hub_client.requests.post")
    def test_ingest_sends_enrichment_provenance(self, post):
        post.return_value = FakeResponse({"item_id": 42})
        client = HubClient(base_url="https://hub.example", api_key="secret")

        item_id = client.ingest_item(
            idempotency_key="key",
            source_link="https://example.com/news",
            source_title="Title",
            source_text="Source",
            translated_title="Заголовок",
            translated_summary="Кратко",
            translated_body="Текст",
            language="ru",
            image_url=None,
            suggested_channels=["telegram", "invalid"],
            metadata={"dedup": {"event_key": "event"}},
            source_documents=[{"url": "https://example.com/news", "kind": "source"}],
            enrichment_status="source_fetched",
            enrichment_query=None,
            publication_mode="automatic",
        )

        self.assertEqual(42, item_id)
        payload = post.call_args.kwargs["json"]
        self.assertEqual("source_fetched", payload["enrichment_status"])
        self.assertEqual("automatic", payload["publication_mode"])
        self.assertEqual("event", payload["metadata"]["dedup"]["event_key"])
        self.assertEqual(["telegram"], payload["suggested_channels"])

    @patch("src.hub_client.requests.post", side_effect=requests.Timeout("timeout"))
    def test_http_failure_is_propagated(self, _post):
        client = HubClient(base_url="https://hub.example", api_key="secret")

        with self.assertRaises(requests.Timeout):
            client.create_job(item_id=42, channel="telegram")


if __name__ == "__main__":
    unittest.main()
