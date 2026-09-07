from dataclasses import dataclass
from typing import Any

from app.semantic.mapper import SemanticMapper
from app.schemas.semantic_query import SemanticQuery


@dataclass
class QueryResult:
    cypher: str
    params: dict[str, Any]


class CypherQueryBuilder:
    """
    跟 SemanticQueryBuilder 的職責一樣：把 SemanticQuery 轉成可執行的查詢語言，
    只是這裡產生的是 Cypher，不是 SQL。
    """

    def __init__(self, mapper: SemanticMapper):
        self.mapper = mapper

    def build(self, query: SemanticQuery) -> QueryResult:
        entity = query.entity
        self.mapper.get_entity(entity)

        source = self.mapper.get_source(entity)
        node_label = source["node_label"]
        var = "n"  # 主節點固定用 n 當變數名

        match_clauses = [f"({var}:{node_label})"]
        return_clauses = []
        params: dict[str, Any] = {}

        # ------------------------------------------------------
        # SELECT（RETURN）
        # ------------------------------------------------------
        fields = query.fields or list(self.mapper.get_properties(entity).keys())

        for field in fields:
            return_sql, extra_match = self._resolve_field(entity, field, var)
            return_clauses.append(return_sql)
            if extra_match:
                match_clauses.append(extra_match)

        if not return_clauses:
            return_clauses = [f"{var} AS {entity.lower()}"]

        # ------------------------------------------------------
        # WHERE（含全文搜尋）
        # ------------------------------------------------------
        where_clauses = []

        for index, filter_item in enumerate(query.filters):
            condition, condition_params, extra_match = self._build_filter(
                entity, filter_item.field, filter_item.operator,
                filter_item.value, index, var,
            )
            where_clauses.append(condition)
            params.update(condition_params)
            if extra_match:
                match_clauses.append(extra_match)

        # ------------------------------------------------------
        # 組 Cypher
        # ------------------------------------------------------
        cypher = "MATCH " + ", ".join(dict.fromkeys(match_clauses))

        if where_clauses:
            cypher += "\nWHERE " + " AND ".join(where_clauses)

        cypher += "\nRETURN " + ", ".join(return_clauses)

        if query.order_by:
            direction = query.order_by.direction
            order_field, _ = self._resolve_field(entity, query.order_by.field, var)
            order_alias = order_field.split(" AS ")[-1]
            cypher += f"\nORDER BY {order_alias} {direction}"

        if query.limit is not None:
            cypher += f"\nLIMIT {query.limit}"

        return QueryResult(cypher=cypher, params=params)

    # ------------------------------------------------------
    # 欄位解析：property 直接取值，relation 用箭頭走訪
    # ------------------------------------------------------

    def _resolve_field(self, entity: str, field: str, var: str) -> tuple[str, str | None]:
        field = field.split(".")[0]
        properties = self.mapper.get_properties(entity)

        if field in properties:
            return f"{var}.{field} AS {field}", None

        relations = self.mapper.get_relations(entity)

        if field in relations:
            relation = relations[field]
            rel_type = relation["relationship_type"]
            target_entity = relation["target"]["entity"]
            target_label = self.mapper.get_source(target_entity)["node_label"]
            display_property = relation["display"]["property"]

            target_var = f"{var}_{field}"
            match_clause = f"({var})-[:{rel_type}]->({target_var}:{target_label})"

            return f"{target_var}.{display_property} AS {field}", match_clause

        raise ValueError(f"Unknown field: {entity}.{field}")

    # ------------------------------------------------------
    # 過濾條件：一般比較 vs 全文搜尋
    # ------------------------------------------------------

    def _build_filter(
        self, entity: str, field: str, operator: str, value: Any,
        index: int, var: str,
    ) -> tuple[str, dict[str, Any], str | None]:
        field = field.split(".")[0]
        param_name = f"filter_{index}"
        properties = self.mapper.get_properties(entity)

        if field in properties:
            property_info = properties[field]
            column_ref = f"{var}.{field}"

            # 非結構化文字欄位：走全文索引搜尋（比 CONTAINS 更適合大量自由文字）
            if operator == "LIKE" and property_info.get("fulltext"):
                node_label = self.mapper.get_source(entity)["node_label"]
                index_name = f"{node_label.lower()}_fulltext"
                condition = (
                    f"{var} IN [x IN "
                    f"[r IN db.index.fulltext.queryNodes('{index_name}', ${param_name}) | r.node] "
                    f"WHERE x = {var}]"
                )
                # 實務上更常見的寫法是把全文搜尋拆成獨立的 CALL 子句，這裡先用簡化版示意
                return condition, {param_name: value}, None

            if operator == "LIKE":
                return f"{column_ref} CONTAINS ${param_name}", {param_name: value}, None

            if operator == "IN":
                if not isinstance(value, list):
                    raise ValueError("IN operator requires a list")
                return f"{column_ref} IN ${param_name}", {param_name: value}, None

            allowed_operators = {"=", "<>", ">", ">=", "<", "<="}
            cypher_operator = "<>" if operator == "!=" else operator
            if cypher_operator not in allowed_operators:
                raise ValueError(f"Unsupported operator: {operator}")

            return f"{column_ref} {cypher_operator} ${param_name}", {param_name: value}, None

        relations = self.mapper.get_relations(entity)

        if field in relations:
            relation = relations[field]
            rel_type = relation["relationship_type"]
            target_entity = relation["target"]["entity"]
            target_label = self.mapper.get_source(target_entity)["node_label"]
            display_property = relation["display"]["property"]

            target_var = f"{var}_{field}"
            match_clause = f"({var})-[:{rel_type}]->({target_var}:{target_label})"
            column_ref = f"{target_var}.{display_property}"

            if operator == "LIKE":
                return f"{column_ref} CONTAINS ${param_name}", {param_name: value}, match_clause

            if operator != "=":
                raise ValueError(f"Relation field '{field}' only supports LIKE or = currently.")

            return f"{column_ref} = ${param_name}", {param_name: value}, match_clause

        raise ValueError(f"Unknown filter: {entity}.{field}")
