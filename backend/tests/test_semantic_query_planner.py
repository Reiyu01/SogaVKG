import sqlite3
import tempfile
import unittest
from pathlib import Path

from app.semantic.mapper import SemanticMapper
from app.services.semantic_query_planner import QueryPlanPolicy, SemanticQueryPlanner
from app.services.source_resolution import resolve_entity_source_adapters


class SemanticQueryPlannerTests(unittest.TestCase):
    def test_executes_validated_static_plan_with_published_key_handoff(self):
        with tempfile.TemporaryDirectory() as directory:
            root, mappings = Path(directory), Path(directory) / "mappings"
            mappings.mkdir(); assets_db, categories_db = root / "assets.db", root / "categories.db"
            (mappings / "asset.yaml").write_text("entity: Asset\ningestion: {source_table: assets, primary_key: id, source_id: assets}\nproperties: {name: {column: name}}\n", encoding="utf-8")
            (mappings / "category.yaml").write_text("entity: Category\ningestion: {source_table: categories, primary_key: id, source_id: categories}\nproperties: {name: {column: name}}\n", encoding="utf-8")
            with sqlite3.connect(assets_db) as connection:
                connection.executescript("CREATE TABLE assets (id INTEGER, name TEXT, category_id INTEGER); INSERT INTO assets VALUES (1, 'Camera one', 10), (2, 'Sensor one', 20);")
            with sqlite3.connect(categories_db) as connection:
                connection.executescript("CREATE TABLE categories (id INTEGER, name TEXT); INSERT INTO categories VALUES (10, 'Camera'), (20, 'Sensor');")
            mapper = SemanticMapper(mappings)
            sources = resolve_entity_source_adapters(mapper, [{"id": "assets", "active": True, "source_type": "sqlite", "config": {"path": str(assets_db)}}, {"id": "categories", "active": True, "source_type": "sqlite", "config": {"path": str(categories_db)}}])
            result = SemanticQueryPlanner(mapper, sources, [{"id": "asset-category", "source_entity": "Asset", "relation_name": "category", "target_entity": "Category", "source_column": "category_id", "target_column": "id"}]).execute_static({"steps": [
                {"id": "category", "entity": "Category", "fields": ["name"], "filters": [{"field": "name", "operator": "=", "value": "Camera"}]},
                {"id": "asset", "entity": "Asset", "fields": ["name"], "input": {"from_step": "category", "relation_rule_id": "asset-category"}},
            ]})
            self.assertEqual(result["data"], [{"name": "Camera one"}])
            self.assertEqual(result["lineage"]["steps"][1]["relation_rule_id"], "asset-category")

    def test_rejects_unpublished_relation_handoff(self):
        planner = SemanticQueryPlanner.__new__(SemanticQueryPlanner)
        planner.policy = QueryPlanPolicy()
        planner.relation_rules = []
        planner.mapper = type("Mapper", (), {"get_entity": lambda _, entity: {"properties": {"name": {"column": "name"}}}})()
        with self.assertRaisesRegex(ValueError, "published rule"):
            planner.validate({"steps": [{"id": "a", "entity": "Category"}, {"id": "b", "entity": "Asset", "input": {"from_step": "a", "relation_rule_id": "missing"}}]})


if __name__ == "__main__":
    unittest.main()
