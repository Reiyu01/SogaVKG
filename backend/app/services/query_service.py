"""
建 SQL：把上层传进来的 SemanticQuery（就是你上一条讯息那种物件）丢给 builder.build()，拿到 QueryResult(sql, params)。
执行查询：把 SQL 字串和参数化的 params 丢给 db.execute()——因为用的是具名参数（:filter_0 这种），可以有效防止 SQL 注入。
包装回传：回传一个统一格式的 dict，包含 data（查询结果列表）和 count（笔数），方便 API 层直接序列化成 JSON 回给前端。
"""

from app.adapters.base import DatabaseAdapter
from app.schemas.semantic_query import SemanticQuery
from app.semantic.mapper import SemanticMapper
from app.semantic.cypher_query_builder import CypherQueryBuilder


# from app.semantic.query_builder import (
#     SemanticQueryBuilder,
# )


class QueryService:

    def __init__(
        self,
        db: DatabaseAdapter,
        mapper: SemanticMapper,
    ):
        self.db = db

        self.builder = CypherQueryBuilder(mapper) 
        # self.builder = (
        #     SemanticQueryBuilder(
        #         mapper
        #     )
        # )

    def execute(
        self,
        query: SemanticQuery,
    ):

        query_result = (
            self.builder.build(query)
        )

        rows = self.db.execute(query_result.cypher, query_result.params) 
        # rows = self.db.execute(
        #     query_result.sql,
        #     query_result.params,
        # )

        return {
            "data": rows,
            "count": len(rows),
        }