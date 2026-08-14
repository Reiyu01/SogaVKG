from pathlib import Path

from app.semantic import SemanticMapper, SemanticQueryBuilder
# from app.semantic.query_builder import (
#     SemanticQueryBuilder,
# )


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


    # === 加上這行來檢查實際載入的 key ===
    print("Loaded Relations:", mapper.get_relations("Asset").keys())
    print("Loaded Properties:", mapper.get_properties("Asset").keys())


    builder = SemanticQueryBuilder(
        mapper
    )
    
    query = {
        "entity": "Asset",

        "fields": [
            "asset_code",
            "name",
            "quantity",
            "status",
            "category",
            "location",
        ],

        "filters": {
            "name": "ESP32",
            "location": "C217",
        },

        "limit": 20,
    }

    result = builder.build(
        query
    )

    print("=" * 60)
    print("Semantic Query")
    print("=" * 60)

    print(query)

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