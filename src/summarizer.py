from __future__ import annotations

import logging
from typing import Optional

from src.llm import chat_completion

logger = logging.getLogger(__name__)


def _simple_summary(text: str, max_chars: int = 420, max_lines: int = 2) -> str:
    normalized = " ".join(text.split())
    if not normalized:
        return ""
    if len(normalized) > max_chars:
        normalized = normalized[:max_chars].rsplit(" ", 1)[0]
    parts = [p.strip() for p in normalized.split(".") if p.strip()]
    if not parts:
        return normalized
    lines: list[str] = []
    for part in parts[: max(1, max_lines)]:
        lines.append(f"• {part}.")
    return "\n".join(lines)


def summarize_text(
    text: str,
    target_language: str,
    llm_api_key: Optional[str] = None,
    llm_model: str = "gpt-4.1-mini",
    llm_base_url: str = "https://api.openai.com/v1",
    prompt_template: Optional[str] = None,
    summary_max_lines: int = 2,
    llm_max_tokens: int = 1000,
) -> str:
    if not text.strip():
        return ""
    summary_max_lines = max(1, summary_max_lines)

    if not llm_api_key:
        return _simple_summary(text, max_lines=summary_max_lines)

    try:
        default_prompt = (
            "You are an editor for Telegram and VK digest posts. Write in '{target_language}'. "
            "Return exactly {summary_max_lines} lines, each line starts with '• '. "
            "Keep it factual and concise, no hype, no markdown, no date/source/link repetition."
        )
        raw_template = prompt_template or default_prompt
        try:
            prompt = raw_template.format(
                target_language=target_language,
                summary_max_lines=summary_max_lines,
            )
        except Exception as ex:
            logger.warning("LLM summary prompt formatting failed; default prompt will be used: %s", ex)
            prompt = default_prompt.format(
                target_language=target_language,
                summary_max_lines=summary_max_lines,
            )
        out = chat_completion(
            api_key=llm_api_key,
            base_url=llm_base_url,
            model=llm_model,
            system_prompt=prompt,
            user_text=text,
            max_tokens=llm_max_tokens,
            temperature=0.1,
        )
        if out:
            logger.info(
                "LLM summary succeeded target_language=%s output_chars=%s lines=%s",
                target_language,
                len(out),
                len([line for line in out.splitlines() if line.strip()]),
            )
            return out
        logger.warning("LLM summary returned empty response; simple summary will be used.")
    except Exception as ex:
        logger.warning("LLM summary generation failed; simple summary will be used: %s", ex)

    return _simple_summary(text, max_lines=summary_max_lines)
