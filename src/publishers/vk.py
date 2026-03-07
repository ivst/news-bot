from __future__ import annotations

import re
from typing import Optional

import requests


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

    def _upload_wall_photo(self, image_url: str) -> Optional[str]:
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

        image_resp = requests.get(image_url, timeout=30)
        image_resp.raise_for_status()
        content_type = image_resp.headers.get("Content-Type", "image/jpeg")
        files = {"photo": ("news.jpg", image_resp.content, content_type)}
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

        photo_attachment = None
        if image_url:
            try:
                photo_attachment = self._upload_wall_photo(image_url)
            except Exception:
                photo_attachment = None

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
