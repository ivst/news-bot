from __future__ import annotations

import hashlib
import logging
import time
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
        endpoint = f"{self.base_url}/api/v1/items"
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
        started_at = time.monotonic()
        logger.debug(
            "Hub ingest request started endpoint=%s timeout=%s idempotency_key=%s",
            endpoint,
            self.timeout_seconds,
            idempotency_key,
        )
        try:
            resp = requests.post(
                endpoint,
                json=payload,
                headers=self._headers(),
                timeout=self.timeout_seconds,
            )
            resp.raise_for_status()
            body = resp.json()
        except requests.RequestException:
            elapsed_ms = int((time.monotonic() - started_at) * 1000)
            logger.exception(
                "Hub ingest request failed endpoint=%s elapsed_ms=%s idempotency_key=%s",
                endpoint,
                elapsed_ms,
                idempotency_key,
            )
            raise
        except ValueError:
            elapsed_ms = int((time.monotonic() - started_at) * 1000)
            logger.exception(
                "Hub ingest response JSON decode failed endpoint=%s status=%s elapsed_ms=%s idempotency_key=%s",
                endpoint,
                resp.status_code,
                elapsed_ms,
                idempotency_key,
            )
            raise

        item_id = body.get("item_id")
        if isinstance(item_id, int):
            elapsed_ms = int((time.monotonic() - started_at) * 1000)
            logger.info(
                "Hub ingest succeeded endpoint=%s status=%s elapsed_ms=%s item_id=%s",
                endpoint,
                resp.status_code,
                elapsed_ms,
                item_id,
            )
            return item_id
        logger.warning(
            "Hub ingest response missing item_id endpoint=%s status=%s",
            endpoint,
            resp.status_code,
        )
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
        endpoint = f"{self.base_url}/api/v1/jobs"
        payload = {
            "item_id": item_id,
            "channel": channel,
        }
        if payload_snapshot:
            payload["payload_snapshot"] = payload_snapshot
        started_at = time.monotonic()
        logger.debug(
            "Hub job create request started endpoint=%s timeout=%s item_id=%s channel=%s",
            endpoint,
            self.timeout_seconds,
            item_id,
            channel,
        )
        try:
            resp = requests.post(
                endpoint,
                json=payload,
                headers=self._headers(),
                timeout=self.timeout_seconds,
            )
            resp.raise_for_status()
            body = resp.json()
        except requests.RequestException:
            elapsed_ms = int((time.monotonic() - started_at) * 1000)
            logger.exception(
                "Hub job create request failed endpoint=%s elapsed_ms=%s item_id=%s channel=%s",
                endpoint,
                elapsed_ms,
                item_id,
                channel,
            )
            raise
        except ValueError:
            elapsed_ms = int((time.monotonic() - started_at) * 1000)
            logger.exception(
                "Hub job create response JSON decode failed endpoint=%s status=%s elapsed_ms=%s item_id=%s channel=%s",
                endpoint,
                resp.status_code,
                elapsed_ms,
                item_id,
                channel,
            )
            raise

        job_id = body.get("job_id")
        if isinstance(job_id, int):
            elapsed_ms = int((time.monotonic() - started_at) * 1000)
            logger.info(
                "Hub job create succeeded endpoint=%s status=%s elapsed_ms=%s job_id=%s item_id=%s channel=%s",
                endpoint,
                resp.status_code,
                elapsed_ms,
                job_id,
                item_id,
                channel,
            )
            return job_id
        logger.warning(
            "Hub job create response missing job_id endpoint=%s status=%s item_id=%s channel=%s",
            endpoint,
            resp.status_code,
            item_id,
            channel,
        )
        return None
