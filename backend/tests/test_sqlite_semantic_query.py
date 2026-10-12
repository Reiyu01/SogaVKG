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

    def test_expands_identity_mapping_and_reports_conflicts(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); mappings = root / "mappings"; mappings.mkdir(); database = root / "source.db"
            (mappings / "asset.yaml").write_text("entity: Asset\ningestion: {source_table: assets, primary_key: id}\nproperties:\n  asset_code: {column: asset_code}\n  name: {column: name}\n", encoding="utf-8")
            (mappings / "sheet.yaml").write_text("entity: SheetAsset\ningestion: {source_table: sheet_assets, primary_key: id}\nproperties:\n  asset_code: {column: code}\n  name: {column: display_name}\n", encoding="utf-8")
            with sqlite3.connect(database) as connection:
                connection.executescript("CREATE TABLE assets (id INTEGER, asset_code TEXT, name TEXT); CREATE TABLE sheet_assets (id INTEGER, code TEXT, display_name TEXT); INSERT INTO assets VALUES (1, 'A-1', 'Canonical name'); INSERT INTO sheet_assets VALUES (8, 'A-1', 'Sheet name');")
            service = SQLiteSemanticQueryService(SemanticMapper(mappings), database)
            result = service.execute_with_identity_mappings(SemanticQuery(entity="Asset"), [{"id": "alignment-a", "source_entity": "Asset", "target_entity": "SheetAsset", "source_column": "asset_code", "target_column": "code"}])
            match = result["identity_expansion"]["matches"][0]
            self.assertEqual(match["records"][1]["entity"], "SheetAsset")
            self.assertEqual(match["field_conflicts"][0]["field"], "name")


if __name__ == "__main__":
    unittest.main()
