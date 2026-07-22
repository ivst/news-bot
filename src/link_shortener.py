from __future__ import annotations

import logging

import requests


logger = logging.getLogger(__name__)


def shorten_url(url: str, provider: str = "isgd", timeout: int = 15) -> str:
    p = (provider or "isgd").strip().lower()
    try:
        if p == "tinyurl":
            logger.debug("Shorten URL request started provider=tinyurl timeout=%s", timeout)
            resp = requests.get(
                "https://tinyurl.com/api-create.php",
                params={"url": url},
                timeout=timeout,
            )
            resp.raise_for_status()
            short = (resp.text or "").strip()
            if short.startswith("http"):
                logger.info("Shorten URL succeeded provider=tinyurl")
                return short
            logger.warning("Shorten URL returned invalid response provider=tinyurl")
            return url

        logger.debug("Shorten URL request started provider=isgd timeout=%s", timeout)
        resp = requests.get(
            "https://is.gd/create.php",
            params={"format": "simple", "url": url},
            timeout=timeout,
        )
        resp.raise_for_status()
        short = (resp.text or "").strip()
        if short.startswith("http"):
            logger.info("Shorten URL succeeded provider=isgd")
            return short
        logger.warning("Shorten URL returned invalid response provider=isgd")
    except requests.RequestException as ex:
        logger.warning("Shorten URL request failed provider=%s: %s", p, ex)
        return url
    except Exception:
        logger.exception("Shorten URL failed with unexpected error provider=%s", p)
        return url

    return url
