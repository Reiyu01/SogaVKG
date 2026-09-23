import sqlite3
import tempfile
import unittest
from pathlib import Path

from app.semantic.mapper import SemanticMapper
from app.services.graph_projection import GraphProjectionService


class GraphProjectionTests(unittest.TestCase):
    def test_projects_mapped_rows_and_foreign_key_relations_without_neo4j(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            database = root / "source.db"
            mappings = root / "mappings"
            mappings.mkdir()
            (mappings / "categories.yaml").write_text("""entity: Category\ningestion:\n  source_table: categories\n  primary_key: id\nproperties:\n  name:\n    column: name\n""", encoding="utf-8")
            (mappings / "assets.yaml").write_text("""entity: Asset\ningestion:\n  source_table: assets\n  primary_key: id\nproperties:\n  name:\n    column: name\nrelations:\n  belongs_to:\n    label: belongs to\n    ingestion:\n      foreign_key: category_id\n      target_key: id\n    target:\n      entity: Category\n""", encoding="utf-8")
            with sqlite3.connect(database) as connection:
                connection.executescript("""CREATE TABLE categories (id INTEGER PRIMARY KEY, name TEXT);\nCREATE TABLE assets (id INTEGER PRIMARY KEY, name TEXT, category_id INTEGER);\nINSERT INTO categories VALUES (1, 'Camera');\nINSERT INTO assets VALUES (7, 'ESP32-CAM', 1);""")

            projection = GraphProjectionService(SemanticMapper(mappings), database).project()

            self.assertEqual(projection["count"], {"nodes": 2, "edges": 1})
            self.assertEqual(projection["edges"][0]["source"], "Asset:7")
            self.assertEqual(projection["edges"][0]["target"], "Category:1")


if __name__ == "__main__":
    unittest.main()
