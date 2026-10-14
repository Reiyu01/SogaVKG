import tempfile
import unittest
import sqlite3
from pathlib import Path

from app.adapters.source_adapter import SourceAdapter
from app.schemas.semantic_query import SemanticQuery
from app.semantic.mapper import SemanticMapper
from app.services.graph_projection import GraphProjectionService
from app.services.sqlite_semantic_query import SemanticQueryService
from app.adapters.source_adapter import SQLiteSourceAdapter


class MemoryPostgreSQLAdapter(SourceAdapter):
    """Adapter-shaped test double: proves services do not require SQLite."""
    source_type = "postgresql"

    def __init__(self, tables): self.tables = tables
    def inspect_schema(self): return {"source_type": self.source_type, "tables": [{"name": name} for name in self.tables]}
    def table_columns(self, table): return set(self.tables[table][0]) if self.tables[table] else set()
    def read_rows(self, table): return [dict(row) for row in self.tables[table]]
    def values(self, table, column): return {row.get(column) for row in self.tables[table]}
    def find_rows(self, table, column=None, value=None, limit=300):
        rows = self.read_rows(table)
        return ([row for row in rows if row.get(column) == value] if column else rows)[:limit]
    def duplicate_keys(self, table, primary_key): return {"duplicate_key_count": 0, "duplicate_row_count": 0, "samples": []}


class SourceAdapterContractTests(unittest.TestCase):
    def test_sqlite_fetch_rows_pushes_key_lookup_projection_and_limit(self):
        with tempfile.TemporaryDirectory() as directory:
            database = Path(directory) / "source.db"
            with sqlite3.connect(database) as connection:
                connection.executescript("CREATE TABLE assets (id INTEGER, name TEXT, secret TEXT); INSERT INTO assets VALUES (1, 'Camera', 'x'), (2, 'Sensor', 'y');")
            rows = SQLiteSourceAdapter(database).fetch_rows("assets", columns={"id", "name"}, key_column="id", keys={2}, limit=1)
            self.assertEqual(rows, [{"id": 2, "name": "Sensor"}])
    def _mapper(self, root: Path) -> SemanticMapper:
        mappings = root / "mappings"; mappings.mkdir()
        asset = "entity: Asset\ningestion: {source_table: assets, primary_key: id}\nproperties: {name: {column: name}, quantity: {column: quantity}}\nrelations:\n  category:\n    ingestion: {foreign_key: category_id, target_key: id}\n    target: {entity: Category}\n    display: {property: name}\n"
        category = "entity: Category\ningestion: {source_table: categories, primary_key: id}\nproperties: {name: {column: name}}\n"
        (mappings / "asset.yaml").write_text(asset, encoding="utf-8")
        (mappings / "category.yaml").write_text(category, encoding="utf-8")
        return SemanticMapper(mappings)

    def test_projection_and_single_source_query_use_adapter_contract(self):
        with tempfile.TemporaryDirectory() as directory:
            mapper = self._mapper(Path(directory))
            adapter = MemoryPostgreSQLAdapter({"assets": [{"id": 1, "name": "Camera", "quantity": 2, "category_id": 10}], "categories": [{"id": 10, "name": "Optics"}]})
            sources = {"Asset": adapter, "Category": adapter}
            self.assertEqual(GraphProjectionService(mapper, sources).project()["count"], {"nodes": 2, "edges": 1})
            result = SemanticQueryService(mapper, sources).execute(SemanticQuery(entity="Asset", fields=["name", "category"], limit=10))
            self.assertEqual(result["data"], [{"name": "Camera", "category": "Optics"}])

    def test_cross_source_relation_query_uses_bounded_mapping_approved_join(self):
        with tempfile.TemporaryDirectory() as directory:
            mapper = self._mapper(Path(directory))
            assets = MemoryPostgreSQLAdapter({"assets": [{"id": 1, "name": "Camera", "quantity": 2, "category_id": 10}]})
            categories = MemoryPostgreSQLAdapter({"categories": [{"id": 10, "name": "Optics"}]})
            result = SemanticQueryService(mapper, {"Asset": assets, "Category": categories}).execute(SemanticQuery(entity="Asset", fields=["name", "category"], filters=[{"field": "category", "operator": "=", "value": "Optics"}]))
            self.assertEqual(result["data"], [{"name": "Camera", "category": "Optics"}])
            self.assertTrue(result["lineage"]["federated"])


if __name__ == "__main__":
    unittest.main()
