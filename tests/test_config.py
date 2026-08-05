import json
import os
import unittest
from unittest.mock import patch

from src.config import effective_streams, load_settings


class ConfigTests(unittest.TestCase):
    def test_existing_environment_keeps_enrichment_disabled_and_legacy_window(self):
        with patch("src.config.load_dotenv"), patch.dict(
            os.environ,
            {"SIMILAR_DEDUP_WINDOW": "15"},
            clear=True,
        ):
            settings = load_settings()

        self.assertFalse(settings.enrichment_enabled)
        self.assertEqual(15, settings.dedup_recent_published_limit)

    def test_new_dedup_limit_and_enrichment_are_explicitly_configurable(self):
        with patch("src.config.load_dotenv"), patch.dict(
            os.environ,
            {
                "DEDUP_RECENT_PUBLISHED_LIMIT": "100",
                "ENRICHMENT_ENABLED": "true",
                "ENRICHMENT_MODE": "source_only",
            },
            clear=True,
        ):
            settings = load_settings()

        self.assertTrue(settings.enrichment_enabled)
        self.assertEqual("source_only", settings.enrichment_mode)
        self.assertEqual(100, settings.dedup_recent_published_limit)

    def test_streams_json_is_loaded_with_per_stream_overrides(self):
        streams_json = json.dumps(
            {
                "streams": [
                    {
                        "id": "ai news",
                        "name": "AI",
                        "rss_urls": ["https://feed.example/ai"],
                        "target_topic": "AI,neural networks",
                        "schedule_cron": "5 * * * *",
                        "max_news_per_run": 2,
                        "channels": ["vk"],
                    },
                    {
                        "id": "markets",
                        "rss_urls": ["https://feed.example/markets"],
                    },
                ]
            }
        )
        with patch("src.config.load_dotenv"), patch.dict(
            os.environ,
            {
                "STREAMS_CONFIG_JSON": streams_json,
                "TARGET_TOPIC": "default-topic",
                "SCHEDULE_CRON": "*/30 * * * *",
                "MAX_NEWS_PER_RUN": "4",
            },
            clear=True,
        ):
            settings = load_settings()

        streams = effective_streams(settings)
        self.assertEqual(["ai-news", "markets"], [stream.stream_id for stream in streams])
        self.assertEqual("AI", streams[0].name)
        self.assertEqual(["vk"], streams[0].channels)
        self.assertEqual("default-topic", streams[1].target_topic)
        self.assertEqual("*/30 * * * *", streams[1].schedule_cron)
        self.assertEqual(4, streams[1].max_news_per_run)

    def test_legacy_settings_become_one_default_stream(self):
        with patch("src.config.load_dotenv"), patch.dict(
            os.environ,
            {
                "RSS_URLS": "https://feed.example/one, https://feed.example/two",
                "TARGET_TOPIC": "world,technology",
            },
            clear=True,
        ):
            settings = load_settings()

        streams = effective_streams(settings)
        self.assertEqual(1, len(streams))
        self.assertEqual("default", streams[0].stream_id)
        self.assertEqual(["https://feed.example/one", "https://feed.example/two"], streams[0].rss_urls)


if __name__ == "__main__":
    unittest.main()
