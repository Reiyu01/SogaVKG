"""Validated, bounded execution of LLM-proposed static federated query plans.

Plans name Mapping entities and properties only.  Raw tables, SQL, and arbitrary
join columns are deliberately absent from the public plan format.
"""

from __future__ import annotations

from dataclasses import dataclass
from time import monotonic
from typing import Any

from app.adapters.source_adapter import SourceAdapter
from app.semantic.mapper import SemanticMapper


@dataclass(frozen=True)
class QueryPlanPolicy:
    max_steps: int = 5
    max_rows_per_step: int = 1_000
    max_total_rows: int = 5_000
    max_duration_seconds: float = 15.0


class SemanticQueryPlanner:
    """Validates and executes a small, Mapping-constrained static plan DSL."""

    def __init__(self, mapper: SemanticMapper, sources: dict[str, SourceAdapter], relation_rules: list[dict[str, Any]], policy: QueryPlanPolicy | None = None):
        self.mapper, self.sources, self.relation_rules = mapper, sources, relation_rules
        self.policy = policy or QueryPlanPolicy()

    @staticmethod
    def _table(mapping: dict[str, Any]) -> str:
        return mapping.get("ingestion", {}).get("source_table") or mapping.get("source", {}).get("table")

    @staticmethod
    def _matches(value: Any, operator: str, expected: Any) -> bool:
        if operator == "=": return value == expected
        if operator == "!=": return value != expected
        if operator == "IN": return isinstance(expected, list) and value in expected
        if operator == "LIKE": return str(expected).replace("%", "").lower() in str(value or "").lower()
        if value is None: return False
        return {">": value > expected, ">=": value >= expected, "<": value < expected, "<=": value <= expected}[operator]

    def validate(self, plan: dict[str, Any]) -> list[dict[str, Any]]:
        steps = plan.get("steps")
        if not isinstance(steps, list) or not steps or len(steps) > self.policy.max_steps:
            raise ValueError(f"Plan must contain between 1 and {self.policy.max_steps} steps")
        ids: set[str] = set()
        validated = []
        for index, step in enumerate(steps):
            step_id, entity = step.get("id"), step.get("entity")
            if not isinstance(step_id, str) or not step_id or step_id in ids:
                raise ValueError("Every plan step needs a unique id")
            ids.add(step_id)
            mapping = self.mapper.get_entity(entity)
            fields = step.get("fields") or list(mapping.get("properties", {}))
            if not isinstance(fields, list) or not set(fields) <= set(mapping.get("properties", {})):
                raise ValueError(f"Plan step {step_id} projects an unknown Mapping property")
            filters = step.get("filters", [])
            if not isinstance(filters, list):
                raise ValueError(f"Plan step {step_id} filters must be a list")
            for item in filters:
                if item.get("field") not in mapping.get("properties", {}) or item.get("operator", "=") not in {"=", "!=", "IN", "LIKE", ">", ">=", "<", "<="}:
                    raise ValueError(f"Plan step {step_id} contains an unapproved filter")
            limit = step.get("limit", self.policy.max_rows_per_step)
            if not isinstance(limit, int) or not 0 < limit <= self.policy.max_rows_per_step:
                raise ValueError(f"Plan step {step_id} has an invalid limit")
            input_spec = step.get("input")
            rule = None
            if index == 0 and input_spec:
                raise ValueError("The first plan step cannot have an input handoff")
            if index and not input_spec:
                raise ValueError("Every later plan step requires a published relation-rule handoff")
            if input_spec:
                from_step, rule_id = input_spec.get("from_step"), input_spec.get("relation_rule_id")
                if from_step not in ids:
                    raise ValueError("Plan inputs must refer to an earlier step")
                rule = next((candidate for candidate in self.relation_rules if candidate["id"] == rule_id), None)
                if not rule or rule["source_entity"] != entity:
                    raise ValueError("Plan input must use a published rule for its destination entity")
                previous = next(candidate for candidate in validated if candidate["id"] == from_step)
                if rule["target_entity"] != previous["entity"]:
                    raise ValueError("Relation rule does not connect the handoff entities")
            validated.append({"id": step_id, "entity": entity, "fields": fields, "filters": filters, "limit": limit, "input": input_spec, "rule": rule})
        return validated

    def execute_static(self, plan: dict[str, Any]) -> dict[str, Any]:
        started, total_rows = monotonic(), 0
        steps = self.validate(plan)
        handoff_columns: dict[str, set[str]] = {}
        for step in steps:
            if step["rule"]:
                handoff_columns.setdefault(step["input"]["from_step"], set()).add(step["rule"]["target_column"])
        outputs: dict[str, list[dict[str, Any]]] = {}
        audit_steps = []
        for step in steps:
            if monotonic() - started > self.policy.max_duration_seconds:
                raise ValueError("Query plan exceeded its time budget")
            mapping = self.mapper.get_entity(step["entity"])
            property_columns = {field: definition["column"] for field, definition in mapping.get("properties", {}).items()}
            columns = {property_columns[field] for field in step["fields"]}
            columns.update(property_columns[item["field"]] for item in step["filters"])
            key_column = keys = None
            if step["rule"]:
                rule = step["rule"]
                key_column = rule["source_column"]
                columns.add(key_column)
                keys = {row.get(rule["target_column"]) for row in outputs[step["input"]["from_step"]] if row.get(rule["target_column"]) is not None}
                if len(keys) > self.policy.max_rows_per_step:
                    raise ValueError("Plan handoff exceeds the key budget")
            primary_key = mapping.get("ingestion", {}).get("primary_key", "id")
            columns.add(primary_key)
            columns.update(handoff_columns.get(step["id"], set()))
            rows = self.sources[step["entity"]].fetch_rows(self._table(mapping), columns=columns, key_column=key_column, keys=keys, limit=step["limit"])
            rows = [row for row in rows if all(self._matches(row.get(property_columns[item["field"]]), item.get("operator", "="), item.get("value")) for item in step["filters"])]
            total_rows += len(rows)
            if total_rows > self.policy.max_total_rows:
                raise ValueError("Query plan exceeded its total row budget")
            outputs[step["id"]] = rows
            audit_steps.append({"id": step["id"], "entity": step["entity"], "row_count": len(rows), "relation_rule_id": step["rule"]["id"] if step["rule"] else None})
        final = steps[-1]
        final_mapping = self.mapper.get_entity(final["entity"])
        data = [{field: row.get(final_mapping["properties"][field]["column"]) for field in final["fields"]} for row in outputs[final["id"]]]
        return {"data": data, "count": len(data), "lineage": {"planner": "static", "steps": audit_steps, "policy": self.policy.__dict__}}
