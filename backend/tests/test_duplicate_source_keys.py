import sqlite3
import tempfile
import unittest
from pathlib import Path

from app.services.data_quality import preview_mappings
from app.semantic.mapper import SemanticMapper


class DuplicateSourceKeyTests(unittest.TestCase):
    def test_preview_reports_duplicate_non_null_primary_keys_with_samples(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            database = root / "source.db"
            mappings = root / "mappings"
            mappings.mkdir()
            (mappings / "assets.yaml").write_text("""entity: Asset
ingestion:
  source_table: assets
  primary_key: asset_code
properties:
  asset_code:
    column: asset_code
""", encoding="utf-8")
            with sqlite3.connect(database) as connection:
                connection.executescript("""CREATE TABLE assets (asset_code TEXT, name TEXT);
INSERT INTO assets VALUES ('A-001', 'Camera A');
INSERT INTO assets VALUES ('A-001', 'Camera B');
INSERT INTO assets VALUES ('A-002', 'Laptop');
INSERT INTO assets VALUES (NULL, 'No key');""")

            preview = preview_mappings(SemanticMapper(mappings), database)

            duplicate_report = preview[0]["duplicate_primary_keys"]
            self.assertEqual(duplicate_report["duplicate_key_count"], 1)
            self.assertEqual(duplicate_report["duplicate_row_count"], 1)
            self.assertEqual(duplicate_report["samples"], [{"primary_key": "A-001", "occurrences": 2}])


if __name__ == "__main__":
    unittest.main()
