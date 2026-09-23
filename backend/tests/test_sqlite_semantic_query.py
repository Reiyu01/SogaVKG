import sqlite3
import tempfile
import unittest
from pathlib import Path

from app.schemas.semantic_query import SemanticQuery
from app.semantic.mapper import SemanticMapper
from app.services.sqlite_semantic_query import SQLiteSemanticQueryService


class SQLiteSemanticQueryTests(unittest.TestCase):
    def test_queries_mapping_properties_and_relations_with_parameters(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); mappings = root / "mappings"; mappings.mkdir(); database = root / "source.db"
            (mappings / "asset.yaml").write_text("""entity: Asset\ningestion: {source_table: assets, primary_key: id}\nproperties:\n  name: {column: name}\nrelations:\n  category:\n    ingestion: {foreign_key: category_id, target_key: id}\n    target: {entity: Category}\n    display: {property: name}\n""", encoding="utf-8")
            (mappings / "category.yaml").write_text("""entity: Category\ningestion: {source_table: categories, primary_key: id}\nproperties:\n  name: {column: name}\n""", encoding="utf-8")
            with sqlite3.connect(database) as connection:
                connection.executescript("""CREATE TABLE assets (id INTEGER, name TEXT, category_id INTEGER);\nCREATE TABLE categories (id INTEGER, name TEXT);\nINSERT INTO assets VALUES (1, 'ESP32-CAM', 2); INSERT INTO categories VALUES (2, 'Camera');""")
            service = SQLiteSemanticQueryService(SemanticMapper(mappings), database)
            result = service.execute(SemanticQuery(entity="Asset", fields=["name", "category"], limit=10))
            self.assertEqual(result["data"], [{"name": "ESP32-CAM", "category": "Camera"}])


if __name__ == "__main__":
    unittest.main()
