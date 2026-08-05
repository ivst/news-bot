import unittest
from unittest.mock import Mock, patch

from src.llm import chat_completion


class LlmTests(unittest.TestCase):
    @patch("src.llm.requests.post")
    def test_truncated_response_is_rejected(self, post):
        response = Mock()
        response.status_code = 200
        response.raise_for_status.return_value = None
        response.json.return_value = {
            "choices": [{
                "finish_reason": "length",
                "message": {"content": "partial output"},
            }],
            "usage": {"prompt_tokens": 10, "completion_tokens": 20},
        }
        post.return_value = response

        result = chat_completion(
            api_key="key",
            base_url="https://llm.example/v1",
            model="model",
            system_prompt="system",
            user_text="text",
        )

        self.assertIsNone(result)


if __name__ == "__main__":
    unittest.main()
