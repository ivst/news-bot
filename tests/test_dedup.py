import tempfile
import unittest
from pathlib import Path

from main import _find_similar_recent
from src.storage import SeenNewsStore


class DedupTests(unittest.TestCase):
    def test_paraphrased_event_is_detected_in_recent_window(self):
        with tempfile.TemporaryDirectory() as directory:
            store = SeenNewsStore(Path(directory) / "news.db")
            store.record_attempt(
                channel="telegram",
                link="https://example.com/old",
                title="Company announces a new project in Tokyo",
                summary="The company approved a new project in Tokyo after today's meeting.",
                text_norm="company approved a new project in tokyo after todays meeting",
                status="published",
            )

            matched, score, link, reason = _find_similar_recent(
                store,
                channel="telegram",
                title="New Tokyo project approved by the company",
                summary="The company has approved its Tokyo project following a meeting today.",
                text_norm="company has approved its tokyo project following a meeting today",
                window=100,
                threshold=0.90,
                token_threshold=0.72,
                min_overlap_tokens=6,
            )

            self.assertTrue(matched, reason)
            self.assertGreater(score, 0.5)
            self.assertEqual("https://example.com/old", link)

    def test_unrelated_news_is_not_detected(self):
        with tempfile.TemporaryDirectory() as directory:
            store = SeenNewsStore(Path(directory) / "news.db")
            store.record_attempt(
                channel="telegram",
                link="https://example.com/old",
                title="Weather forecast for northern regions",
                summary="Heavy snow is expected in the northern regions this weekend.",
                text_norm="heavy snow expected northern regions weekend",
                status="published",
            )

            matched, _, _, _ = _find_similar_recent(
                store,
                channel="telegram",
                title="Technology company opens an office in Tokyo",
                summary="The company opened a new research office in Tokyo today.",
                text_norm="company opened new research office tokyo today",
                window=100,
                threshold=0.90,
                token_threshold=0.72,
                min_overlap_tokens=6,
            )

            self.assertFalse(matched)


if __name__ == "__main__":
    unittest.main()
