"""
Neo4j 版本的 DatabaseAdapter 實作。
"""

from typing import Any

from neo4j import GraphDatabase

from app.adapters.base import DatabaseAdapter


class Neo4jAdapter(DatabaseAdapter):

    def __init__(self, uri: str, user: str, password: str):
        self.driver = GraphDatabase.driver(uri, auth=(user, password))

    # ======================================================
    # 讀取：多筆
    # ======================================================

    def execute(
        self,
        query: str,
        params: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        """執行查詢並回傳 dict list。"""

        def _run(tx):
            result = tx.run(query, params or {})
            return [record.data() for record in result]

        with self.driver.session() as session:
            return session.execute_read(_run)

    # ======================================================
    # 讀取：單筆
    # ======================================================

    def execute_one(
        self,
        query: str,
        params: dict[str, Any] | None = None,
    ) -> dict[str, Any] | None:
        """執行查詢並取得單筆資料。"""

        def _run(tx):
            result = tx.run(query, params or {})
            record = result.single()
            return record.data() if record else None

        with self.driver.session() as session:
            return session.execute_read(_run)

    # ======================================================
    # 寫入：CREATE / SET / DELETE 等
    # ======================================================

    def execute_write(
        self,
        query: str,
        params: dict[str, Any] | None = None,
    ) -> int:
        """執行 CREATE / SET / DELETE，回傳受影響的節點/關係數量。"""

        def _run(tx):
            result = tx.run(query, params or {})
            summary = result.consume()
            counters = summary.counters
            return (
                counters.nodes_created
                + counters.nodes_deleted
                + counters.relationships_created
                + counters.relationships_deleted
                + counters.properties_set
            )

        with self.driver.session() as session:
            return session.execute_write(_run)

    # ======================================================
    # 收尾
    # ======================================================

    def close(self):
        self.driver.close()