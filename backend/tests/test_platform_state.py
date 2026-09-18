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


if __name__ == "__main__":
    unittest.main()
