"""Acceptance coverage for a project-style federated query across two sources."""

import sqlite3
import tempfile
import unittest
from pathlib import Path

from app.schemas.semantic_query import SemanticQuery
from app.semantic.mapper import SemanticMapper
from app.services.source_resolution import resolve_entity_source_adapters
from app.services.sqlite_semantic_query import SemanticQueryService


class FederatedQueryAcceptanceTests(unittest.TestCase):
    def test_published_relation_rule_can_replace_yaml_relation(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            mappings = root / "mappings"; mappings.mkdir()
            assets_db, master_db = root / "assets.db", root / "master.db"
            (mappings / "asset.yaml").write_text("entity: Asset\ningestion: {source_table: assets, primary_key: id, source_id: assets-source}\nproperties: {name: {column: name}}\n", encoding="utf-8")
            (mappings / "category.yaml").write_text("entity: Category\ningestion: {source_table: categories, primary_key: id, source_id: master-source}\nproperties: {name: {column: name}}\n", encoding="utf-8")
            with sqlite3.connect(assets_db) as connection:
                connection.executescript("CREATE TABLE assets (id INTEGER, name TEXT, category_id INTEGER); INSERT INTO assets VALUES (1, 'Camera one', 10);")
            with sqlite3.connect(master_db) as connection:
                connection.executescript("CREATE TABLE categories (id INTEGER, name TEXT); INSERT INTO categories VALUES (10, 'Camera');")
            mapper = SemanticMapper(mappings)
            adapters = resolve_entity_source_adapters(mapper, [{"id": "assets-source", "active": True, "source_type": "sqlite", "config": {"path": str(assets_db)}}, {"id": "master-source", "active": True, "source_type": "sqlite", "config": {"path": str(master_db)}}])
            result = SemanticQueryService(mapper, adapters, relation_rules=[{"id": "rule-1", "source_entity": "Asset", "relation_name": "category", "target_entity": "Category", "source_column": "category_id", "target_column": "id", "display_property": "name"}]).execute(SemanticQuery(entity="Asset", fields=["name", "category"], filters=[{"field": "category", "operator": "=", "value": "Camera"}]))
            self.assertEqual(result["data"], [{"name": "Camera one", "category": "Camera"}])
            self.assertEqual(result["lineage"]["relation_rule_id"], "rule-1")

    def test_filters_assets_from_one_source_by_category_in_another_source(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            mappings = root / "mappings"; mappings.mkdir()
            assets_db, master_db = root / "assets.db", root / "master.db"
            (mappings / "asset.yaml").write_text(
                "entity: Asset\ningestion: {source_table: assets, primary_key: id, source_id: assets-source}\nproperties:\n  asset_code: {column: asset_code}\n  name: {column: name}\nrelations:\n  category:\n    ingestion: {foreign_key: category_id, target_key: id}\n    target: {entity: Category}\n    display: {property: name}\n",
                encoding="utf-8",
            )
            (mappings / "category.yaml").write_text(
                "entity: Category\ningestion: {source_table: categories, primary_key: id, source_id: master-source}\nproperties:\n  name: {column: name}\n",
                encoding="utf-8",
            )
            with sqlite3.connect(assets_db) as connection:
                connection.executescript("CREATE TABLE assets (id INTEGER, asset_code TEXT, name TEXT, category_id INTEGER); INSERT INTO assets VALUES (1, 'A-001', 'Camera one', 10), (2, 'A-002', 'Sensor one', 20);")
            with sqlite3.connect(master_db) as connection:
                connection.executescript("CREATE TABLE categories (id INTEGER, name TEXT); INSERT INTO categories VALUES (10, 'Camera'), (20, 'Sensor');")

            mapper = SemanticMapper(mappings)
            adapters = resolve_entity_source_adapters(mapper, [
                {"id": "assets-source", "active": True, "source_type": "sqlite", "config": {"path": str(assets_db)}},
                {"id": "master-source", "active": True, "source_type": "sqlite", "config": {"path": str(master_db)}},
            ])
            result = SemanticQueryService(mapper, adapters).execute(SemanticQuery(
                entity="Asset", fields=["asset_code", "name", "category"],
                filters=[{"field": "category", "operator": "=", "value": "Camera"}],
            ))

            self.assertEqual(result["data"], [{"asset_code": "A-001", "name": "Camera one", "category": "Camera"}])
            self.assertEqual(result["lineage"], {
                "federated": True,
                "entities": ["Asset", "Category"],
                "join": "Asset.category_id = Category.id",
                "policy": {"max_join_keys": 1000, "max_source_rows": 5000, "max_result_rows": 500, "max_duration_seconds": 10.0},
            })


if __name__ == "__main__":
    unittest.main()
