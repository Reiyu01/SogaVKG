import sqlite3
import tempfile
import unittest
from pathlib import Path

from app.semantic.mapper import SemanticMapper
from app.services.graph_projection import GraphProjectionService
from app.services.source_resolution import resolve_entity_source_paths


class MultiSourceProjectionTests(unittest.TestCase):
    def test_projects_cross_source_relation_between_entity_specific_sqlite_files(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); assets_db = root / "assets.db"; categories_db = root / "categories.db"; mappings = root / "mappings"; mappings.mkdir()
            (mappings / "categories.yaml").write_text("entity: Category\ningestion: {source_table: categories, primary_key: id, source_id: source-categories}\nproperties: {name: {column: name}}\n", encoding="utf-8")
            (mappings / "assets.yaml").write_text("entity: Asset\ningestion: {source_table: assets, primary_key: id, source_id: source-assets}\nproperties: {name: {column: name}}\nrelations:\n  belongs_to:\n    ingestion: {foreign_key: category_id, target_key: id}\n    target: {entity: Category}\n", encoding="utf-8")
            with sqlite3.connect(assets_db) as connection:
                connection.executescript("CREATE TABLE assets (id INTEGER, name TEXT, category_id INTEGER); INSERT INTO assets VALUES (7, 'ESP32-CAM', 1);")
            with sqlite3.connect(categories_db) as connection:
                connection.executescript("CREATE TABLE categories (id INTEGER, name TEXT); INSERT INTO categories VALUES (1, 'Camera');")
            mapper = SemanticMapper(mappings)
            paths = resolve_entity_source_paths(mapper, [
                {"id": "source-assets", "active": True, "source_type": "sqlite", "config": {"path": str(assets_db)}},
                {"id": "source-categories", "active": True, "source_type": "sqlite", "config": {"path": str(categories_db)}},
            ])

            projection = GraphProjectionService(mapper, paths).project()

            self.assertEqual(projection["count"], {"nodes": 2, "edges": 1})
            self.assertEqual(projection["edges"][0]["source"], "Asset:7")
            self.assertEqual(projection["edges"][0]["target"], "Category:1")


if __name__ == "__main__":
    unittest.main()
