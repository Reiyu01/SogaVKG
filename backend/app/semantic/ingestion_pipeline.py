"""
在原本的 IngestionPipeline 基礎上，加入進度回報機制。
"""

import sqlite3
from abc import ABC, abstractmethod
from typing import Any, Callable

from neo4j import GraphDatabase

from app.semantic.mapper import SemanticMapper


class SourceReader(ABC):
    @abstractmethod
    def read(self, ingestion_config: dict[str, Any]) -> list[dict[str, Any]]:
        ...


class SQLiteSourceReader(SourceReader):
    def __init__(self, db_path: str):
        self.conn = sqlite3.connect(db_path)
        self.conn.row_factory = sqlite3.Row

    def read(self, ingestion_config: dict[str, Any]) -> list[dict[str, Any]]:
        table = ingestion_config["source_table"]
        rows = self.conn.execute(f"SELECT * FROM {table}").fetchall()
        return [dict(row) for row in rows]


class IngestionPipeline:
    def __init__(
        self,
        mapper: SemanticMapper,
        neo4j_uri: str,
        neo4j_user: str,
        neo4j_password: str,
        project_id: str | None = None,
        on_progress: Callable[[str, str], None] | None = None,
    ):
        """
        on_progress(step_name, message)：每完成一個步驟就呼叫一次，
        讓外部（例如 IngestionJob）可以記錄目前進度。
        """
        self.mapper = mapper
        self.project_id = project_id
        self.driver = GraphDatabase.driver(neo4j_uri, auth=(neo4j_user, neo4j_password))
        self.readers: dict[str, SourceReader] = {}
        self.on_progress = on_progress or (lambda step, msg: None)

    def register_reader(self, source_type: str, reader: SourceReader):
        self.readers[source_type] = reader

    def run(self, reset: bool = True):
        summary = {"mode": "full" if reset else "incremental", "entities": [], "relations": []}
        with self.driver.session() as session:
            if reset:
                self.on_progress("reset", "清空舊資料中...")
                session.run("MATCH (n) DETACH DELETE n")

            entity_rows: dict[str, list[dict]] = {}
            total_entities = len(self.mapper.mappings)

            for i, (entity, mapping) in enumerate(self.mapper.mappings.items(), 1):
                ingestion_config = mapping.get("ingestion")
                if not ingestion_config:
                    self.on_progress("nodes", f"[{i}/{total_entities}] {entity} 沒有 ingestion 設定，跳過")
                    continue

                source_type = ingestion_config["source_type"]
                reader = self.readers.get(source_type)
                if reader is None:
                    raise ValueError(f"沒有註冊 source_type='{source_type}' 的讀取器")

                rows = reader.read(ingestion_config)
                entity_rows[entity] = rows

                primary_key = mapping.get("ingestion", {}).get("primary_key", "id")
                source_ids = {row.get(primary_key) for row in rows if row.get(primary_key) is not None}
                node_label = mapping["source"]["node_label"]
                graph_ids = {record["source_id"] for record in session.run(
                    f"MATCH (n:{node_label} {{ _project_id: $project_id }}) RETURN n._source_id AS source_id",
                    project_id=self.project_id,
                )}
                deletion_candidates = sorted(graph_ids - source_ids) if not reset else []

                node_changes = self._create_nodes(session, entity, mapping, rows)
                summary["entities"].append({"entity": entity, "processed": len(rows), "skipped_missing_primary_key": sum(row.get(primary_key) is None for row in rows), "deletion_candidates": len(deletion_candidates), "deletion_candidate_ids": deletion_candidates[:20], **node_changes})
                self.on_progress("nodes", f"[{i}/{total_entities}] {entity}：建立 {len(rows)} 個節點")

            for entity, mapping in self.mapper.mappings.items():
                if entity not in entity_rows:
                    continue
                rows = entity_rows[entity]
                relations = mapping.get("relations", {})

                for rel_name, relation in relations.items():
                    rel_ingestion = relation.get("ingestion")
                    if not rel_ingestion:
                        continue
                    self._create_relationships(session, entity, mapping, relation, rows)
                    summary["relations"].append({"entity": entity, "relation": rel_name, "processed": len(rows)})
                    self.on_progress("relations", f"{entity}.{rel_name} 關係建立完成")

            self._create_fulltext_indexes(session)
            self.on_progress("done", "建置完成")
        return summary

    def _create_nodes(
        self,
        session,
        entity: str,
        mapping: dict,
        rows: list[dict],
    ):
        node_label = mapping["source"]["node_label"]

        properties = mapping.get(
            "properties",
            {},
        )

        ingestion_config = mapping.get(
            "ingestion",
            {},
        )

        primary_key = ingestion_config.get(
            "primary_key",
            "id",
        )

        batch = []

        for row in rows:
            source_id = row.get(
                primary_key
            )

            if source_id is None:
                continue

            props = {
                prop_name: row.get(
                    prop_info["column"]
                )
                for prop_name, prop_info
                in properties.items()
                if prop_info["column"] in row
            }

            props["_source_id"] = source_id
            if self.project_id:
                props["_project_id"] = self.project_id

            batch.append(
                {
                    "source_id": source_id,
                    "props": props,
                }
            )

        if not batch:
            return {"created": 0, "updated": 0, "unchanged": 0}

        existing_rows = session.run(
            f"""MATCH (n:{node_label} {{ _project_id: $project_id }})
            WHERE n._source_id IN $source_ids
            RETURN n._source_id AS source_id, properties(n) AS props""",
            source_ids=[item["source_id"] for item in batch], project_id=self.project_id,
        )
        existing = {row["source_id"]: row["props"] for row in existing_rows}
        created = updated = unchanged = 0
        for item in batch:
            old = existing.get(item["source_id"])
            if old is None:
                created += 1
            elif any(old.get(key) != value for key, value in item["props"].items() if not key.startswith("_")):
                updated += 1
            else:
                unchanged += 1

        session.run(
            f"""
            UNWIND $rows AS item

            MERGE (n:{node_label} {{
                _source_id: item.source_id,
                _project_id: $project_id
            }})

            SET n += item.props
            """,
            rows=batch, project_id=self.project_id,
        )
        return {"created": created, "updated": updated, "unchanged": unchanged}
    def _create_relationships(
        self,
        session,
        entity: str,
        mapping: dict,
        relation: dict,
        rows: list[dict],
    ):
        source_node_label = mapping["source"]["node_label"]

        rel_type = relation["relationship_type"]

        rel_ingestion = relation["ingestion"]

        foreign_key = rel_ingestion["foreign_key"]

        target_entity = relation["target"]["entity"]

        target_mapping = self.mapper.get_entity(
            target_entity
        )

        target_node_label = (
            target_mapping["source"]["node_label"]
        )

        source_key_column = (
            mapping
            .get("ingestion", {})
            .get("primary_key", "id")
        )

        target_key_column = (
            rel_ingestion.get("target_key")
            or target_mapping
            .get("ingestion", {})
            .get("primary_key", "id")
        )

        batch = []

        for row in rows:
            source_id = row.get(
                source_key_column
            )

            target_id = row.get(
                foreign_key
            )

            if (
                source_id is None
                or target_id is None
            ):
                continue

            batch.append(
                {
                    "source_id": source_id,
                    "target_id": target_id,
                }
            )

        if not batch:
            return

        session.run(
            f"""MATCH (a:{source_node_label} {{ _project_id: $project_id }})-[r:{rel_type}]->()
            WHERE a._source_id IN $source_ids DELETE r""",
            source_ids=[item["source_id"] for item in batch], project_id=self.project_id,
        )

        session.run(
            f"""
            UNWIND $rows AS row

            MATCH (a:{source_node_label} {{
                _source_id: row.source_id, _project_id: $project_id
            }})

            MATCH (b:{target_node_label} {{
                _source_id: row.target_id, _project_id: $project_id
            }})

            MERGE (a)-[:{rel_type}]->(b)
            """,
            rows=batch, project_id=self.project_id,
        )

    def _create_fulltext_indexes(self, session):
        for entity, mapping in self.mapper.mappings.items():
            node_label = mapping.get("source", {}).get("node_label")
            if not node_label:
                continue

            fulltext_fields = [
                name for name, info in mapping.get("properties", {}).items()
                if info.get("fulltext")
            ]
            if not fulltext_fields:
                continue

            field_list = ", ".join(f"n.{f}" for f in fulltext_fields)
            index_name = f"{node_label.lower()}_fulltext"

            session.run(
                f"""
                CREATE FULLTEXT INDEX {index_name} IF NOT EXISTS
                FOR (n:{node_label}) ON EACH [{field_list}]
                """
            )
            self.on_progress("index", f"{node_label} 全文索引建立完成")

    def close(self):
        self.driver.close()
