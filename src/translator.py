from __future__ import annotations

import re
from typing import Optional

from deep_translator import GoogleTranslator

from src.llm import chat_completion


def _looks_like_target_language(text: str, target_language: str) -> bool:
    lang = (target_language or "").strip().lower().split("-", 1)[0]
    if lang in {"ru", "uk", "bg"}:
        return bool(re.search(r"[А-Яа-яЁёІіЇїЄєҐґ]", text))
    if lang == "en":
        return bool(re.search(r"[A-Za-z]", text))
    if lang == "ja":
        return bool(re.search(r"[\u3040-\u30ff\u4e00-\u9fff]", text))
    if lang in {"zh", "zh_cn", "zh_tw"}:
        return bool(re.search(r"[\u4e00-\u9fff]", text))
    if lang == "ko":
        return bool(re.search(r"[\uac00-\ud7af]", text))
    return True


def translate_text(
    text: str,
    target_language: str,
    llm_api_key: Optional[str] = None,
    llm_model: str = "gpt-4.1-mini",
    llm_base_url: str = "https://api.openai.com/v1",
    use_llm_translation: bool = False,
) -> Optional[str]:
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
            if out and _looks_like_target_language(out, target_language):
                return out
        except Exception:
            pass

    try:
        out = GoogleTranslator(source="auto", target=target_language).translate(text)
        if out and _looks_like_target_language(out, target_language):
            return out
    except Exception:
        pass

    return None
