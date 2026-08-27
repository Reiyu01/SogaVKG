import sqlite3
from pathlib import Path
from typing import Any, Protocol, runtime_checkable
from urllib.parse import quote


class QuerySafetyError(ValueError):
    """The requested statement is not a single read query."""


class DatabaseDependencyError(RuntimeError):
    """A database dependency could not serve a validated query."""


@runtime_checkable
class ReadOnlyDatabasePort(Protocol):
    def execute(
        self,
        query: str,
        params: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]: ...

    def check_readiness(self) -> None: ...


class SQLiteReadOnlyAdapter:
    """Least-privilege SQLite adapter used by the query application."""

    def __init__(self, db_path: str | Path):
        self.db_path = Path(db_path)

    def _connect(self) -> sqlite3.Connection:
        if not self.db_path.is_file():
            raise DatabaseDependencyError("database dependency unavailable")
        database_uri = f"file:{quote(str(self.db_path.resolve()), safe='/')}?mode=ro"
        try:
            connection = sqlite3.connect(database_uri, uri=True, timeout=5)
            connection.row_factory = sqlite3.Row
            connection.execute("PRAGMA query_only = ON")
            return connection
        except sqlite3.Error as exc:
            raise DatabaseDependencyError("database dependency unavailable") from exc

    @staticmethod
    def _validate_read_query(query: str) -> str:
        statement = query.strip()
        if not statement or "\x00" in statement:
            raise QuerySafetyError("query must be a single SELECT statement")
        without_trailing = statement[:-1].rstrip() if statement.endswith(";") else statement
        if ";" in without_trailing or not without_trailing.upper().startswith("SELECT"):
            raise QuerySafetyError("query must be a single SELECT statement")
        return statement

    def execute(
        self,
        query: str,
        params: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        statement = self._validate_read_query(query)
        try:
            with self._connect() as connection:
                cursor = connection.execute(statement, params or {})
                return [dict(row) for row in cursor.fetchall()]
        except (QuerySafetyError, DatabaseDependencyError):
            raise
        except sqlite3.Error as exc:
            raise DatabaseDependencyError("database query unavailable") from exc

    def check_readiness(self) -> None:
        try:
            with self._connect() as connection:
                connection.execute("SELECT 1").fetchone()
        except DatabaseDependencyError:
            raise
        except sqlite3.Error as exc:
            raise DatabaseDependencyError("database dependency unavailable") from exc
