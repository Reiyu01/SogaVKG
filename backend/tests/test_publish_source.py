import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from app.repositories.platform_state import PlatformStateRepository


class PublishSourceTests(unittest.TestCase):
    def test_publish_flow_can_persist_an_ad_hoc_sqlite_path_as_project_source(self):
        with tempfile.TemporaryDirectory() as directory:
            repository = PlatformStateRepository(Path(directory) / "platform.db")
            repository.create_project({"id": "project-1", "name": "Demo"})
            source = repository.save_source({
                "id": "source-1", "project_id": "project-1", "name": "Published SQLite source (demo.db)",
                "source_type": "sqlite", "config": {"path": "/data/demo.db"},
            })
            self.assertTrue(source["active"])
            self.assertEqual(repository.list_sources("project-1")[0]["config"]["path"], "/data/demo.db")


if __name__ == "__main__":
    unittest.main()
