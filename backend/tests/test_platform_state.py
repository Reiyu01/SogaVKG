import tempfile
import unittest
from pathlib import Path

from app.repositories.platform_state import PlatformStateRepository


class PlatformStateRepositoryTests(unittest.TestCase):
    def test_source_profiles_and_jobs_survive_repository_recreation(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "platform.db"
            repository = PlatformStateRepository(path)
            repository.save_source({
                "id": "source-1",
                "name": "Example source",
                "source_type": "sqlite",
                "config": {"path": "/data/example.db"},
            })
            repository.create_job({
                "id": "job-1", "status": "pending", "logs": [], "error": None,
                "source_id": "source-1", "started_at": "2026-01-01T00:00:00+00:00",
                "finished_at": None,
            })

            reopened = PlatformStateRepository(path)

            self.assertEqual(reopened.get_source("source-1")["config"]["path"], "/data/example.db")
            self.assertEqual(reopened.get_job("job-1")["source_id"], "source-1")

    def test_job_persists_mapping_version_used_for_a_build(self):
        with tempfile.TemporaryDirectory() as directory:
            repository = PlatformStateRepository(Path(directory) / "platform.db")
            repository.create_project({"id": "project-1", "name": "Demo"})
            version = repository.create_mapping_version("project-1", [{"entity": "Asset"}])
            repository.create_job({
                "id": "job-1", "project_id": "project-1", "status": "done", "logs": [], "error": None,
                "source_id": "source-1", "started_at": "2026-01-01T00:00:00+00:00", "finished_at": None,
                "mapping_version_id": version["id"],
            })
            self.assertEqual(repository.get_job("job-1")["mapping_version_id"], "project-1:v1")

    def test_identity_alignment_audit_and_mapping_version_snapshot(self):
        with tempfile.TemporaryDirectory() as directory:
            repository = PlatformStateRepository(Path(directory) / "platform.db")
            repository.create_project({"id": "project-1", "name": "Demo"})
            alignment = repository.save_entity_alignment({"id": "alignment-1", "project_id": "project-1", "source_entity": "Asset", "target_entity": "SheetAsset", "source_column": "code", "target_column": "code"})
            version = repository.create_mapping_version("project-1", [{"entity": "Asset"}], [alignment])
            repository.delete_entity_alignment("project-1", "alignment-1")
            snapshot = repository.get_mapping_version("project-1", version["version"])
            self.assertEqual(snapshot["entity_alignments"], [alignment])
            self.assertEqual([event["action"] for event in repository.list_entity_alignment_audit_events("project-1")], ["deleted", "created"])

    def test_query_audit_preserves_plan_and_not_credentials(self):
        with tempfile.TemporaryDirectory() as directory:
            repository = PlatformStateRepository(Path(directory) / "platform.db")
            repository.create_project({"id": "project-1", "name": "Demo"})
            repository.record_query_audit_event({"project_id": "project-1", "query_kind": "semantic", "sources": ["Asset", "Category"], "plan": {"entity": "Asset"}, "result_count": 1, "duration_ms": 12})
            event = repository.list_query_audit_events("project-1")[0]
            self.assertEqual(event["plan"], {"entity": "Asset"})
            self.assertEqual(event["sources"], ["Asset", "Category"])

    def test_relation_rules_are_project_scoped_and_versioned(self):
        with tempfile.TemporaryDirectory() as directory:
            repository = PlatformStateRepository(Path(directory) / "platform.db")
            repository.create_project({"id": "project-1", "name": "Demo"})
            rule = repository.save_relation_rule({
                "id": "rule-1", "project_id": "project-1", "source_entity": "Asset",
                "relation_name": "category", "target_entity": "Category",
                "source_column": "category_id", "target_column": "id", "display_property": "name",
            })
            version = repository.create_mapping_version("project-1", [{"entity": "Asset"}])
            self.assertEqual(repository.list_relation_rules("project-1"), [rule])
            self.assertEqual(repository.get_mapping_version("project-1", version["version"])["relation_rules"], [rule])


if __name__ == "__main__":
    unittest.main()
