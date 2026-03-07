from __future__ import annotations

import re
from typing import Optional

import requests


class VKPublisher:
    API_VERSION = "5.199"

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

    def publish(
        self, message: str, attachment_link: Optional[str] = None, source_link: Optional[str] = None
    ) -> None:
        if not self.enabled:
            return

        payload = {
            "owner_id": f"-{self.group_id}",
            "from_group": 1,
            "message": message,
            "access_token": self.access_token,
            "v": self.API_VERSION,
        }
        if attachment_link:
            payload["attachments"] = attachment_link
        resp = requests.post("https://api.vk.com/method/wall.post", data=payload, timeout=30)
        resp.raise_for_status()
        body = resp.json()
        if "error" in body:
            code, msg = self._extract_error(body)
            # Some links cannot be used as attachment previews in VK.
            if payload.get("attachments") and code == 100 and "link_photo_sizing_rule" in msg:
                fallback_payload = dict(payload)
                fallback_payload.pop("attachments", None)
                if source_link:
                    fallback_payload["message"] = self._inject_source_link(message, source_link)
                fallback_resp = requests.post(
                    "https://api.vk.com/method/wall.post", data=fallback_payload, timeout=30
                )
                fallback_resp.raise_for_status()
                fallback_body = fallback_resp.json()
                if "error" in fallback_body:
                    raise RuntimeError(f"VK API error: {fallback_body['error']}")
                return
            raise RuntimeError(f"VK API error: {body['error']}")
