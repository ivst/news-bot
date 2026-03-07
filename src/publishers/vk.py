from __future__ import annotations

import json
import logging
import re
from io import BytesIO
from typing import Optional
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup
from PIL import Image

logger = logging.getLogger("news-bot.vk")


class VKPublisher:
    API_VERSION = "5.199"
    API_BASE = "https://api.vk.com/method"

    def __init__(self, group_id: Optional[str], access_token: Optional[str]):
        self.group_id = group_id
        self.access_token = access_token

    @property
    def enabled(self) -> bool:
        return bool(self.group_id and self.access_token)

    @staticmethod
    def _extract_error(body: dict) -> tuple[int | None, str]:
        err = body.get("error") if isinstance(body, dict) else None
        if not isinstance(err, dict):
            return None, ""
        code = err.get("error_code")
        msg = str(err.get("error_msg") or "")
        return code if isinstance(code, int) else None, msg

    @staticmethod
    def _inject_source_link(message: str, source_link: str) -> str:
        # Replace trailing "Источник" marker instead of appending a duplicate line.
        out = re.sub(r"(?:\n\s*)?Источник\s*$", "", message.strip(), flags=re.IGNORECASE).strip()
        return f"{out}\n\nИсточник: {source_link}"

    def _api_call(self, method: str, payload: dict) -> dict:
        resp = requests.post(f"{self.API_BASE}/{method}", data=payload, timeout=30)
        resp.raise_for_status()
        body = resp.json()
        if "error" in body:
            raise RuntimeError(f"VK API error: {body['error']}")
        return body.get("response") or {}

    @staticmethod
    def _to_jpeg_if_needed(image_bytes: bytes, content_type: str, image_url: str) -> tuple[bytes, str]:
        lower_ct = (content_type or "").lower()
        lower_url = image_url.lower()
        needs_convert = (
            "image/webp" in lower_ct
            or "image/avif" in lower_ct
            or "image/svg" in lower_ct
            or lower_url.endswith(".webp")
            or lower_url.endswith(".avif")
            or lower_url.endswith(".svg")
        )
        if not needs_convert:
            return image_bytes, content_type or "image/jpeg"

        img = Image.open(BytesIO(image_bytes)).convert("RGB")
        out = BytesIO()
        img.save(out, format="JPEG", quality=90, optimize=True)
        return out.getvalue(), "image/jpeg"

    def _upload_wall_photo(self, image_url: str, source_link: Optional[str] = None) -> Optional[str]:
        if not image_url:
            return None

        upload_server = self._api_call(
            "photos.getWallUploadServer",
            {
                "group_id": self.group_id,
                "access_token": self.access_token,
                "v": self.API_VERSION,
            },
        )
        upload_url = str(upload_server.get("upload_url") or "")
        if not upload_url:
            return None

        headers = {"User-Agent": "Mozilla/5.0 (news-bot)"}
        image_resp = requests.get(image_url, timeout=30, headers=headers)
        if image_resp.status_code >= 400 and source_link:
            headers["Referer"] = source_link
            image_resp = requests.get(image_url, timeout=30, headers=headers)
        image_resp.raise_for_status()

        raw_bytes = image_resp.content
        raw_type = image_resp.headers.get("Content-Type", "image/jpeg")
        try:
            upload_bytes, upload_type = self._to_jpeg_if_needed(raw_bytes, raw_type, image_url)
        except Exception as ex:
            logger.warning("VK image convert failed, using original bytes for %s: %s", image_url, ex)
            upload_bytes, upload_type = raw_bytes, raw_type

        files = {"photo": ("news.jpg", upload_bytes, upload_type)}
        upload_resp = requests.post(upload_url, files=files, timeout=60)
        upload_resp.raise_for_status()
        upload_body = upload_resp.json()

        saved = self._api_call(
            "photos.saveWallPhoto",
            {
                "group_id": self.group_id,
                "photo": upload_body.get("photo"),
                "server": upload_body.get("server"),
                "hash": upload_body.get("hash"),
                "access_token": self.access_token,
                "v": self.API_VERSION,
            },
        )
        if not isinstance(saved, list) or not saved:
            return None
        first = saved[0]
        owner_id = first.get("owner_id")
        photo_id = first.get("id")
        if owner_id is None or photo_id is None:
            return None
        return f"photo{owner_id}_{photo_id}"

    @staticmethod
    def _extract_image_from_html(page_url: str, html_text: str) -> Optional[str]:
        soup = BeautifulSoup(html_text, "html.parser")
        for selector, attr in [
            ("meta[property='og:image']", "content"),
            ("meta[name='og:image']", "content"),
            ("meta[name='twitter:image']", "content"),
            ("meta[property='twitter:image']", "content"),
        ]:
            tag = soup.select_one(selector)
            if tag and tag.get(attr):
                return urljoin(page_url, str(tag.get(attr)).strip())
        img = soup.find("img")
        if img and img.get("src"):
            return urljoin(page_url, str(img.get("src")).strip())

        # JSON-LD fallback: "image" can be string/list/object
        for script in soup.select("script[type='application/ld+json']"):
            raw = script.get_text(strip=True)
            if not raw:
                continue
            try:
                data = json.loads(raw)
            except Exception:
                continue

            def pick(obj) -> Optional[str]:
                if isinstance(obj, str):
                    return urljoin(page_url, obj.strip())
                if isinstance(obj, list):
                    for it in obj:
                        got = pick(it)
                        if got:
                            return got
                    return None
                if isinstance(obj, dict):
                    if isinstance(obj.get("url"), str):
                        return urljoin(page_url, obj["url"].strip())
                    return pick(obj.get("image"))
                return None

            got = pick(data)
            if got:
                return got
        return None

    def _discover_image_url(self, image_url: Optional[str], article_url: Optional[str]) -> Optional[str]:
        if image_url:
            return image_url
        if not article_url:
            return None
        try:
            page_resp = requests.get(
                article_url,
                timeout=30,
                allow_redirects=True,
                headers={"User-Agent": "Mozilla/5.0 (news-bot)"},
            )
            page_resp.raise_for_status()
            final_url = page_resp.url or article_url
            return self._extract_image_from_html(final_url, page_resp.text)
        except Exception as ex:
            logger.warning("VK image discovery failed for %s: %s", article_url, ex)
            return None

    def _wall_post(self, payload: dict) -> dict:
        resp = requests.post(f"{self.API_BASE}/wall.post", data=payload, timeout=30)
        resp.raise_for_status()
        return resp.json()

    def publish(
        self,
        message: str,
        attachment_link: Optional[str] = None,
        source_link: Optional[str] = None,
        image_url: Optional[str] = None,
    ) -> None:
        if not self.enabled:
            return

        discovered_image = self._discover_image_url(image_url, attachment_link or source_link)
        photo_attachment = None
        if discovered_image:
            try:
                photo_attachment = self._upload_wall_photo(discovered_image, source_link=source_link)
            except Exception as ex:
                logger.warning("VK photo upload failed for %s: %s", discovered_image, ex)
                photo_attachment = None
        else:
            logger.info("VK image not found for post source: %s", source_link or attachment_link)

        attachments: list[str] = []
        if photo_attachment:
            attachments.append(photo_attachment)
        if attachment_link:
            attachments.append(attachment_link)

        payload = {
            "owner_id": f"-{self.group_id}",
            "from_group": 1,
            "message": message,
            "access_token": self.access_token,
            "v": self.API_VERSION,
        }
        if attachments:
            payload["attachments"] = ",".join(attachments)

        body = self._wall_post(payload)
        if "error" in body:
            code, msg = self._extract_error(body)
            # Some links cannot be used as attachment previews in VK.
            if payload.get("attachments") and code == 100 and "link_photo_sizing_rule" in msg and attachment_link:
                fallback_payload = dict(payload)
                fallback_attachments = [a for a in attachments if a != attachment_link]
                if fallback_attachments:
                    fallback_payload["attachments"] = ",".join(fallback_attachments)
                else:
                    fallback_payload.pop("attachments", None)
                if source_link:
                    fallback_payload["message"] = self._inject_source_link(message, source_link)
                fallback_body = self._wall_post(fallback_payload)
                if "error" in fallback_body:
                    raise RuntimeError(f"VK API error: {fallback_body['error']}")
                return
            raise RuntimeError(f"VK API error: {body['error']}")
