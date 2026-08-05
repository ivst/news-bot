import unittest
from unittest.mock import patch

from src.rewriter import rewrite_news


class RewriterTests(unittest.TestCase):
    @patch("src.rewriter.chat_completion", return_value="Переработанный текст новости")
    def test_rewrite_uses_configured_prompt_and_returns_post(self, completion):
        result = rewrite_news(
            "Source article",
            target_language="ru",
            api_key="key",
            model="model",
            base_url="https://llm.example/v1",
            prompt_template="Rewrite in {target_language}, max {rewrite_max_chars} chars.",
            max_tokens=100,
            max_chars=1000,
        )

        self.assertEqual("Переработанный текст новости", result)
        self.assertIn("Rewrite in ru, max 1000 chars.", completion.call_args.kwargs["system_prompt"])

    @patch("src.rewriter.chat_completion", side_effect=RuntimeError("provider down"))
    def test_rewrite_failure_returns_none_for_summary_fallback(self, _completion):
        self.assertIsNone(
            rewrite_news(
                "Source article",
                target_language="ru",
                api_key="key",
                model="model",
                base_url="https://llm.example/v1",
                prompt_template="",
                max_tokens=100,
                max_chars=1000,
            )
        )


if __name__ == "__main__":
    unittest.main()
