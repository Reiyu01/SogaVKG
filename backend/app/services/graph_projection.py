"""Build a bounded visual graph directly from a mapped SQLite source.

The projection is deliberately read-only: it does not copy customer data into a
second graph database.  Mapping remains the single definition of entities and
relationships used by both the graph view and future AI queries.
"""

from __future__ import annotations

import re
import sqlite3
from collections.abc import Iterable
from pathlib import Path
from typing import Any

from app.semantic.mapper import SemanticMapper


_IDENTIFIER = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def _identifier(value: str) -> str:
    """Allow only SQLite identifiers originating from a validated Mapping."""
    if not _IDENTIFIER.fullmatch(value):
        raise ValueError(f"Invalid mapping identifier: {value!r}")
    return f'"{value}"'


class GraphProjectionService:
    def __init__(self, mapper: SemanticMapper, database_path: Path):
        self.mapper = mapper
        self.database_path = database_path

    @staticmethod
    def _node_id(entity: str, source_id: Any) -> str:
        return f"{entity}:{source_id}"

    @staticmethod
    def _mapping_table(mapping: dict[str, Any]) -> str:
        return mapping.get("ingestion", {}).get("source_table") or mapping.get("source", {}).get("table")

    @staticmethod
    def _primary_key(mapping: dict[str, Any]) -> str:
        return mapping.get("ingestion", {}).get("primary_key", "id")

    @staticmethod
    def _label(entity: str, mapping: dict[str, Any], row: dict[str, Any]) -> str:
        for property_name in ("name", "asset_code", "title"):
            column = mapping.get("properties", {}).get(property_name, {}).get("column")
            if column and row.get(column) not in (None, ""):
                return str(row[column])
        return str(row.get(GraphProjectionService._primary_key(mapping), entity))

    def _rows(self, connection: sqlite3.Connection, mapping: dict[str, Any], limit: int) -> list[dict[str, Any]]:
        table = self._mapping_table(mapping)
        primary_key = self._primary_key(mapping)
        if not table:
            raise ValueError("Mapping does not define ingestion.source_table")
        return [dict(row) for row in connection.execute(
            f"SELECT * FROM {_identifier(table)} WHERE {_identifier(primary_key)} IS NOT NULL LIMIT ?", (limit,)
        )]

    def _as_node(self, entity: str, mapping: dict[str, Any], row: dict[str, Any]) -> dict[str, Any]:
        source_id = row[self._primary_key(mapping)]
        return {
            "id": self._node_id(entity, source_id), "entity": entity,
            "label": self._label(entity, mapping, row), "properties": row,
        }

    def entity_nodes(self, entity: str, limit: int = 12) -> dict[str, Any]:
        """Load only a small first layer after its Entity node is selected."""
        mapping = self.mapper.get_entity(entity)
        with sqlite3.connect(self.database_path) as connection:
            connection.row_factory = sqlite3.Row
            rows = self._rows(connection, mapping, max(1, min(limit, 30)))
        return {"nodes": [self._as_node(entity, mapping, row) for row in rows], "edges": []}

    def neighbors(self, entity: str, source_id: str, limit: int = 20) -> dict[str, Any]:
        """Expand the outgoing Mapping relations for one selected data node."""
        mapping = self.mapper.get_entity(entity)
        primary_key = self._primary_key(mapping)
        table = self._mapping_table(mapping)
        if not table:
            raise ValueError(f"{entity} has no source table")
        nodes: list[dict[str, Any]] = []
        edges: list[dict[str, Any]] = []
        with sqlite3.connect(self.database_path) as connection:
            connection.row_factory = sqlite3.Row
            row = connection.execute(
                f"SELECT * FROM {_identifier(table)} WHERE {_identifier(primary_key)} = ?", (source_id,)
            ).fetchone()
            if row is None:
                raise ValueError(f"{entity} record {source_id!r} was not found")
            source = dict(row)
            source_node = self._node_id(entity, source[primary_key])
            for relation_name, relation in mapping.get("relations", {}).items():
                target_entity = relation.get("target", {}).get("entity")
                if target_entity not in self.mapper.mappings:
                    continue
                foreign_key = relation.get("ingestion", {}).get("foreign_key")
                target_mapping = self.mapper.get_entity(target_entity)
                target_key = relation.get("ingestion", {}).get("target_key") or self._primary_key(target_mapping)
                value = source.get(foreign_key)
                if value is None:
                    continue
                target_table = self._mapping_table(target_mapping)
                target_rows = connection.execute(
                    f"SELECT * FROM {_identifier(target_table)} WHERE {_identifier(target_key)} = ? LIMIT ?", (value, max(1, min(limit, 30)))
                ).fetchall()
                for target_row in map(dict, target_rows):
                    target_node = self._as_node(target_entity, target_mapping, target_row)
                    nodes.append(target_node)
                    edge_id = f"{source_node}:{relation_name}:{target_node['id']}"
                    edges.append({"id": edge_id, "source": source_node, "target": target_node["id"], "type": relation.get("label") or relation_name})
        return {"nodes": nodes, "edges": edges}

    def project(self, limit: int = 120) -> dict[str, Any]:
        limit = max(1, min(limit, 300))
        mappings = self.mapper.mappings
        if not mappings:
            return {"nodes": [], "edges": [], "count": {"nodes": 0, "edges": 0}}

        per_entity = max(1, limit // len(mappings))
        nodes: dict[str, dict[str, Any]] = {}
        edges: dict[str, dict[str, Any]] = {}

        with sqlite3.connect(self.database_path) as connection:
            connection.row_factory = sqlite3.Row
            rows_by_entity: dict[str, list[dict[str, Any]]] = {}
            for entity, mapping in mappings.items():
                rows = self._rows(connection, mapping, per_entity)
                rows_by_entity[entity] = rows
                primary_key = self._primary_key(mapping)
                for row in rows:
                    source_id = row[primary_key]
                    node_id = self._node_id(entity, source_id)
                    nodes[node_id] = self._as_node(entity, mapping, row)

            for entity, mapping in mappings.items():
                source_key = self._primary_key(mapping)
                for relation_name, relation in mapping.get("relations", {}).items():
                    target_entity = relation.get("target", {}).get("entity")
                    if target_entity not in mappings:
                        continue
                    foreign_key = relation.get("ingestion", {}).get("foreign_key")
                    target_mapping = mappings[target_entity]
                    target_key = relation.get("ingestion", {}).get("target_key") or self._primary_key(target_mapping)
                    if not foreign_key:
                        continue
                    target_rows = {row.get(target_key): row for row in rows_by_entity.get(target_entity, [])}
                    for row in rows_by_entity[entity]:
                        target_value = row.get(foreign_key)
                        target_row = target_rows.get(target_value)
                        if target_value is None or target_row is None:
                            continue
                        source = self._node_id(entity, row[source_key])
                        target = self._node_id(target_entity, target_row[target_key])
                        edge_id = f"{source}:{relation_name}:{target}"
                        edges[edge_id] = {
                            "id": edge_id,
                            "source": source,
                            "target": target,
                            "type": relation.get("label") or relation_name,
                        }

        return {
            "nodes": list(nodes.values()),
            "edges": list(edges.values()),
            "count": {"nodes": len(nodes), "edges": len(edges)},
        }

    def records(self, entity: str, limit: int = 50, keyword: str | None = None) -> dict[str, Any]:
        mapping = self.mapper.get_entity(entity)
        limit = max(1, min(limit, 100))
        table = self._mapping_table(mapping)
        if not table:
            raise ValueError(f"{entity} has no source table")
        properties = mapping.get("properties", {})
        searchable = next((item.get("column") for item in properties.values() if item.get("searchable") or item.get("fulltext")), None)
        sql = f"SELECT * FROM {_identifier(table)}"
        params: list[Any] = []
        if keyword and searchable:
            sql += f" WHERE CAST({_identifier(searchable)} AS TEXT) LIKE ?"
            params.append(f"%{keyword}%")
        sql += " LIMIT ?"
        params.append(limit)
        with sqlite3.connect(self.database_path) as connection:
            connection.row_factory = sqlite3.Row
            rows = [dict(row) for row in connection.execute(sql, params)]
        return {"entity": entity, "data": rows, "count": len(rows)}
