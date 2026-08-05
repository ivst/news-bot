from __future__ import annotations

import logging
from typing import Optional

from src.llm import chat_completion
from src.text_cleaner import strip_ui_noise

logger = logging.getLogger("news-bot.rewriter")


def rewrite_news(
    text: str,
    *,
    target_language: str,
    api_key: Optional[str],
    model: str,
    base_url: str,
    prompt_template: str,
    max_tokens: int,
    max_chars: int,
) -> Optional[str]:
    if not text.strip() or not api_key:
        return None

    default_prompt = (
        "You are a factual news editor. Rewrite the material in '{target_language}' "
        "as a ready-to-publish news post. Use only facts from the material, do not invent details, "
        "do not add a title, source, link, or editorial commentary. Keep it concise and within "
        "{rewrite_max_chars} characters. Return only the rewritten post."
    )
    try:
        prompt = (prompt_template or default_prompt).format(
            target_language=target_language,
            rewrite_max_chars=max_chars,
        )
    except Exception as ex:
        logger.warning("LLM rewrite prompt formatting failed; default prompt will be used: %s", ex)
        prompt = default_prompt.format(target_language=target_language, rewrite_max_chars=max_chars)

    try:
        result = chat_completion(
            api_key=api_key,
            base_url=base_url,
            model=model,
            system_prompt=prompt,
            user_text=text,
            temperature=0.2,
            max_tokens=max_tokens,
        )
    except Exception as ex:
        logger.warning("LLM rewrite failed; original summary will be used: %s", ex)
        return None

    if not result:
        return None
    cleaned = strip_ui_noise(result).strip()
    if not cleaned:
        return None
    return cleaned[:max(200, max_chars)].strip()
