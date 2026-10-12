import tempfile
import unittest
from pathlib import Path

from app.repositories.platform_state import PlatformStateRepository
from app.semantic.mapper import SemanticMapper
from app.semantic.schema_description import build_schema_description


class EntityAlignmentTests(unittest.TestCase):
    def test_persists_concept_alignment_and_exposes_it_to_schema_description(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            state = PlatformStateRepository(root / "state.db")
            state.create_project({"id": "project-a", "name": "A"})
            alignment = state.save_entity_alignment({
                "id": "alignment-1", "project_id": "project-a",
                "source_entity": "GoogleSheetAsset", "target_entity": "Asset",
                "source_column": "asset_code", "target_column": "asset_code",
                "relation_type": "CONCEPT_EQUIVALENT_TO", "label": "同一概念",
            })
            self.assertEqual(state.list_entity_alignments("project-a"), [alignment])
            mappings = root / "mappings"; mappings.mkdir()
            (mappings / "asset.yaml").write_text("entity: Asset\nproperties: {asset_code: {column: asset_code}}\n", encoding="utf-8")
            (mappings / "google.yaml").write_text("entity: GoogleSheetAsset\nproperties: {asset_code: {column: asset_code}}\n", encoding="utf-8")
            description = build_schema_description(SemanticMapper(mappings), [alignment])
            self.assertIn("GoogleSheetAsset 與 Asset 是同一概念", description)
            self.assertIn("asset_code = asset_code", description)


if __name__ == "__main__":
    unittest.main()
