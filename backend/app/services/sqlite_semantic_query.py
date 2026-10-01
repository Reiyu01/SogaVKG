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


class SQLiteSemanticQueryService(SemanticQueryService):
    """Backward-compatible name for callers still using SQLite paths."""
