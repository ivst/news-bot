from __future__ import annotations

from typing import Optional

from deep_translator import GoogleTranslator

from src.llm import chat_completion


def translate_text(
    text: str,
    target_language: str,
    llm_api_key: Optional[str] = None,
    llm_model: str = "gpt-4.1-mini",
    llm_base_url: str = "https://api.openai.com/v1",
    use_llm_translation: bool = False,
) -> str:
    if not text.strip():
        return text

    if use_llm_translation and llm_api_key:
        try:
            out = chat_completion(
                api_key=llm_api_key,
                base_url=llm_base_url,
                model=llm_model,
                system_prompt=(
                    f"Translate user text to '{target_language}'. "
                    "Return only translated text without explanations."
                ),
                user_text=text,
                temperature=0.0,
                max_tokens=700,
            )
            if out:
                return out
        except Exception:
            pass

    try:
        return GoogleTranslator(source="auto", target=target_language).translate(text)
    except Exception:
        return text
