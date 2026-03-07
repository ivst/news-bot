from __future__ import annotations

import re


# Common website UI phrases that sometimes leak into RSS snippets.
_NOISE_PATTERNS = [
    r"\bссылка\s+скопирована\b",
    r"\bразмер\s+шрифта\s+уменьшен\b",
    r"\bразмер\s+шрифта\s+увеличен\b",
    r"\blink\s+copied\b",
    r"\bfont\s+size\s+(?:decreased|increased)\b",
    r"\bcopy\s+link\b",
]


def strip_ui_noise(text: str) -> str:
    if not text:
        return ""

    cleaned = text
    for pattern in _NOISE_PATTERNS:
        cleaned = re.sub(pattern, " ", cleaned, flags=re.IGNORECASE)

    # Normalize separator leftovers after phrase removal.
    cleaned = re.sub(r"\s{2,}", " ", cleaned)
    cleaned = re.sub(r"\s+([,.;:!?])", r"\1", cleaned)
    return cleaned.strip(" -|,.;:!?")
