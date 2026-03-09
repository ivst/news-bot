from __future__ import annotations

import hashlib
import logging
from typing import Iterable, Optional

import requests

logger = logging.getLogger("news-bot.hub")


class HubClient:
    def __init__(
        self,
        *,
        base_url: Optional[str],
        api_key: Optional[str],
        timeout_seconds: int = 15,
    ):
        self.base_url = (base_url or "").rstrip("/")
        self.api_key = api_key or ""
        self.timeout_seconds = max(3, timeout_seconds)

    @property
    def enabled(self) -> bool:
        return bool(self.base_url)

    @staticmethod
    def build_idempotency_key(link: str) -> str:
        return hashlib.sha1(link.encode("utf-8")).hexdigest()

    def _headers(self) -> dict:
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["X-Api-Key"] = self.api_key
        return headers

    def ingest_item(
        self,
        *,
        idempotency_key: str,
        source_link: str,
        source_title: str,
        source_text: str,
        translated_title: str,
        translated_summary: str,
        translated_body: str,
        language: str,
        image_url: Optional[str],
        suggested_channels: Iterable[str],
    ) -> int | None:
        if not self.enabled:
            return None
        payload = {
            "idempotency_key": idempotency_key,
            "source_link": source_link,
            "source_title": source_title,
            "source_text": source_text,
            "translated_title": translated_title,
            "translated_summary": translated_summary,
            "translated_body": translated_body,
            "language": language,
            "image_url": image_url,
            "suggested_channels": [c for c in suggested_channels if c in {"vk", "telegram"}],
        }
        resp = requests.post(
            f"{self.base_url}/api/v1/items",
            json=payload,
            headers=self._headers(),
            timeout=self.timeout_seconds,
        )
        resp.raise_for_status()
        body = resp.json()
        item_id = body.get("item_id")
        if isinstance(item_id, int):
            return item_id
        return None

    def create_job(
        self,
        *,
        item_id: int,
        channel: str,
        payload_snapshot: Optional[dict] = None,
    ) -> int | None:
        if not self.enabled:
            return None
        payload = {
            "item_id": item_id,
            "channel": channel,
        }
        if payload_snapshot:
            payload["payload_snapshot"] = payload_snapshot
        resp = requests.post(
            f"{self.base_url}/api/v1/jobs",
            json=payload,
            headers=self._headers(),
            timeout=self.timeout_seconds,
        )
        resp.raise_for_status()
        body = resp.json()
        job_id = body.get("job_id")
        if isinstance(job_id, int):
            return job_id
        return None
