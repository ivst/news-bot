from __future__ import annotations

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

    def publish(self, message: str, attachment_link: Optional[str] = None) -> None:
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
            raise RuntimeError(f"VK API error: {body['error']}")
