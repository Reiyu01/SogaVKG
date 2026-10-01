"""Adapter contract for sources used by Builder and read-only projection."""

from abc import ABC, abstractmethod
import sqlite3
from pathlib import Path
from typing import Any


class SourceAdapter(ABC):
    source_type: str

    @abstractmethod
    def inspect_schema(self) -> dict[str, Any]: ...

    @abstractmethod
    def table_columns(self, table: str) -> set[str]: ...

    @abstractmethod
    def read_rows(self, table: str) -> list[dict[str, Any]]: ...

    @abstractmethod
    def values(self, table: str, column: str) -> set[Any]: ...

    @abstractmethod
    def find_rows(self, table: str, column: str | None = None, value: Any = None, limit: int = 300) -> list[dict[str, Any]]: ...

    @abstractmethod
    def duplicate_keys(self, table: str, primary_key: str) -> dict[str, Any]: ...


def quote_identifier(value: str) -> str:
    return '"' + value.replace('"', '""') + '"'


class SQLiteSourceAdapter(SourceAdapter):
    source_type = "sqlite"

    def __init__(self, path: Path):
        self.path = path

    def _connection(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path)
        connection.row_factory = sqlite3.Row
        return connection

    def inspect_schema(self) -> dict[str, Any]:
        with self._connection() as connection:
            tables = []
            for row in connection.execute("SELECT name FROM sqlite_master WHERE type = 'table' AND name NOT LIKE 'sqlite_%' ORDER BY name"):
                name = row["name"]
                columns = [{"name": item["name"], "type": item["type"], "nullable": item["notnull"] == 0, "default": item["dflt_value"], "primary_key": item["pk"] > 0} for item in connection.execute(f"PRAGMA table_info({quote_identifier(name)})")]
                foreign_keys = [{"column": item["from"], "target_table": item["table"], "target_column": item["to"]} for item in connection.execute(f"PRAGMA foreign_key_list({quote_identifier(name)})")]
                samples = [dict(item) for item in connection.execute(f"SELECT * FROM {quote_identifier(name)} LIMIT 5")]
                count = connection.execute(f"SELECT COUNT(*) FROM {quote_identifier(name)}").fetchone()[0]
                tables.append({"name": name, "row_count": count, "columns": columns, "foreign_keys": foreign_keys, "sample_rows": samples})
        return {"source_type": self.source_type, "path": str(self.path), "tables": tables}

    def table_columns(self, table: str) -> set[str]:
        with self._connection() as connection:
            return {row["name"] for row in connection.execute(f"PRAGMA table_info({quote_identifier(table)})")}

    def read_rows(self, table: str) -> list[dict[str, Any]]:
        with self._connection() as connection:
            return [dict(row) for row in connection.execute(f"SELECT * FROM {quote_identifier(table)}")]

    def values(self, table: str, column: str) -> set[Any]:
        with self._connection() as connection:
            return {row[0] for row in connection.execute(f"SELECT {quote_identifier(column)} FROM {quote_identifier(table)}")}

    def find_rows(self, table: str, column: str | None = None, value: Any = None, limit: int = 300) -> list[dict[str, Any]]:
        sql = f"SELECT * FROM {quote_identifier(table)}"; params: list[Any] = []
        if column is not None: sql += f" WHERE {quote_identifier(column)} = ?"; params.append(value)
        sql += " LIMIT ?"; params.append(limit)
        with self._connection() as connection:
            return [dict(row) for row in connection.execute(sql, params)]

    def duplicate_keys(self, table: str, primary_key: str) -> dict[str, Any]:
        key, table_name = quote_identifier(primary_key), quote_identifier(table)
        grouped = f"SELECT {key} AS key_value, COUNT(*) AS occurrences FROM {table_name} WHERE {key} IS NOT NULL GROUP BY {key} HAVING COUNT(*) > 1"
        with self._connection() as connection:
            counts = connection.execute(f"SELECT COUNT(*), COALESCE(SUM(occurrences - 1), 0) FROM ({grouped})").fetchone()
            samples = [{"primary_key": row[0], "occurrences": row[1]} for row in connection.execute(f"{grouped} ORDER BY occurrences DESC, key_value LIMIT 20")]
        return {"duplicate_key_count": counts[0], "duplicate_row_count": counts[1], "samples": samples}


def create_source_adapter(source_type: str, config: dict[str, Any]) -> SourceAdapter:
    if source_type == "sqlite":
        return SQLiteSourceAdapter(Path(config["path"]))
    if source_type == "postgresql":
        from app.adapters.postgres_source_adapter import PostgreSQLSourceAdapter
        return PostgreSQLSourceAdapter(config)
    if source_type == "google_sheets":
        from app.adapters.google_sheets_source_adapter import GoogleSheetsSourceAdapter
        return GoogleSheetsSourceAdapter(config)
    raise ValueError(f"Unsupported source type: {source_type}")
