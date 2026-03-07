from __future__ import annotations

import requests


def shorten_url(url: str, provider: str = "isgd", timeout: int = 15) -> str:
    p = (provider or "isgd").strip().lower()
    try:
        if p == "tinyurl":
            resp = requests.get(
                "https://tinyurl.com/api-create.php",
                params={"url": url},
                timeout=timeout,
            )
            resp.raise_for_status()
            short = (resp.text or "").strip()
            if short.startswith("http"):
                return short
            return url

        resp = requests.get(
            "https://is.gd/create.php",
            params={"format": "simple", "url": url},
            timeout=timeout,
        )
        resp.raise_for_status()
        short = (resp.text or "").strip()
        if short.startswith("http"):
            return short
    except Exception:
        return url

    return url
