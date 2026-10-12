"""Source-neutral semantic queries over Mapping-approved fields.

The historical module name is retained as an import-compatible alias. Query
execution uses SourceAdapter rather than constructing source-specific SQL.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from app.adapters.source_adapter import SQLiteSourceAdapter, SourceAdapter
from app.schemas.semantic_query import SemanticQuery
from app.semantic.mapper import SemanticMapper
from app.services.entity_alignment import normalize_identity_key


class SemanticQueryService:
    def __init__(self, mapper: SemanticMapper, sources: SourceAdapter | dict[str, SourceAdapter] | Path | dict[str, Path]):
        self.mapper = mapper
        if isinstance(sources, Path):
            adapter = SQLiteSourceAdapter(sources)
            self.sources = {entity: adapter for entity in mapper.mappings}
        elif isinstance(sources, dict):
            path_adapters: dict[Path, SQLiteSourceAdapter] = {}
            self.sources = {
                entity: path_adapters.setdefault(source, SQLiteSourceAdapter(source)) if isinstance(source, Path) else source
                for entity, source in sources.items()
            }
        else:
            self.sources = {entity: sources for entity in mapper.mappings}

    def source_for_entity(self, entity: str) -> SourceAdapter:
        return self.sources[entity]

    @staticmethod
    def _table(mapping: dict[str, Any]) -> str:
        table = mapping.get("ingestion", {}).get("source_table") or mapping.get("source", {}).get("table")
        if not table:
            raise ValueError("Mapping has no source table")
        return table

    def _property_column(self, entity: str, field: str) -> str:
        column = self.mapper.get_entity(entity).get("properties", {}).get(field, {}).get("column")
        if not column:
            raise ValueError(f"Unknown property field: {entity}.{field}")
        return column

    def _relation_value(self, entity: str, field: str, row: dict[str, Any]) -> Any:
        mapping = self.mapper.get_entity(entity)
        relation = mapping.get("relations", {}).get(field)
        if not relation:
            raise ValueError(f"Unknown field: {entity}.{field}")
        target_entity = relation.get("target", {}).get("entity")
        if target_entity not in self.mapper.mappings:
            raise ValueError(f"Relation {entity}.{field} has an unknown target")
        if self.source_for_entity(entity) is not self.source_for_entity(target_entity):
            raise ValueError(f"Cross-source relation query is not supported yet: {entity}.{field}")
        foreign_key = relation.get("ingestion", {}).get("foreign_key")
        if not foreign_key:
            raise ValueError(f"Relation {entity}.{field} has no foreign key")
        value = row.get(foreign_key)
        if value is None:
            return None
        target_mapping = self.mapper.get_entity(target_entity)
        target_key = relation.get("ingestion", {}).get("target_key") or target_mapping.get("ingestion", {}).get("primary_key", "id")
        target_rows = self.source_for_entity(target_entity).find_rows(self._table(target_mapping), target_key, value, 1)
        if not target_rows:
            return None
        display = relation.get("display", {}).get("property")
        column = target_mapping.get("properties", {}).get(display or "", {}).get("column") or target_key
        return target_rows[0].get(column)

    def _value(self, entity: str, field: str, row: dict[str, Any]) -> Any:
        mapping = self.mapper.get_entity(entity)
        if field in mapping.get("properties", {}):
            return row.get(self._property_column(entity, field))
        return self._relation_value(entity, field, row)

    @staticmethod
    def _matches(value: Any, operator: str, expected: Any) -> bool:
        if operator == "IN":
            if not isinstance(expected, list) or not expected:
                raise ValueError("IN filters require a non-empty list")
            return value in expected
        if operator == "LIKE":
            return str(expected).replace("%", "").lower() in str(value or "").lower()
        if operator == "=": return value == expected
        if operator == "!=": return value != expected
        if value is None: return False
        return {">": value > expected, ">=": value >= expected, "<": value < expected, "<=": value <= expected}[operator]

    def execute(self, query: SemanticQuery, project_id: str | None = None) -> dict[str, Any]:
        mapping = self.mapper.get_entity(query.entity)
        fields = query.fields or list(mapping.get("properties", {}).keys())
        rows = self.source_for_entity(query.entity).read_rows(self._table(mapping))
        for item in query.filters:
            rows = [row for row in rows if self._matches(self._value(query.entity, item.field, row), item.operator, item.value)]
        if query.order_by:
            rows.sort(key=lambda row: (self._value(query.entity, query.order_by.field, row) is None, self._value(query.entity, query.order_by.field, row)), reverse=query.order_by.direction == "DESC")
        data = [{field: self._value(query.entity, field, row) for field in fields} for row in rows[:query.limit]]
        return {"data": data, "count": len(data)}

    def execute_with_identity_mappings(self, query: SemanticQuery, entity_alignments: list[dict[str, Any]]) -> dict[str, Any]:
        """Attach matched records from aligned concepts without merging values."""
        mapping = self.mapper.get_entity(query.entity)
        rows = self.source_for_entity(query.entity).read_rows(self._table(mapping))
        for item in query.filters:
            rows = [row for row in rows if self._matches(self._value(query.entity, item.field, row), item.operator, item.value)]
        if query.order_by:
            rows.sort(key=lambda row: (self._value(query.entity, query.order_by.field, row) is None, self._value(query.entity, query.order_by.field, row)), reverse=query.order_by.direction == "DESC")
        rows = rows[:query.limit]
        fields = query.fields or list(mapping.get("properties", {}).keys())
        result = {"data": [{field: self._value(query.entity, field, row) for field in fields} for row in rows], "count": len(rows)}
        matches = []
        for alignment in entity_alignments:
            if query.entity not in (alignment["source_entity"], alignment["target_entity"]):
                continue
            forward = alignment["source_entity"] == query.entity
            other_entity = alignment["target_entity"] if forward else alignment["source_entity"]
            local_column = alignment["source_column"] if forward else alignment["target_column"]
            other_column = alignment["target_column"] if forward else alignment["source_column"]
            other_mapping = self.mapper.get_entity(other_entity)
            other_rows = self.source_for_entity(other_entity).read_rows(self._table(other_mapping))
            rule = alignment.get("normalization_rule", "exact")
            by_key = {normalize_identity_key(row.get(other_column), rule): row for row in other_rows if row.get(other_column) not in (None, "")}
            for row in rows:
                raw_key = row.get(local_column)
                key = normalize_identity_key(raw_key, rule)
                other_row = by_key.get(key) if key not in (None, "") else None
                if other_row is None:
                    continue
                base_record = self._provenanced_record(query.entity, mapping, row)
                aligned_record = self._provenanced_record(other_entity, other_mapping, other_row)
                matches.append({"identity_mapping_id": alignment["id"], "identity_key": key, "normalization_rule": rule, "records": [base_record, aligned_record], "field_conflicts": self._field_conflicts(base_record, aligned_record)})
        result["identity_expansion"] = {"enabled": True, "matched_record_count": len(matches), "matches": matches}
        return result

    @staticmethod
    def _provenanced_record(entity: str, mapping: dict[str, Any], row: dict[str, Any]) -> dict[str, Any]:
        return {"entity": entity, "data": {name: row.get(definition.get("column")) for name, definition in mapping.get("properties", {}).items()}}

    @staticmethod
    def _field_conflicts(left: dict[str, Any], right: dict[str, Any]) -> list[dict[str, Any]]:
        conflicts = []
        for field in set(left["data"]) & set(right["data"]):
            left_value, right_value = left["data"][field], right["data"][field]
            if left_value not in (None, "") and right_value not in (None, "") and left_value != right_value:
                conflicts.append({"field": field, "values": [{"entity": left["entity"], "value": left_value}, {"entity": right["entity"], "value": right_value}]})
        return conflicts


class SQLiteSemanticQueryService(SemanticQueryService):
    """Backward-compatible name for callers still using SQLite paths."""
