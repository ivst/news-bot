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
_MONTH_HINTS = {
    "jan",
    "january",
    "feb",
    "february",
    "mar",
    "march",
    "apr",
    "april",
    "may",
    "jun",
    "june",
    "jul",
    "july",
    "aug",
    "august",
    "sep",
    "sept",
    "september",
    "oct",
    "october",
    "nov",
    "november",
    "dec",
    "december",
    "январ",
    "феврал",
    "март",
    "апрел",
    "мая",
    "май",
    "июн",
    "июл",
    "август",
    "сентябр",
    "октябр",
    "ноябр",
    "декабр",
}
_INLINE_META_PATTERNS = [
    # Bracketed source/date fragments: [Source = 11 Mar 2026], [Source: ...]
    r"\[\s*[^\]\n]{0,120}(?:=|:|\||｜)[^\]\n]{0,120}\]",
]


def _looks_like_feed_meta_line(line: str) -> bool:
    compact = " ".join(line.lower().split())
    if not compact:
        return False
    if re.fullmatch(r"[\[\]\(\)（）\s]+", compact):
        return True
    if len(compact) > 180:
        return False

    has_meta_sep = "=" in compact or "｜" in compact or " | " in compact or "source:" in compact or "источник:" in compact
    has_year = bool(re.search(r"\b20\d{2}\b", compact))
    has_day_number = bool(re.search(r"\b\d{1,2}\b", compact))
    has_month_hint = any(token in compact for token in _MONTH_HINTS)
    if has_meta_sep and (has_year or (has_day_number and has_month_hint)):
        return True
    return False


def strip_ui_noise(text: str) -> str:
    if not text:
        return ""

    cleaned = text
    for pattern in _NOISE_PATTERNS:
        cleaned = re.sub(pattern, " ", cleaned, flags=re.IGNORECASE)
    for pattern in _INLINE_META_PATTERNS:
        cleaned = re.sub(pattern, " ", cleaned, flags=re.IGNORECASE)

    # Keep line breaks for platform-specific formatting.
    cleaned = cleaned.replace("\r\n", "\n").replace("\r", "\n")
    lines = []
    for line in cleaned.split("\n"):
        if _looks_like_feed_meta_line(line):
            continue
        normalized = re.sub(r"[ \t]{2,}", " ", line)
        # Drop only orphan bracket tokens like "] text" or "[ text",
        # but keep structured tags such as "[Видео] ...".
        normalized = re.sub(r"^(?:[•\-]\s*)?[\]\[]\s+(?=\S)", "", normalized)
        normalized = re.sub(r"[ \t]+([,.;:!?])", r"\1", normalized)
        normalized = normalized.strip()
        if not normalized:
            continue
        lines.append(normalized)

    cleaned = "\n".join(lines)
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
    return cleaned.strip()
