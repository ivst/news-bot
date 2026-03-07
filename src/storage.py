from __future__ import annotations

import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import List, Tuple


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
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS post_attempts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    channel TEXT NOT NULL,
                    link TEXT NOT NULL,
                    title TEXT NOT NULL,
                    summary TEXT NOT NULL,
                    text_norm TEXT NOT NULL,
                    status TEXT NOT NULL,
                    reason TEXT,
                    similarity REAL,
                    created_at TEXT NOT NULL
                )
                """
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_post_attempts_channel_created ON post_attempts (channel, created_at DESC)"
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

    def cleanup_older_than_days(self, retention_days: int) -> int:
        cutoff = (datetime.now(timezone.utc) - timedelta(days=retention_days)).isoformat()
        with self._connect() as conn:
            cur = conn.execute(
                "DELETE FROM published_news_by_channel WHERE published_at < ?",
                (cutoff,),
            )
            deleted = cur.rowcount if cur.rowcount is not None else 0
            conn.commit()
        return deleted

    def vacuum(self) -> None:
        with self._connect() as conn:
            conn.execute("VACUUM")

    def get_recent_published_texts(self, channel: str, limit: int) -> List[Tuple[str, str]]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT text_norm, link
                FROM post_attempts
                WHERE channel = ? AND status = 'published'
                ORDER BY created_at DESC
                LIMIT ?
                """,
                (channel, limit),
            ).fetchall()
            return [(str(r[0]), str(r[1])) for r in rows]

    def record_attempt(
        self,
        *,
        channel: str,
        link: str,
        title: str,
        summary: str,
        text_norm: str,
        status: str,
        reason: str | None = None,
        similarity: float | None = None,
    ) -> None:
        created_at = datetime.now(timezone.utc).isoformat()
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO post_attempts (
                    channel, link, title, summary, text_norm, status, reason, similarity, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (channel, link, title, summary, text_norm, status, reason, similarity, created_at),
            )
            conn.commit()
