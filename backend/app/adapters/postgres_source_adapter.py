"""Read-only PostgreSQL implementation of the Builder source contract."""

import os
from typing import Any

from app.adapters.source_adapter import SourceAdapter, quote_identifier


class PostgreSQLSourceAdapter(SourceAdapter):
    source_type = "postgresql"

    def __init__(self, config: dict[str, Any]):
        self.config = config

    def _connection(self):
        try:
            import psycopg
            from psycopg.rows import dict_row
        except ImportError as error:
            raise RuntimeError("PostgreSQL support requires psycopg; install backend requirements first") from error
        credential_ref = self.config.get("credential_ref")
        password = os.getenv(credential_ref or "")
        if not credential_ref or not password:
            raise ValueError("PostgreSQL credential_ref must name an environment variable containing the password")
        return psycopg.connect(host=self.config["host"], port=self.config.get("port", 5432), dbname=self.config["database"], user=self.config["username"], password=password, row_factory=dict_row)

    def inspect_schema(self) -> dict[str, Any]:
        with self._connection() as connection, connection.cursor() as cursor:
            cursor.execute("SELECT table_name FROM information_schema.tables WHERE table_schema = 'public' AND table_type = 'BASE TABLE' ORDER BY table_name")
            tables = []
            for row in cursor.fetchall():
                name = row["table_name"]
                cursor.execute("SELECT column_name, data_type, is_nullable, column_default FROM information_schema.columns WHERE table_schema = 'public' AND table_name = %s ORDER BY ordinal_position", (name,))
                columns = [{"name": item["column_name"], "type": item["data_type"], "nullable": item["is_nullable"] == "YES", "default": item["column_default"], "primary_key": False} for item in cursor.fetchall()]
                cursor.execute("SELECT kcu.column_name FROM information_schema.table_constraints tc JOIN information_schema.key_column_usage kcu ON tc.constraint_name = kcu.constraint_name AND tc.table_schema = kcu.table_schema WHERE tc.constraint_type = 'PRIMARY KEY' AND tc.table_schema = 'public' AND tc.table_name = %s", (name,))
                primary_keys = {item["column_name"] for item in cursor.fetchall()}
                for column in columns: column["primary_key"] = column["name"] in primary_keys
                cursor.execute(f"SELECT * FROM {quote_identifier(name)} LIMIT 5"); samples = cursor.fetchall()
                cursor.execute(f"SELECT COUNT(*) AS count FROM {quote_identifier(name)}"); count = cursor.fetchone()["count"]
                tables.append({"name": name, "row_count": count, "columns": columns, "foreign_keys": [], "sample_rows": samples})
        return {"source_type": self.source_type, "tables": tables}

    def table_columns(self, table: str) -> set[str]:
        return {item["name"] for item in next(item for item in self.inspect_schema()["tables"] if item["name"] == table)["columns"]}

    def read_rows(self, table: str) -> list[dict[str, Any]]:
        with self._connection() as connection, connection.cursor() as cursor:
            cursor.execute(f"SELECT * FROM {quote_identifier(table)}"); return cursor.fetchall()

    def values(self, table: str, column: str) -> set[Any]:
        with self._connection() as connection, connection.cursor() as cursor:
            cursor.execute(f"SELECT {quote_identifier(column)} AS value FROM {quote_identifier(table)}"); return {item["value"] for item in cursor.fetchall()}

    def find_rows(self, table: str, column: str | None = None, value: Any = None, limit: int = 300) -> list[dict[str, Any]]:
        sql = f"SELECT * FROM {quote_identifier(table)}"; params: list[Any] = []
        if column is not None: sql += f" WHERE {quote_identifier(column)} = %s"; params.append(value)
        sql += " LIMIT %s"; params.append(limit)
        with self._connection() as connection, connection.cursor() as cursor:
            cursor.execute(sql, params); return cursor.fetchall()

    def duplicate_keys(self, table: str, primary_key: str) -> dict[str, Any]:
        key, table_name = quote_identifier(primary_key), quote_identifier(table)
        grouped = f"SELECT {key} AS key_value, COUNT(*) AS occurrences FROM {table_name} WHERE {key} IS NOT NULL GROUP BY {key} HAVING COUNT(*) > 1"
        with self._connection() as connection, connection.cursor() as cursor:
            cursor.execute(f"SELECT COUNT(*) AS keys, COALESCE(SUM(occurrences - 1), 0) AS rows FROM ({grouped}) grouped"); counts = cursor.fetchone()
            cursor.execute(f"{grouped} ORDER BY occurrences DESC, key_value LIMIT 20"); samples = [{"primary_key": item["key_value"], "occurrences": item["occurrences"]} for item in cursor.fetchall()]
        return {"duplicate_key_count": counts["keys"], "duplicate_row_count": counts["rows"], "samples": samples}
