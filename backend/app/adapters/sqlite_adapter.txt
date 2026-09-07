import sqlite3
from typing import Any

from .base import DatabaseAdapter


class SQLiteAdapter(DatabaseAdapter):

    def __init__(self, db_path: str):
        self.db_path = db_path

    def _connect(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def execute(
        self,
        query: str,
        params: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        with self._connect() as conn:
            cursor = conn.execute(query, params or {})
            return [dict(row) for row in cursor.fetchall()]

    def execute_one(
        self,
        query: str,
        params: dict[str, Any] | None = None,
    ) -> dict[str, Any] | None:
        with self._connect() as conn:
            cursor = conn.execute(query, params or {})
            row = cursor.fetchone()
            return dict(row) if row else None

    def execute_write(
        self,
        query: str,
        params: dict[str, Any] | None = None,
    ) -> int:
        with self._connect() as conn:
            cursor = conn.execute(query, params or {})
            conn.commit()
            return cursor.rowcount