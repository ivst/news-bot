from __future__ import annotations

import sqlite3
from pathlib import Path


class SeenNewsStore:
    def __init__(self, db_path: Path):
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self.db_path)

    def _init_db(self) -> None:
        with self._connect() as conn:
            # Per-channel deduplication table.
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS published_news_by_channel (
                    channel TEXT NOT NULL,
                    link TEXT NOT NULL,
                    published_at TEXT NOT NULL
                    ,PRIMARY KEY (channel, link)
                )
                """
            )
            # Backward-compatible migration from the old schema.
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS published_news (
                    link TEXT PRIMARY KEY,
                    published_at TEXT NOT NULL
                )
                """
            )
            conn.execute(
                """
                INSERT OR IGNORE INTO published_news_by_channel (channel, link, published_at)
                SELECT 'telegram', link, published_at FROM published_news
                """
            )
            conn.execute(
                """
                INSERT OR IGNORE INTO published_news_by_channel (channel, link, published_at)
                SELECT 'vk', link, published_at FROM published_news
                """
            )
            conn.commit()

    def is_seen(self, channel: str, link: str) -> bool:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT 1 FROM published_news_by_channel WHERE channel = ? AND link = ? LIMIT 1",
                (channel, link),
            ).fetchone()
            return row is not None

    def mark_seen(self, channel: str, link: str, published_at: str) -> None:
        with self._connect() as conn:
            conn.execute(
                "INSERT OR IGNORE INTO published_news_by_channel (channel, link, published_at) VALUES (?, ?, ?)",
                (channel, link, published_at),
            )
            conn.commit()
