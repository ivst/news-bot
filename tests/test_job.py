import os
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import Mock, patch

import main
from src.config import load_settings
from src.feeds import NewsItem
from src.storage import SeenNewsStore


def make_settings(database_path: Path, **overrides):
    values = {
        "RSS_URLS": "https://feed.example/rss",
        "TARGET_TOPIC": "",
        "DATABASE_PATH": str(database_path),
        "MAX_NEWS_PER_RUN": "1",
        "DEDUP_CLEANUP_ENABLED": "false",
        "ENRICHMENT_ENABLED": "false",
        "SIMILAR_DEDUP_ENABLED": "false",
        "EVENT_TAG_DEDUP_ENABLED": "false",
        "TELEGRAM_BOT_TOKEN": "token",
        "TELEGRAM_CHAT_ID": "chat",
        "VK_GROUP_ID": "",
        "VK_ACCESS_TOKEN": "",
    }
    values.update(overrides)
    with patch("src.config.load_dotenv"), patch.dict(os.environ, values, clear=True):
        return load_settings()


def make_news():
    return NewsItem(
        title="Original title",
        link="https://example.com/news/1",
        source="Example feed",
        published_at=datetime.now(timezone.utc),
        content="Original article text with enough context.",
        image_url=None,
    )


class JobTests(unittest.TestCase):
    def test_direct_mode_publishes_and_records_seen_item(self):
        with tempfile.TemporaryDirectory() as directory:
            db_path = Path(directory) / "news.db"
            settings = make_settings(db_path)
            telegram = Mock()
            telegram.enabled = True
            vk = Mock()
            vk.enabled = False
            hub = Mock()
            hub.enabled = False

            with patch.object(main, "load_settings", return_value=settings), \
                patch.object(main, "fetch_news", return_value=[make_news()]), \
                patch.object(main, "translate_text", return_value="Переведённый текст"), \
                patch.object(main, "summarize_text", return_value="• Краткое содержание"), \
                patch.object(main, "TelegramPublisher", return_value=telegram), \
                patch.object(main, "VKPublisher", return_value=vk), \
                patch.object(main, "HubClient", return_value=hub), \
                patch.object(main.time, "sleep"):
                main.job()

            telegram.publish.assert_called_once()
            self.assertTrue(SeenNewsStore(db_path).is_seen("telegram", "https://example.com/news/1"))

    def test_hub_only_mode_queues_without_direct_channel_publish(self):
        with tempfile.TemporaryDirectory() as directory:
            db_path = Path(directory) / "news.db"
            settings = make_settings(
                db_path,
                DIRECT_PUBLISH_ENABLED="false",
                HUB_ENABLED="true",
                HUB_BASE_URL="https://hub.example",
                HUB_CHANNELS="telegram",
            )
            telegram = Mock()
            telegram.enabled = False
            vk = Mock()
            vk.enabled = False
            hub = Mock()
            hub.enabled = True
            hub.ingest_item.return_value = 42
            hub.create_job.return_value = 43

            with patch.object(main, "load_settings", return_value=settings), \
                patch.object(main, "fetch_news", return_value=[make_news()]), \
                patch.object(main, "translate_text", return_value="Переведённый текст"), \
                patch.object(main, "summarize_text", return_value="• Краткое содержание"), \
                patch.object(main, "TelegramPublisher", return_value=telegram), \
                patch.object(main, "VKPublisher", return_value=vk), \
                patch.object(main, "HubClient") as hub_class, \
                patch.object(main.time, "sleep"):
                hub_class.return_value = hub
                hub_class.build_idempotency_key.return_value = "idempotency"
                main.job()

            telegram.publish.assert_not_called()
            hub.ingest_item.assert_called_once()
            hub.create_job.assert_called_once()
            self.assertEqual("disabled", hub.ingest_item.call_args.kwargs["enrichment_status"])
            self.assertTrue(SeenNewsStore(db_path).is_seen("telegram", "https://example.com/news/1"))

    def test_llm_rewrite_is_used_for_automatic_publication(self):
        with tempfile.TemporaryDirectory() as directory:
            db_path = Path(directory) / "news.db"
            settings = make_settings(
                db_path,
                LLM_ENABLED="true",
                LLM_API_KEY="key",
                LLM_REWRITE_ENABLED="true",
            )
            telegram = Mock()
            telegram.enabled = True
            vk = Mock()
            vk.enabled = False
            hub = Mock()
            hub.enabled = False

            with patch.object(main, "load_settings", return_value=settings), \
                patch.object(main, "fetch_news", return_value=[make_news()]), \
                patch.object(main, "translate_text", return_value="Переведённый текст"), \
                patch.object(main, "summarize_text", return_value="• Старое краткое резюме"), \
                patch.object(main, "rewrite_news", return_value="Редакторский пост из нейросети"), \
                patch.object(main, "TelegramPublisher", return_value=telegram), \
                patch.object(main, "VKPublisher", return_value=vk), \
                patch.object(main, "HubClient", return_value=hub), \
                patch.object(main.time, "sleep"):
                main.job()

            published_message = telegram.publish.call_args.args[0]
            self.assertIn("Редакторский пост из нейросети", published_message)
            self.assertNotIn("Старое краткое резюме", published_message)


if __name__ == "__main__":
    unittest.main()
