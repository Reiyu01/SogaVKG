"""
通用資料建置管線：
讀取每個 entity 的 YAML 映射（包含 ingestion 設定），
依 source_type 分派給對應的讀取器，把資料寫進 Neo4j。

執行方式：python scripts/ingest_to_neo4j.py
"""

import sqlite3
from abc import ABC, abstractmethod
from typing import Any

from neo4j import GraphDatabase

from app.semantic.mapper import SemanticMapper


# ======================================================
# 來源讀取器（Source Reader）：每種資料來源實作一個
# ======================================================

class SourceReader(ABC):
    @abstractmethod
    def read(self, ingestion_config: dict[str, Any]) -> list[dict[str, Any]]:
        """回傳這個 entity 的所有原始資料列（list of dict）"""
        ...


class SQLiteSourceReader(SourceReader):
    def __init__(self, db_path: str):
        self.conn = sqlite3.connect(db_path)
        self.conn.row_factory = sqlite3.Row

    def read(self, ingestion_config: dict[str, Any]) -> list[dict[str, Any]]:
        table = ingestion_config["source_table"]
        rows = self.conn.execute(f"SELECT * FROM {table}").fetchall()
        return [dict(row) for row in rows]


class GoogleSheetsSourceReader(SourceReader):
    def __init__(self, gspread_client, spreadsheet_id: str):
        self.gc = gspread_client
        self.spreadsheet_id = spreadsheet_id

    def read(self, ingestion_config: dict[str, Any]) -> list[dict[str, Any]]:
        sheet_name = ingestion_config["sheet_name"]
        sh = self.gc.open_by_key(self.spreadsheet_id)
        worksheet = sh.worksheet(sheet_name)
        return worksheet.get_all_records()


# ======================================================
# Ingestion Pipeline：核心邏輯，不管來源是什麼都一樣跑
# ======================================================

class IngestionPipeline:
    def __init__(self, mapper: SemanticMapper, neo4j_uri: str, neo4j_user: str, neo4j_password: str):
        self.mapper = mapper
        self.driver = GraphDatabase.driver(neo4j_uri, auth=(neo4j_user, neo4j_password))
        self.readers: dict[str, SourceReader] = {}

    def register_reader(self, source_type: str, reader: SourceReader):
        """註冊某種 source_type 該用哪個讀取器"""
        self.readers[source_type] = reader

    def run(self, reset: bool = True):
        with self.driver.session() as session:
            if reset:
                session.run("MATCH (n) DETACH DELETE n")

            # ---- 第一輪：先把所有節點建出來（不含關係）----
            entity_rows: dict[str, list[dict]] = {}

            for entity, mapping in self.mapper.mappings.items():
                ingestion_config = mapping.get("ingestion")
                if not ingestion_config:
                    print(f"[跳過] {entity} 沒有 ingestion 設定")
                    continue

                source_type = ingestion_config["source_type"]
                reader = self.readers.get(source_type)

                if reader is None:
                    raise ValueError(f"沒有註冊 source_type='{source_type}' 的讀取器")

                rows = reader.read(ingestion_config)
                entity_rows[entity] = rows

                self._create_nodes(session, entity, mapping, rows)
                print(f"[完成] {entity}：{len(rows)} 個節點")

            # ---- 第二輪：建立關係（此時所有節點都已存在）----
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
                    print(f"[完成] {entity}.{rel_name} 關係")

            # ---- 第三輪：建立全文索引（非結構化文字欄位）----
            self._create_fulltext_indexes(session)

    def _create_nodes(self, session, entity: str, mapping: dict, rows: list[dict]):
        node_label = mapping["source"]["node_label"]
        properties = mapping.get("properties", {})

        for row in rows:
            props = {
                prop_name: row.get(prop_info["column"])
                for prop_name, prop_info in properties.items()
                if prop_info["column"] in row
            }
            if "id" in row:
                props["_source_id"] = row["id"]

            session.run(
                f"CREATE (n:{node_label} $props)",
                props=props,
            )

    def _create_relationships(self, session, entity: str, mapping: dict, relation: dict, rows: list[dict]):
        source_node_label = mapping["source"]["node_label"]
        rel_type = relation["relationship_type"]
        rel_ingestion = relation["ingestion"]
        foreign_key = rel_ingestion["foreign_key"]

        target_entity = relation["target"]["entity"]
        target_mapping = self.mapper.get_entity(target_entity)
        target_node_label = target_mapping["source"]["node_label"]

        source_key_column = mapping.get("ingestion", {}).get("primary_key", "id")

        for row in rows:
            fk_value = row.get(foreign_key)
            if fk_value is None:
                continue

            session.run(
                f"""
                MATCH (a:{source_node_label} {{_source_id: $source_id}})
                MATCH (b:{target_node_label} {{_source_id: $target_id}})
                CREATE (a)-[:{rel_type}]->(b)
                """,
                source_id=row.get(source_key_column),
                target_id=fk_value,
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
            print(f"[完成] {node_label} 全文索引：{fulltext_fields}")

    def close(self):
        self.driver.close()


# ======================================================
# 執行入口
# ======================================================

def main():
    mapper = SemanticMapper("../semantic/mappings")

    pipeline = IngestionPipeline(
        mapper=mapper,
        neo4j_uri="bolt://localhost:7687",
        neo4j_user="neo4j",
        neo4j_password="your_password",
    )

    pipeline.register_reader("sqlite", SQLiteSourceReader("data/lab.db"))

    # 若有 entity 是從 Google Sheets 來，取消下面註解並填入認證資訊
    # import gspread
    # from google.oauth2.service_account import Credentials
    # creds = Credentials.from_service_account_file(
    #     "credentials/service_account.json",
    #     scopes=["https://www.googleapis.com/auth/spreadsheets.readonly"],
    # )
    # gc = gspread.authorize(creds)
    # pipeline.register_reader("google_sheets", GoogleSheetsSourceReader(gc, "你的Spreadsheet ID"))

    pipeline.run(reset=True)
    pipeline.close()


if __name__ == "__main__":
    main()
