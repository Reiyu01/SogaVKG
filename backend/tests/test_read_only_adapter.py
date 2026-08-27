import sqlite3
from pathlib import Path

import pytest

from app.adapters.read_only import (
    DatabaseDependencyError,
    QuerySafetyError,
    ReadOnlyDatabasePort,
    SQLiteReadOnlyAdapter,
)
from app.core.readiness import ReadinessError, check_query_readiness
from app.semantic.mapper import SemanticMapper
from app.services.query_policy import QueryPolicy


PROJECT_ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture
def sqlite_database(tmp_path: Path) -> Path:
    database_path = tmp_path / "assets.db"
    with sqlite3.connect(database_path) as connection:
        connection.executescript(
            """
            CREATE TABLE assets (asset_code TEXT PRIMARY KEY, name TEXT NOT NULL);
            INSERT INTO assets(asset_code, name) VALUES ('A001', 'ESP32');
            """
        )
    return database_path


def test_read_only_port_exposes_no_write_capability(sqlite_database: Path) -> None:
    adapter = SQLiteReadOnlyAdapter(sqlite_database)
    assert isinstance(adapter, ReadOnlyDatabasePort)
    assert not hasattr(adapter, "execute_write")


def test_adapter_returns_rows_and_empty_results(sqlite_database: Path) -> None:
    adapter = SQLiteReadOnlyAdapter(sqlite_database)
    assert adapter.execute(
        "SELECT asset_code, name FROM assets WHERE name = :name;",
        {"name": "ESP32"},
    ) == [{"asset_code": "A001", "name": "ESP32"}]
    assert adapter.execute(
        "SELECT asset_code FROM assets WHERE name = :name;",
        {"name": "missing"},
    ) == []


def test_adapter_rejects_mutation_and_multiple_statements(sqlite_database: Path) -> None:
    adapter = SQLiteReadOnlyAdapter(sqlite_database)
    with pytest.raises(QuerySafetyError):
        adapter.execute("DELETE FROM assets;")
    with pytest.raises(QuerySafetyError):
        adapter.execute("SELECT 1; DROP TABLE assets;")


def test_parameter_value_cannot_change_statement_or_data(sqlite_database: Path) -> None:
    adapter = SQLiteReadOnlyAdapter(sqlite_database)
    before = adapter.execute("SELECT COUNT(*) AS count FROM assets;")
    rows = adapter.execute(
        "SELECT asset_code FROM assets WHERE name = :name;",
        {"name": "ESP32'; DROP TABLE assets; --"},
    )
    after = adapter.execute("SELECT COUNT(*) AS count FROM assets;")
    assert rows == []
    assert before == after == [{"count": 1}]


def test_database_unavailable_is_translated(tmp_path: Path) -> None:
    adapter = SQLiteReadOnlyAdapter(tmp_path / "missing.db")
    with pytest.raises(DatabaseDependencyError, match="database dependency unavailable"):
        adapter.execute("SELECT 1;")


def test_readiness_checks_database_and_required_asset_mapping(
    sqlite_database: Path,
) -> None:
    mapper = SemanticMapper(PROJECT_ROOT / "semantic" / "mappings")
    check_query_readiness(
        SQLiteReadOnlyAdapter(sqlite_database),
        mapper,
        QueryPolicy(),
    )


def test_readiness_fails_when_public_mapping_is_missing(sqlite_database: Path) -> None:
    class IncompleteMapper:
        def get_entity(self, entity: str) -> dict:
            return {"entity": entity}

        def get_properties(self, entity: str) -> dict:
            return {"asset_code": {}}

        def get_relations(self, entity: str) -> dict:
            return {}

    with pytest.raises(ReadinessError, match="required public mappings"):
        check_query_readiness(
            SQLiteReadOnlyAdapter(sqlite_database),
            IncompleteMapper(),  # type: ignore[arg-type]
            QueryPolicy(),
        )
