from __future__ import annotations

from typing import Optional

from src.llm import chat_completion


def _simple_summary(text: str, max_chars: int = 420) -> str:
    normalized = " ".join(text.split())
    if len(normalized) <= max_chars:
        return normalized
    cut = normalized[:max_chars].rsplit(" ", 1)[0]
    return cut + "..."


def summarize_text(
    text: str,
    target_language: str,
    llm_api_key: Optional[str] = None,
    llm_model: str = "gpt-4.1-mini",
    llm_base_url: str = "https://api.openai.com/v1",
) -> str:
    if not text.strip():
        return ""

    if not llm_api_key:
        return _simple_summary(text)

    try:
        prompt = (
            f"You are a news editor. Create a short, factual summary in language '{target_language}'. "
            "Length: 2-3 sentences, no hype, no markdown."
        )
        out = chat_completion(
            api_key=llm_api_key,
            base_url=llm_base_url,
            model=llm_model,
            system_prompt=prompt,
            user_text=text,
            max_tokens=220,
            temperature=0.1,
        )
        if out:
            return out
    except Exception:
        pass

    return _simple_summary(text)
