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

    # Keep line breaks for platform-specific formatting.
    cleaned = cleaned.replace("\r\n", "\n").replace("\r", "\n")
    lines = []
    for line in cleaned.split("\n"):
        normalized = re.sub(r"[ \t]{2,}", " ", line)
        normalized = re.sub(r"[ \t]+([,.;:!?])", r"\1", normalized)
        lines.append(normalized.strip())

    cleaned = "\n".join(lines)
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
    return cleaned.strip()
