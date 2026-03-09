from __future__ import annotations

import logging
from typing import Optional

import requests

logger = logging.getLogger(__name__)


def _ensure_telegram_ok(resp: requests.Response) -> None:
    resp.raise_for_status()
    try:
        body = resp.json()
    except ValueError as ex:
        raise requests.RequestException("Telegram API returned non-JSON response") from ex
    if isinstance(body, dict) and body.get("ok") is False:
        desc = str(body.get("description") or "unknown Telegram API error")
        code = body.get("error_code")
        raise requests.RequestException(f"Telegram API error ({code}): {desc}")


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
        _ensure_telegram_ok(resp)

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
        _ensure_telegram_ok(resp)

    def _send_photo_upload(self, message: str, image_url: str) -> None:
        caption = message
        if len(caption) > 1024:
            caption = caption[:1014].rsplit(" ", 1)[0] + "..."

        image_resp = requests.get(image_url, timeout=30)
        image_resp.raise_for_status()
        content_type = image_resp.headers.get("content-type", "")
        if not content_type.startswith("image/"):
            raise requests.RequestException(f"unexpected content-type: {content_type}")

        tg_url = f"https://api.telegram.org/bot{self.bot_token}/sendPhoto"
        data = {
            "chat_id": str(self.chat_id),
            "caption": caption,
            "parse_mode": "HTML",
        }
        files = {
            "photo": ("image.jpg", image_resp.content, content_type),
        }
        resp = requests.post(tg_url, data=data, files=files, timeout=30)
        _ensure_telegram_ok(resp)

    def publish(self, message: str, image_url: Optional[str] = None) -> None:
        if not self.enabled:
            return

        if image_url:
            try:
                self._send_photo(message, image_url)
                return
            except requests.RequestException as exc:
                logger.warning("Telegram sendPhoto by URL failed, trying upload fallback: %s", exc)
            try:
                self._send_photo_upload(message, image_url)
                return
            except requests.RequestException as exc:
                logger.warning("Telegram sendPhoto upload fallback failed: %s", exc)

        self._send_message(message)
