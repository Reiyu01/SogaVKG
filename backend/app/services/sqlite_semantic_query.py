"""Execute a SemanticQuery against a mapped SQLite source, without Neo4j."""

from __future__ import annotations

import re
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from app.schemas.semantic_query import SemanticQuery
from app.semantic.mapper import SemanticMapper

_IDENTIFIER = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def identifier(value: str) -> str:
    if not _IDENTIFIER.fullmatch(value):
        raise ValueError(f"Invalid mapping identifier: {value!r}")
    return f'"{value}"'


@dataclass
class SqliteQueryResult:
    sql: str
    params: list[Any]


class SQLiteSemanticQueryService:
    """Only Mapping-approved identifiers can become SQL; values are parameters."""

    def __init__(self, mapper: SemanticMapper, database_path: Path):
        self.mapper = mapper
        self.database_path = database_path

    def _table(self, mapping: dict[str, Any]) -> str:
        table = mapping.get("ingestion", {}).get("source_table") or mapping.get("source", {}).get("table")
        if not table:
            raise ValueError("Mapping has no source table")
        return table

    def _field(self, entity: str, field: str, alias: str, joins: list[str]) -> str:
        mapping = self.mapper.get_entity(entity)
        properties = mapping.get("properties", {})
        if field in properties:
            return f"{alias}.{identifier(properties[field]['column'])}"
        relation = mapping.get("relations", {}).get(field)
        if not relation:
            raise ValueError(f"Unknown field: {entity}.{field}")
        target_entity = relation.get("target", {}).get("entity")
        target = self.mapper.get_entity(target_entity)
        source_key = relation.get("ingestion", {}).get("foreign_key")
        target_key = relation.get("ingestion", {}).get("target_key") or target.get("ingestion", {}).get("primary_key", "id")
        if not source_key:
            raise ValueError(f"Relation {entity}.{field} has no foreign key")
        target_alias = f"r_{field}"
        join = f"LEFT JOIN {identifier(self._table(target))} {target_alias} ON {alias}.{identifier(source_key)} = {target_alias}.{identifier(target_key)}"
        if join not in joins:
            joins.append(join)
        display_property = relation.get("display", {}).get("property")
        column = target.get("properties", {}).get(display_property or "", {}).get("column") or target_key
        return f"{target_alias}.{identifier(column)}"

    def build(self, query: SemanticQuery) -> SqliteQueryResult:
        mapping = self.mapper.get_entity(query.entity)
        alias = "source"
        joins: list[str] = []
        fields = query.fields or list(mapping.get("properties", {}).keys())
        select = [f"{self._field(query.entity, field, alias, joins)} AS {identifier(field)}" for field in fields]
        conditions: list[str] = []
        params: list[Any] = []
        for item in query.filters:
            column = self._field(query.entity, item.field, alias, joins)
            if item.operator == "IN":
                if not isinstance(item.value, list) or not item.value:
                    raise ValueError("IN filters require a non-empty list")
                conditions.append(f"{column} IN ({', '.join('?' for _ in item.value)})")
                params.extend(item.value)
            else:
                conditions.append(f"{column} {item.operator} ?")
                params.append(f"%{item.value}%" if item.operator == "LIKE" else item.value)
        order_clause = None
        if query.order_by:
            order = self._field(query.entity, query.order_by.field, alias, joins)
            order_clause = f" ORDER BY {order} {query.order_by.direction}"
        sql = f"SELECT {', '.join(select)} FROM {identifier(self._table(mapping))} {alias}"
        if joins:
            sql += " " + " ".join(joins)
        if conditions:
            sql += " WHERE " + " AND ".join(conditions)
        if order_clause:
            sql += order_clause
        sql += " LIMIT ?"
        params.append(query.limit)
        return SqliteQueryResult(sql, params)

    def execute(self, query: SemanticQuery, project_id: str | None = None) -> dict[str, Any]:
        result = self.build(query)
        with sqlite3.connect(self.database_path) as connection:
            connection.row_factory = sqlite3.Row
            rows = [dict(row) for row in connection.execute(result.sql, result.params)]
        return {"data": rows, "count": len(rows)}
