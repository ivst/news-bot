from __future__ import annotations

import logging
import time
from typing import Optional

import requests


logger = logging.getLogger("news-bot.llm")


def chat_completion(
    *,
    api_key: str,
    base_url: str,
    model: str,
    system_prompt: str,
    user_text: str,
    timeout: int = 45,
    temperature: float = 0.2,
    max_tokens: int = 300,
) -> Optional[str]:
    endpoint = f"{base_url.rstrip('/')}/chat/completions"
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_text},
        ],
        "temperature": temperature,
        "max_tokens": max_tokens,
    }

    started_at = time.monotonic()
    logger.debug(
        "LLM request started endpoint=%s model=%s timeout=%s temperature=%s max_tokens=%s user_chars=%s",
        endpoint,
        model,
        timeout,
        temperature,
        max_tokens,
        len(user_text or ""),
    )

    try:
        response = requests.post(
            endpoint,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json=payload,
            timeout=timeout,
        )
        response.raise_for_status()
    except requests.RequestException:
        elapsed_ms = int((time.monotonic() - started_at) * 1000)
        logger.exception(
            "LLM HTTP request failed endpoint=%s model=%s elapsed_ms=%s",
            endpoint,
            model,
            elapsed_ms,
        )
        raise

    try:
        data = response.json()
    except ValueError:
        elapsed_ms = int((time.monotonic() - started_at) * 1000)
        logger.exception(
            "LLM response JSON decode failed endpoint=%s model=%s status=%s elapsed_ms=%s",
            endpoint,
            model,
            response.status_code,
            elapsed_ms,
        )
        raise

    choices = data.get("choices") or []
    if not choices:
        elapsed_ms = int((time.monotonic() - started_at) * 1000)
        logger.warning(
            "LLM response has no choices endpoint=%s model=%s status=%s elapsed_ms=%s",
            endpoint,
            model,
            response.status_code,
            elapsed_ms,
        )
        return None

    choice0 = choices[0] if isinstance(choices[0], dict) else {}
    finish_reason = choice0.get("finish_reason")
    usage = data.get("usage") if isinstance(data.get("usage"), dict) else {}
    usage_prompt_tokens = usage.get("prompt_tokens")
    usage_completion_tokens = usage.get("completion_tokens")
    usage_total_tokens = usage.get("total_tokens")
    choice0_meta = {
        "index": choice0.get("index"),
        "finish_reason": finish_reason,
        "logprobs": choice0.get("logprobs"),
    }

    message = choice0.get("message") or {}
    content = message.get("content")
    if isinstance(content, str):
        content = content.strip()
        elapsed_ms = int((time.monotonic() - started_at) * 1000)
        logger.info(
            "LLM response received endpoint=%s model=%s status=%s elapsed_ms=%s content_chars=%s "
            "finish_reason=%s usage_prompt_tokens=%s usage_completion_tokens=%s usage_total_tokens=%s",
            endpoint,
            model,
            response.status_code,
            elapsed_ms,
            len(content),
            finish_reason,
            usage_prompt_tokens,
            usage_completion_tokens,
            usage_total_tokens,
        )
        if not content:
            logger.warning(
                "LLM returned empty string content endpoint=%s model=%s status=%s finish_reason=%s choice0_meta=%s",
                endpoint,
                model,
                response.status_code,
                finish_reason,
                choice0_meta,
            )
        return content or None

    elapsed_ms = int((time.monotonic() - started_at) * 1000)
    logger.warning(
        "LLM response content is not string endpoint=%s model=%s status=%s elapsed_ms=%s content_type=%s "
        "finish_reason=%s choice0_meta=%s usage_prompt_tokens=%s usage_completion_tokens=%s usage_total_tokens=%s",
        endpoint,
        model,
        response.status_code,
        elapsed_ms,
        type(content).__name__,
        finish_reason,
        choice0_meta,
        usage_prompt_tokens,
        usage_completion_tokens,
        usage_total_tokens,
    )
    return None
