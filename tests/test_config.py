import os
import unittest
from unittest.mock import patch

from src.config import load_settings


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


if __name__ == "__main__":
    unittest.main()
