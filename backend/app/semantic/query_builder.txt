from dataclasses import dataclass
from typing import Any

from app.semantic.mapper import SemanticMapper
from app.schemas.semantic_query import SemanticQuery

@dataclass
class QueryResult:
    sql: str
    params: dict[str, Any]


class SemanticQueryBuilder:

    def __init__(
        self,
        mapper: SemanticMapper,
    ):
        self.mapper = mapper

    # ======================================================
    # Public
    # ======================================================

    def build(
        self,
        query: SemanticQuery,
    ) -> QueryResult:

        # ======================================================
        # Entity
        # ======================================================

        entity = query.entity

        self.mapper.get_entity(
            entity
        )

        # ======================================================
        # Source
        # ======================================================

        source = self.mapper.get_source(
            entity
        )

        table = source["table"]

        alias = source.get(
            "alias",
            "t",
        )

        # ======================================================
        # SELECT
        # ======================================================

        fields = query.fields

        select_clauses = []
        joins = []

        for field in fields:

            field_sql, field_joins = (
                self._build_field(
                    entity,
                    field,
                )
            )

            select_clauses.append(
                field_sql
            )

            joins.extend(
                field_joins
            )

        if not select_clauses:

            select_clauses = [
                f"{alias}.*"
            ]

        # ======================================================
        # WHERE
        # ======================================================

        where_clauses = []
        params = {}

        for index, filter_item in enumerate(
            query.filters
        ):

            (
                condition,
                condition_params,
                filter_joins,
            ) = self._build_filter(
                entity=entity,
                field=filter_item.field,
                operator=filter_item.operator,
                value=filter_item.value,
                index=index,
            )

            where_clauses.append(
                condition
            )

            params.update(
                condition_params
            )

            joins.extend(
                filter_joins
            )

        # ======================================================
        # Remove duplicate JOIN
        # ======================================================

        joins = list(
            dict.fromkeys(joins)
        )

        # ======================================================
        # SQL
        # ======================================================

        sql = (
            "SELECT\n"
            "    "
            + ",\n    ".join(
                select_clauses
            )
            + f"\nFROM {table} {alias}"
        )

        # ======================================================
        # JOIN
        # ======================================================

        if joins:

            sql += (
                "\n"
                + "\n".join(joins)
            )

        # ======================================================
        # WHERE
        # ======================================================

        if where_clauses:

            sql += (
                "\nWHERE "
                + "\n  AND ".join(
                    where_clauses
                )
            )

        # ======================================================
        # ORDER BY
        # ======================================================

        if query.order_by:

            sql += (
                "\nORDER BY "
                + self._build_order_by(
                    entity,
                    query.order_by.model_dump(),
                )
            )

        # ======================================================
        # LIMIT
        # ======================================================

        if query.limit is not None:

            limit = min(
                query.limit,
                500,
            )

            sql += (
                f"\nLIMIT {limit}"
            )

        sql += ";"

        return QueryResult(
            sql=sql,
            params=params,
        )

    # ======================================================
    # SELECT field
    # ======================================================

    def _build_field(
        self,
        entity: str,
        field: str,
    ) -> tuple[
        str,
        list[str],
    ]:
        #2026/08/31
        field = field.split(".")[0]

        alias = self.mapper.get_alias(
            entity
        )

        properties = (
            self.mapper.get_properties(
                entity
            )
        )

        # --------------------------------------------------
        # Property
        # --------------------------------------------------

        if field in properties:

            column = (
                self.mapper.get_property_column(
                    entity,
                    field,
                )
            )

            return (
                f"{alias}.{column} AS {field}",
                [],
            )

        # --------------------------------------------------
        # Relation
        # --------------------------------------------------

        relations = (
            self.mapper.get_relations(
                entity
            )
        )

        if field in relations:

            relation = (
                self.mapper.get_relation(
                    entity,
                    field,
                )
            )

            join = (
                self._build_relation_join(
                    entity,
                    relation,
                )
            )

            target = relation["target"]
            target_alias = target["alias"]

            display_property = (
                relation["display"]["property"]
            )

            # 取得 target mapping
            target_entity = target["entity"]

            display_column = (
                self.mapper.get_property_column(
                    target_entity,
                    display_property,
                )
            )

            return (
                f"{target_alias}."
                f"{display_column} "
                f"AS {field}",
                [join],
            )

        raise ValueError(
            f"Unknown field: "
            f"{entity}.{field}"
        )

    # ======================================================
    # Filter
    # ======================================================

    def _build_filter(
        self,
        entity: str,
        field: str,
        operator: str,
        value,
        index: int,
    ):
        param_name = f"filter_{index}"
        
        #2026/08/31
        field = field.split(".")[0]
        
        alias = self.mapper.get_alias(
            entity
        )

        properties = self.mapper.get_properties(
            entity
        )

        # ======================================================
        # Property
        # ======================================================

        if field in properties:

            column = self.mapper.get_property_column(
                entity,
                field,
            )

            property_info = properties[field]

            data_type = property_info.get(
                "type",
                "string",
            )

            column_sql = f"{alias}.{column}"

            # ----------------------------------------------
            # LIKE
            # ----------------------------------------------

            if operator == "LIKE":

                return (
                    f"{column_sql} LIKE :{param_name}",
                    {
                        param_name: f"%{value}%"
                    },
                    [],
                )

            # ----------------------------------------------
            # IN
            # ----------------------------------------------

            if operator == "IN":

                if not isinstance(value, list):
                    raise ValueError(
                        "IN operator requires a list"
                    )

                placeholders = []

                params = {}

                for i, item in enumerate(value):

                    name = (
                        f"{param_name}_{i}"
                    )

                    placeholders.append(
                        f":{name}"
                    )

                    params[name] = item

                return (
                    f"{column_sql} IN "
                    f"({', '.join(placeholders)})",
                    params,
                    [],
                )

            # ----------------------------------------------
            # Comparison
            # ----------------------------------------------

            allowed_operators = {
                "=",
                "!=",
                ">",
                ">=",
                "<",
                "<=",
            }

            if operator not in allowed_operators:
                raise ValueError(
                    f"Unsupported operator: "
                    f"{operator}"
                )

            return (
                f"{column_sql} "
                f"{operator} "
                f":{param_name}",
                {
                    param_name: value
                },
                [],
            )

        # ======================================================
        # Relation
        # ======================================================

        relations = self.mapper.get_relations(
            entity
        )

        if field in relations:

            relation = self.mapper.get_relation(
                entity,
                field,
            )

            join = self._build_relation_join(
                entity,
                relation,
            )

            target = relation["target"]

            target_entity = target["entity"]
            target_alias = target["alias"]

            display_property = (
                relation["display"]["property"]
            )

            target_column = (
                self.mapper.get_property_column(
                    target_entity,
                    display_property,
                )
            )

            column_sql = (
                f"{target_alias}.{target_column}"
            )

            if operator == "LIKE":

                return (
                    f"{column_sql} LIKE :{param_name}",
                    {
                        param_name: f"%{value}%"
                    },
                    [join],
                )

            if operator != "=":

                raise ValueError(
                    f"Relation field "
                    f"'{field}' only supports "
                    f"LIKE or = currently."
                )

            return (
                f"{column_sql} = :{param_name}",
                {
                    param_name: value
                },
                [join],
            )

        raise ValueError(
            f"Unknown filter: "
            f"{entity}.{field}"
        )


    def _build_relation_join(
        self,
        entity: str,
        relation: dict,
    ) -> str:
        """
        根據 YAML Mapping 建立 JOIN。

        例如：

        Asset.location

        YAML:
            source:
            foreign_key: location_id

            target:
            table: locations
            alias: l
            key: id

        會產生：

            LEFT JOIN locations l
                ON a.location_id = l.id
        """

        # ======================================================
        # Source
        # ======================================================

        source = self.mapper.get_source(
            entity
        )

        source_alias = source.get(
            "alias",
            "t",
        )

        # ======================================================
        # Foreign Key
        # ======================================================

        source_config = relation.get(
            "source",
            {}
        )

        foreign_key = source_config.get(
            "foreign_key"
        )

        if not foreign_key:
            raise ValueError(
                f"Relation '{entity}' "
                f"does not define "
                f"source.foreign_key"
            )

        # ======================================================
        # Target
        # ======================================================

        target = relation.get(
            "target",
            {}
        )

        target_table = target.get(
            "table"
        )

        target_alias = target.get(
            "alias"
        )

        target_key = target.get(
            "key"
        )

        if not target_table:
            raise ValueError(
                f"Relation '{entity}' "
                f"does not define "
                f"target.table"
            )

        if not target_alias:
            raise ValueError(
                f"Relation '{entity}' "
                f"does not define "
                f"target.alias"
            )

        if not target_key:
            raise ValueError(
                f"Relation '{entity}' "
                f"does not define "
                f"target.key"
            )

        # ======================================================
        # Build JOIN
        # ======================================================

        return (
            f"LEFT JOIN {target_table} {target_alias}\n"
            f"    ON {source_alias}.{foreign_key} "
            f"= {target_alias}.{target_key}"
        )


    # ======================================================
    # JOIN
    # ======================================================

    def _build_relation_join(
        self,
        entity: str,
        relation: dict[str, Any],
    ) -> str:

        source = self.mapper.get_source(
            entity
        )

        source_alias = source.get(
            "alias",
            "t",
        )

        foreign_key = (
            relation["source"]["foreign_key"]
        )

        target = relation["target"]

        target_table = target["table"]
        target_alias = target["alias"]
        target_key = target["key"]

        return (
            f"LEFT JOIN "
            f"{target_table} "
            f"{target_alias}\n"
            f"    ON "
            f"{source_alias}.{foreign_key} "
            f"= "
            f"{target_alias}.{target_key}"
        )

    # ======================================================
    # ORDER BY
    # ======================================================

    def _build_order_by(
        self,
        entity: str,
        order_by: dict[str, Any],
    ) -> str:

        field = order_by.get(
            "field"
        )

        direction = str(
            order_by.get(
                "direction",
                "ASC",
            )
        ).upper()

        if direction not in {
            "ASC",
            "DESC",
        }:
            raise ValueError(
                f"Invalid order direction: "
                f"{direction}"
            )

        field_sql, joins = (
            self._build_field(
                entity,
                field,
            )
        )

        # 取得 SQL alias
        alias = (
            field_sql.split(" AS ")[-1]
        )

        return (
            f"{alias} {direction}"
        )