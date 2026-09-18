"""Regression tests for the generic semantic-query to Cypher translation."""

import tempfile
import unittest
from pathlib import Path

import yaml

from app.schemas.semantic_query import QueryFilter, SemanticQuery
from app.semantic.cypher_query_builder import CypherQueryBuilder
from app.semantic.mapper import SemanticMapper


class CypherQueryBuilderTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        mapping_dir = Path(self.temp_dir.name)
        mappings = [
            {
                "entity": "Document",
                "source": {"node_label": "Document"},
                "ingestion": {"source_type": "sqlite", "source_table": "documents", "primary_key": "id"},
                "properties": {
                    "title": {"column": "title", "type": "string"},
                    "score": {"column": "score", "type": "number"},
                },
                "relations": {
                    "owner": {
                        "relationship_type": "OWNED_BY",
                        "target": {"entity": "Person"},
                        "display": {"property": "display_name"},
                    },
                },
            },
            {
                "entity": "Person",
                "source": {"node_label": "Person"},
                "ingestion": {"source_type": "sqlite", "source_table": "people", "primary_key": "id"},
                "properties": {"display_name": {"column": "display_name", "type": "string"}},
            },
        ]
        for mapping in mappings:
            (mapping_dir / f"{mapping['entity'].lower()}.yaml").write_text(
                yaml.safe_dump(mapping, sort_keys=False), encoding="utf-8"
            )
        self.builder = CypherQueryBuilder(SemanticMapper(mapping_dir))

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_builds_parameterized_property_and_relation_query(self):
        query = SemanticQuery(
            entity="Document",
            fields=["title", "owner"],
            filters=[QueryFilter(field="owner", operator="LIKE", value="Ada")],
            limit=10,
        )

        result = self.builder.build(query)

        self.assertIn("MATCH (n:Document), (n)-[:OWNED_BY]->(n_owner:Person)", result.cypher)
        self.assertIn("n.title AS title, n_owner.display_name AS owner", result.cypher)
        self.assertIn("n_owner.display_name CONTAINS $filter_0", result.cypher)
        self.assertIn("LIMIT 10", result.cypher)
        self.assertEqual(result.params, {"filter_0": "Ada"})

    def test_rejects_unknown_field(self):
        with self.assertRaisesRegex(ValueError, "Unknown field"):
            self.builder.build(SemanticQuery(entity="Document", fields=["not_a_field"]))


if __name__ == "__main__":
    unittest.main()
