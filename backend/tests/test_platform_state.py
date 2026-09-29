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


if __name__ == "__main__":
    unittest.main()
