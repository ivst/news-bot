import unittest
from unittest.mock import patch

from src.translator import translate_text


class TranslatorTests(unittest.TestCase):
    @patch("src.translator.GoogleTranslator")
    def test_long_google_translation_is_split_into_chunks(self, translator_class):
        translator = translator_class.return_value
        translator.translate.side_effect = lambda chunk: "перевод " + chunk[:20]
        text = "\n\n".join("A long paragraph with useful context. " * 150 for _ in range(2))

        result = translate_text(text, "ru")

        self.assertTrue(result.startswith("перевод"))
        self.assertGreater(translator.translate.call_count, 1)


if __name__ == "__main__":
    unittest.main()
