from __future__ import annotations

import base64
import logging
import mimetypes
import os
from typing import Optional
from urllib.parse import urlparse

import requests

logger = logging.getLogger("news-bot.bitrix24")


class Bitrix24Publisher:
    """Publisher for the Bitrix24 News Feed (log.blogpost.add)."""

    def __init__(
        self,
        webhook_url: Optional[str],
        destination: list[str] | None = None,
        tags: str = "",
        show_source: bool = True,
        image_upload_enabled: bool = True,
        timeout_seconds: int = 30,
    ):
        self.webhook_url = (webhook_url or "").strip()
        self.destination = [str(value).strip() for value in (destination or ["UA"]) if str(value).strip()]
        self.tags = tags.strip()
        self.show_source = show_source
        self.image_upload_enabled = image_upload_enabled
        self.timeout_seconds = max(3, timeout_seconds)

    @property
    def enabled(self) -> bool:
        return bool(self.webhook_url and self.destination)

    @staticmethod
    def _image_filename(image_url: str, content_type: str) -> str:
        name = os.path.basename(urlparse(image_url).path).strip()
        if not name or "." not in name:
            extension = mimetypes.guess_extension(content_type.split(";", 1)[0].strip()) or ".jpg"
            name = f"news{extension}"
        return name[:150]

    def _download_image(self, image_url: str) -> list[str] | None:
        try:
            response = requests.get(
                image_url,
                timeout=self.timeout_seconds,
                headers={"User-Agent": "Mozilla/5.0 (news-bot)"},
            )
            response.raise_for_status()
            content_type = (response.headers.get("Content-Type") or "").lower()
            if not content_type.startswith("image/"):
                raise RuntimeError(f"unexpected image content-type: {content_type or 'empty'}")
            if not response.content:
                raise RuntimeError("image response is empty")
            filename = self._image_filename(image_url, content_type)
            encoded = base64.b64encode(response.content).decode("ascii")
            return [filename, encoded]
        except Exception as ex:
            logger.warning("Bitrix24 image download failed url=%s error=%s", image_url, ex)
            return None

    def publish(
        self,
        title: str,
        message: str,
        source_link: Optional[str] = None,
        image_url: Optional[str] = None,
    ) -> int | None:
        if not self.enabled:
            return None

        post_message = message.strip()
        if self.show_source and source_link and "Источник:" not in post_message:
            post_message = f"{post_message}\n\nИсточник: {source_link}"
        payload: dict = {
            "POST_TITLE": title.strip(),
            "POST_MESSAGE": post_message,
            "DEST": self.destination,
            "PARSE_PREVIEW": "Y" if source_link else "N",
        }
        if self.tags:
            payload["TAGS"] = self.tags

        if image_url and self.image_upload_enabled:
            file_payload = self._download_image(image_url)
            if file_payload:
                payload["FILES"] = [file_payload]

        response = requests.post(self.webhook_url, json=payload, timeout=self.timeout_seconds)
        if "FILES" in payload and response.status_code >= 400:
            logger.warning("Bitrix24 rejected post with image; retrying without image status=%s", response.status_code)
            payload.pop("FILES", None)
            response = requests.post(self.webhook_url, json=payload, timeout=self.timeout_seconds)
        response.raise_for_status()
        body = response.json()
        if not isinstance(body, dict):
            raise RuntimeError("Bitrix24 API returned invalid JSON body")
        if body.get("error"):
            if "FILES" in payload:
                logger.warning("Bitrix24 rejected image attachment; retrying post without image")
                payload.pop("FILES", None)
                response = requests.post(self.webhook_url, json=payload, timeout=self.timeout_seconds)
                response.raise_for_status()
                body = response.json()
                if not isinstance(body, dict):
                    raise RuntimeError("Bitrix24 API returned invalid JSON body")
            if body.get("error"):
                raise RuntimeError(
                    f"Bitrix24 API error: {body.get('error')} {body.get('error_description') or ''}".strip()
                )
        result = body.get("result")
        logger.info("Bitrix24 News Feed post created post_id=%s", result)
        return int(result) if isinstance(result, int) else None
