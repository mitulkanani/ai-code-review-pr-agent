import json
from pathlib import Path
import sqlite3
from contextlib import contextmanager
from typing import Iterator
from uuid import UUID

from app.models import ReviewResult


class ReviewStore:
    def __init__(self, database_path: str):
        self.database_path = database_path
        if database_path != ":memory:":
            Path(database_path).parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    @contextmanager
    def _connection(self) -> Iterator[sqlite3.Connection]:
        connection = sqlite3.connect(self.database_path, timeout=15)
        connection.row_factory = sqlite3.Row
        try:
            yield connection
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def _initialize(self) -> None:
        with self._connection() as conn:
            conn.execute(
                """CREATE TABLE IF NOT EXISTS reviews (
                    review_id TEXT PRIMARY KEY,
                    repository TEXT NOT NULL,
                    pull_request INTEGER NOT NULL,
                    created_at TEXT NOT NULL,
                    result_json TEXT NOT NULL
                )"""
            )

    def save(self, result: ReviewResult) -> None:
        with self._connection() as conn:
            conn.execute(
                "INSERT OR REPLACE INTO reviews VALUES (?, ?, ?, ?, ?)",
                (str(result.review_id), result.repository, result.pull_request,
                 result.created_at.isoformat(), result.model_dump_json()),
            )

    def get(self, review_id: UUID) -> ReviewResult | None:
        with self._connection() as conn:
            row = conn.execute("SELECT result_json FROM reviews WHERE review_id = ?", (str(review_id),)).fetchone()
        return ReviewResult.model_validate_json(row["result_json"]) if row else None

    def recent(self, limit: int = 20) -> list[ReviewResult]:
        with self._connection() as conn:
            rows = conn.execute(
                "SELECT result_json FROM reviews ORDER BY created_at DESC LIMIT ?", (limit,)
            ).fetchall()
        return [ReviewResult.model_validate_json(row["result_json"]) for row in rows]
