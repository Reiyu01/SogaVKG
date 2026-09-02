from pathlib import Path

from app.schemas.semantic_query import (
    SemanticQuery,
    QueryFilter,
)

from app.semantic.mapper import (
    SemanticMapper,
)

from app.semantic.query_builder import (
    SemanticQueryBuilder,
)


BASE_DIR = Path(__file__).resolve().parents[2]

MAPPING_DIR = (
    BASE_DIR
    / "semantic"
    / "mappings"
)


def main():

    mapper = SemanticMapper(
        MAPPING_DIR
    )

    builder = SemanticQueryBuilder(
        mapper
    )

    query = SemanticQuery(
        entity="Asset",

        fields=[
            "asset_code",
            "name",
            "quantity",
            "status",
            "category",
            "location",
        ],

        filters=[
            QueryFilter(
                field="name",
                operator="LIKE",
                value="ESP32",
            ),

            QueryFilter(
                field="location",
                operator="LIKE",
                value="C217",
            ),
        ],

        limit=20,
    )

    result = builder.build(
        query
    )

    print("=" * 60)
    print("Semantic Query")
    print("=" * 60)

    print(query.model_dump())

    print()
    print("=" * 60)
    print("Generated SQL")
    print("=" * 60)

    print(result.sql)

    print()
    print("=" * 60)
    print("Parameters")
    print("=" * 60)

    print(result.params)


if __name__ == "__main__":
    main()