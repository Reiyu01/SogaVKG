import unittest
import sys
import types

# The test exercises the pipeline's Cypher scope only; it does not need the
# optional Neo4j driver package or a running Neo4j instance.
if "neo4j" not in sys.modules:
    neo4j = types.ModuleType("neo4j")
    neo4j.GraphDatabase = object
    sys.modules["neo4j"] = neo4j

from app.semantic.ingestion_pipeline import IngestionPipeline


class FakeSession:
    def __init__(self):
        self.calls = []

    def run(self, query, **params):
        self.calls.append((query, params))
        return []


class FakeSessionContext:
    def __init__(self, session):
        self.session = session

    def __enter__(self):
        return self.session

    def __exit__(self, exc_type, exc, traceback):
        return False


class FakeDriver:
    def __init__(self, session):
        self._session = session

    def session(self):
        return FakeSessionContext(self._session)


class EmptyMapper:
    mappings = {}


class IngestionPipelineTests(unittest.TestCase):
    def test_full_reset_deletes_only_the_current_project(self):
        session = FakeSession()
        pipeline = object.__new__(IngestionPipeline)
        pipeline.mapper = EmptyMapper()
        pipeline.project_id = "project-a"
        pipeline.driver = FakeDriver(session)
        pipeline.readers = {}
        pipeline.on_progress = lambda *_: None

        pipeline.run(reset=True)

        self.assertEqual(
            session.calls[0],
            (
                "MATCH (n { _project_id: $project_id }) DETACH DELETE n",
                {"project_id": "project-a"},
            ),
        )


if __name__ == "__main__":
    unittest.main()
