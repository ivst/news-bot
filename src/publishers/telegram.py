from __future__ import annotations

from typing import Optional

import requests


class TelegramPublisher:
    def __init__(self, bot_token: Optional[str], chat_id: Optional[str]):
        self.bot_token = bot_token
        self.chat_id = chat_id

    @property
    def enabled(self) -> bool:
        return bool(self.bot_token and self.chat_id)

    def _send_message(self, message: str) -> None:
        url = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"
        payload = {
            "chat_id": self.chat_id,
            "text": message,
            "parse_mode": "HTML",
            "disable_web_page_preview": False,
        }
        resp = requests.post(url, json=payload, timeout=30)
        resp.raise_for_status()

    def _send_photo(self, message: str, image_url: str) -> None:
        # Telegram caption is limited to 1024 characters.
        caption = message
        if len(caption) > 1024:
            caption = caption[:1014].rsplit(" ", 1)[0] + "..."
        url = f"https://api.telegram.org/bot{self.bot_token}/sendPhoto"
        payload = {
            "chat_id": self.chat_id,
            "photo": image_url,
            "caption": caption,
            "parse_mode": "HTML",
        }
        resp = requests.post(url, json=payload, timeout=30)
        resp.raise_for_status()

    def publish(self, message: str, image_url: Optional[str] = None) -> None:
        if not self.enabled:
            return

        if image_url:
            try:
                self._send_photo(message, image_url)
                return
            except requests.RequestException:
                # Fall back to plain text if Telegram can't fetch the image URL.
                pass

        self._send_message(message)
