import sqlite3
import tempfile
import unittest
from pathlib import Path

from app.repositories.platform_state import PlatformStateRepository
from app.schemas.semantic_query import SemanticQuery
from app.semantic.mapper import SemanticMapper
from app.services.graph_projection import GraphProjectionService
from app.services.mapping_service import MappingService
from app.services.sqlite_semantic_query import SQLiteSemanticQueryService


MAPPING = {
    "entity": "Asset",
    "label": "Asset",
    "source": {"node_label": "Asset"},
    "ingestion": {"source_type": "sqlite", "source_table": "assets", "primary_key": "id"},
    "properties": {"name": {"column": "name", "type": "string"}},
    "relations": {},
}


class ProjectIsolationTests(unittest.TestCase):
    def test_projects_keep_sources_mappings_projection_queries_and_history_isolated(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            state = PlatformStateRepository(root / "platform.db")
            project_a = state.create_project({"id": "project-a", "name": "Project A"})
            project_b = state.create_project({"id": "project-b", "name": "Project B"})

            source_a, source_b = root / "source-a.db", root / "source-b.db"
            for database, name in ((source_a, "A 的相機"), (source_b, "B 的筆電")):
                with sqlite3.connect(database) as connection:
                    connection.execute("CREATE TABLE assets (id INTEGER, name TEXT)")
                    connection.execute("INSERT INTO assets VALUES (?, ?)", (1, name))

            mappings_a, mappings_b = root / "project-a" / "mappings", root / "project-b" / "mappings"
            MappingService(mappings_a).save_mapping(MAPPING)
            MappingService(mappings_b).save_mapping(MAPPING)
            state.save_source({"id": "source-a", "project_id": project_a["id"], "name": "A source", "source_type": "sqlite", "config": {"path": str(source_a)}})
            state.save_source({"id": "source-b", "project_id": project_b["id"], "name": "B source", "source_type": "sqlite", "config": {"path": str(source_b)}})
            state.create_job({"id": "job-a", "project_id": project_a["id"], "status": "done", "logs": [], "error": None, "source_id": "source-a", "started_at": "2026-01-01T00:00:00+00:00", "finished_at": None})
            state.create_job({"id": "job-b", "project_id": project_b["id"], "status": "done", "logs": [], "error": None, "source_id": "source-b", "started_at": "2026-01-02T00:00:00+00:00", "finished_at": None})

            mapper_a, mapper_b = SemanticMapper(mappings_a), SemanticMapper(mappings_b)
            graph_a = GraphProjectionService(mapper_a, source_a).project()
            graph_b = GraphProjectionService(mapper_b, source_b).project()
            query = SemanticQuery(entity="Asset", fields=["name"])
            query_a = SQLiteSemanticQueryService(mapper_a, source_a).execute(query)
            query_b = SQLiteSemanticQueryService(mapper_b, source_b).execute(query)

            self.assertEqual([node["label"] for node in graph_a["nodes"]], ["A 的相機"])
            self.assertEqual([node["label"] for node in graph_b["nodes"]], ["B 的筆電"])
            self.assertEqual(query_a["data"], [{"name": "A 的相機"}])
            self.assertEqual(query_b["data"], [{"name": "B 的筆電"}])
            self.assertEqual([source["id"] for source in state.list_sources(project_a["id"])], ["source-a"])
            self.assertEqual([source["id"] for source in state.list_sources(project_b["id"])], ["source-b"])
            self.assertEqual([job["id"] for job in state.list_jobs(project_a["id"])], ["job-a"])
            self.assertEqual([job["id"] for job in state.list_jobs(project_b["id"])], ["job-b"])

            state.set_source_active("source-a", False)
            self.assertFalse(state.get_source("source-a")["active"])
            self.assertTrue(state.get_source("source-b")["active"])


if __name__ == "__main__":
    unittest.main()
