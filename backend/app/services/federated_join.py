"""Bounded, Mapping-approved one-hop joins across independent sources."""

from __future__ import annotations

from dataclasses import dataclass
from time import monotonic
from typing import Any

from app.adapters.source_adapter import SourceAdapter
from app.schemas.semantic_query import SemanticQuery
from app.semantic.mapper import SemanticMapper


@dataclass(frozen=True)
class FederatedQueryPolicy:
    max_join_keys: int = 1_000
    max_source_rows: int = 5_000
    max_result_rows: int = 500
    max_duration_seconds: float = 10.0


class FederatedJoinExecutor:
    """Executes only relations published in Mapping; never accepts raw joins."""

    def __init__(self, mapper: SemanticMapper, sources: dict[str, SourceAdapter], policy: FederatedQueryPolicy | None = None, relation_rules: list[dict[str, Any]] | None = None):
        self.mapper, self.sources, self.policy = mapper, sources, policy or FederatedQueryPolicy()
        self.relation_rules = relation_rules or []

    def _relation(self, entity: str, relation_name: str) -> dict[str, Any]:
        """Use a repository rule when published; YAML remains a legacy fallback."""
        rule = next((item for item in self.relation_rules if item["source_entity"] == entity and item["relation_name"] == relation_name), None)
        if rule:
            return {
                "target": {"entity": rule["target_entity"]},
                "ingestion": {"foreign_key": rule["source_column"], "target_key": rule["target_column"]},
                "display": {"property": rule["display_property"]} if rule.get("display_property") else {},
                "rule_id": rule["id"],
            }
        relation = self.mapper.get_entity(entity).get("relations", {}).get(relation_name)
        if not relation:
            raise ValueError(f"Unknown relation: {entity}.{relation_name}")
        return relation

    @staticmethod
    def _table(mapping: dict[str, Any]) -> str:
        table = mapping.get("ingestion", {}).get("source_table") or mapping.get("source", {}).get("table")
        if not table:
            raise ValueError("Mapping has no source table")
        return table

    @staticmethod
    def _property_column(mapping: dict[str, Any], field: str) -> str:
        column = mapping.get("properties", {}).get(field, {}).get("column")
        if not column:
            raise ValueError(f"Unknown mapped property: {mapping.get('entity', 'Entity')}.{field}")
        return column

    def execute_relation_filter(self, query: SemanticQuery, relation_name: str, expected: Any) -> dict[str, Any]:
        started = monotonic()
        def ensure_budget() -> None:
            if monotonic() - started > self.policy.max_duration_seconds:
                raise ValueError("Federated query exceeded the configured time budget")
        source_mapping = self.mapper.get_entity(query.entity)
        relation = self._relation(query.entity, relation_name)
        target_entity = relation.get("target", {}).get("entity")
        target_mapping = self.mapper.get_entity(target_entity)
        foreign_key = relation.get("ingestion", {}).get("foreign_key")
        target_key = relation.get("ingestion", {}).get("target_key") or target_mapping.get("ingestion", {}).get("primary_key", "id")
        display_property = relation.get("display", {}).get("property")
        display_column = self._property_column(target_mapping, display_property) if display_property else target_key
        if not foreign_key:
            raise ValueError(f"Relation {query.entity}.{relation_name} has no foreign key")

        target_rows = self.sources[target_entity].fetch_rows(
            self._table(target_mapping), columns={target_key, display_column}, limit=self.policy.max_source_rows,
        )
        ensure_budget()
        target_keys = {row.get(target_key) for row in target_rows if row.get(display_column) == expected and row.get(target_key) is not None}
        if len(target_keys) > self.policy.max_join_keys:
            raise ValueError("Federated join exceeds the configured join-key limit; narrow the filter")
        fields = query.fields or list(source_mapping.get("properties", {}).keys())
        source_columns = {foreign_key}
        source_columns.update(self._property_column(source_mapping, field) for field in fields if field != relation_name)
        source_rows = self.sources[query.entity].fetch_rows(
            self._table(source_mapping), columns=source_columns, key_column=foreign_key, keys=target_keys, limit=self.policy.max_source_rows,
        )
        ensure_budget()
        data = []
        for row in source_rows[:min(query.limit, self.policy.max_result_rows)]:
            item = {}
            for field in fields:
                if field == relation_name:
                    item[field] = expected
                else:
                    item[field] = row.get(self._property_column(source_mapping, field))
            data.append(item)
        lineage = {"federated": True, "entities": [query.entity, target_entity], "join": f"{query.entity}.{foreign_key} = {target_entity}.{target_key}", "policy": {"max_join_keys": self.policy.max_join_keys, "max_source_rows": self.policy.max_source_rows, "max_result_rows": self.policy.max_result_rows, "max_duration_seconds": self.policy.max_duration_seconds}}
        if relation.get("rule_id"):
            lineage["relation_rule_id"] = relation["rule_id"]
        return {
            "data": data, "count": len(data),
            "lineage": lineage,
        }
