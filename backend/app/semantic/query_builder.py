from dataclasses import dataclass
from typing import Any

from app.semantic.mapper import SemanticMapper


@dataclass
class QueryResult:
    sql: str
    params: dict[str, Any]
    limit: int
    limit_was_clamped: bool


class SemanticQueryBuilder:

    def __init__(
        self,
        mapper: SemanticMapper,
        default_fields: tuple[str, ...] | None = None,
        default_limit: int = 20,
        maximum_limit: int = 100,
    ):
        self.mapper = mapper

        self.default_fields = default_fields or (
            "asset_code",
            "name",
            "quantity",
            "status",
            "category",
            "location",
        )
        self.default_limit = default_limit
        self.maximum_limit = maximum_limit
        if not self.default_fields:
            raise ValueError("default_fields must not be empty")
        if default_limit < 1 or maximum_limit < default_limit:
            raise ValueError("invalid query limits")

    # ======================================================
    # Public
    # ======================================================

    def build(
        self,
        query: dict[str, Any],
        fetch_one_extra: bool = False,
    ) -> QueryResult:

        entity = query.get("entity")

        if not entity:
            raise ValueError(
                "Query requires 'entity'"
            )

        # 確認 Entity 存在
        self.mapper.get_entity(entity)

        fields = query.get("fields") or list(self.default_fields)

        filters = query.get(
            "filters",
            {},
        )

        joins: list[str] = []
        select_clauses: list[str] = []

        # --------------------------------------------------
        # FROM
        # --------------------------------------------------

        source = self.mapper.get_source(
            entity
        )

        table = source["table"]
        alias = source.get(
            "alias",
            "t",
        )

        # --------------------------------------------------
        # SELECT
        # --------------------------------------------------

        for field in fields:

            select_sql, field_joins = (
                self._build_field(
                    entity,
                    field,
                )
            )

            select_clauses.append(
                select_sql
            )

            joins.extend(
                field_joins
            )


        # --------------------------------------------------
        # WHERE
        # --------------------------------------------------

        where_clauses = []
        params = {}

        for index, (
            field,
            value,
        ) in enumerate(
            filters.items()
        ):

            (
                condition,
                condition_params,
                filter_joins,
            ) = self._build_filter(
                entity,
                field,
                value,
                index,
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

        order_by = query.get("order_by")
        order_by_sql = None
        if order_by:
            order_by_sql, order_joins = self._build_order_by(
                entity,
                order_by,
            )
            joins.extend(order_joins)

        # --------------------------------------------------
        # Remove duplicate joins
        # --------------------------------------------------

        joins = list(
            dict.fromkeys(joins)
        )

        # --------------------------------------------------
        # Build SQL
        # --------------------------------------------------

        sql = (
            "SELECT\n"
            "    "
            + ",\n    ".join(
                select_clauses
            )
            + f"\nFROM {table} {alias}"
        )

        if joins:

            sql += (
                "\n"
                + "\n".join(joins)
            )

        if where_clauses:

            sql += (
                "\nWHERE "
                + "\n  AND ".join(
                    where_clauses
                )
            )

        # --------------------------------------------------
        # ORDER BY
        # --------------------------------------------------

        if order_by_sql:
            sql += "\nORDER BY " + order_by_sql

        # --------------------------------------------------
        # LIMIT
        # --------------------------------------------------

        requested_limit = query.get("limit")
        if requested_limit is None:
            requested_limit = self.default_limit
        if isinstance(requested_limit, bool) or not isinstance(requested_limit, int):
            raise ValueError("limit must be an integer")
        if requested_limit <= 0:
            raise ValueError("limit must be greater than 0")
        limit = min(requested_limit, self.maximum_limit)
        sql_limit = limit + 1 if fetch_one_extra else limit
        sql += f"\nLIMIT {sql_limit}"

        sql += ";"

        return QueryResult(
            sql=sql,
            params=params,
            limit=limit,
            limit_was_clamped=requested_limit > self.maximum_limit,
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
        value: Any,
        index: int,
    ) -> tuple[
        str,
        dict[str, Any],
        list[str],
    ]:

        param_name = (
            f"filter_{index}"
        )

        alias = self.mapper.get_alias(
            entity
        )

        properties = (
            self.mapper.get_properties(
                entity
            )
        )

        # --------------------------------------------------
        # Property filter
        # --------------------------------------------------

        if field in properties:

            column = (
                self.mapper.get_property_column(
                    entity,
                    field,
                )
            )

            property_info = properties[
                field
            ]

            data_type = property_info.get(
                "type",
                "string",
            )

            # 字串使用 LIKE
            if (
                data_type == "string"
                and isinstance(value, str)
            ):

                return (
                    f"{alias}.{column} "
                    f"LIKE :{param_name}",
                    {
                        param_name:
                            f"%{value}%"
                    },
                    [],
                )

            # Number / integer 等
            return (
                f"{alias}.{column} "
                f"= :{param_name}",
                {
                    param_name: value
                },
                [],
            )

        # --------------------------------------------------
        # Relation filter
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

            target_entity = (
                relation["target"]["entity"]
            )

            target_alias = (
                relation["target"]["alias"]
            )

            display_property = (
                relation["display"]["property"]
            )

            target_column = (
                self.mapper.get_property_column(
                    target_entity,
                    display_property,
                )
            )

            return (
                f"{target_alias}.{target_column} "
                f"LIKE :{param_name}",
                {
                    param_name:
                        f"%{value}%"
                },
                [join],
            )

        raise ValueError(
            f"Unknown filter: "
            f"{entity}.{field}"
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
    ) -> tuple[str, list[str]]:

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

        return f"{alias} {direction}", joins
