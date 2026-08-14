from pathlib import Path
from typing import Any

import yaml


class SemanticMapper:
    """
    負責載入與提供 Semantic Mapping。

    YAML:
        semantic/mappings/*.yaml

    例如：

        Asset.name
            ↓
        assets.name

        Asset.category
            ↓
        categories.name
    """

    def __init__(self, mapping_dir: str | Path):
        self.mapping_dir = Path(mapping_dir)

        if not self.mapping_dir.exists():
            raise FileNotFoundError(
                f"Mapping directory not found: "
                f"{self.mapping_dir}"
            )

        self.mappings: dict[str, dict[str, Any]] = {}

        self._load()

    # ======================================================
    # Load
    # ======================================================

    def _load(self) -> None:

        yaml_files = list(
            self.mapping_dir.glob("*.yaml")
        )

        if not yaml_files:
            raise FileNotFoundError(
                f"No YAML mapping found in: "
                f"{self.mapping_dir}"
            )

        for file_path in yaml_files:
            
            print(f"--> 正在載入檔案: {file_path.resolve()}")
            with open(
                file_path,
                "r",
                encoding="utf-8",
            ) as f:

                data = yaml.safe_load(f)

            if not data:
                continue

            entity = data.get("entity")

            if not entity:
                raise ValueError(
                    f"Mapping file '{file_path}' "
                    f"does not define 'entity'"
                )

            self.mappings[entity] = data

    # ======================================================
    # Entity
    # ======================================================

    def get_entity(
        self,
        entity: str,
    ) -> dict[str, Any]:

        if entity not in self.mappings:
            raise ValueError(
                f"Unknown semantic entity: {entity}"
            )

        return self.mappings[entity]

    # ======================================================
    # Source
    # ======================================================

    def get_source(
        self,
        entity: str,
    ) -> dict[str, Any]:

        mapping = self.get_entity(entity)

        source = mapping.get(
            "source",
            {},
        )

        if not source:
            raise ValueError(
                f"Entity '{entity}' "
                f"does not define source"
            )

        return source

    def get_table(
        self,
        entity: str,
    ) -> str:

        source = self.get_source(entity)

        table = source.get("table")

        if not table:
            raise ValueError(
                f"Entity '{entity}' "
                f"does not define source.table"
            )

        return table

    def get_alias(
        self,
        entity: str,
    ) -> str:

        source = self.get_source(entity)

        return source.get(
            "alias",
            entity.lower(),
        )

    # ======================================================
    # Properties
    # ======================================================

    def get_properties(
        self,
        entity: str,
    ) -> dict[str, Any]:

        mapping = self.get_entity(entity)

        return mapping.get(
            "properties",
            {},
        )

    def get_property(
        self,
        entity: str,
        property_name: str,
    ) -> dict[str, Any]:

        properties = self.get_properties(
            entity
        )

        if property_name not in properties:
            raise ValueError(
                f"Unknown property: "
                f"{entity}.{property_name}"
            )

        return properties[property_name]

    def get_property_column(
        self,
        entity: str,
        property_name: str,
    ) -> str:

        property_mapping = self.get_property(
            entity,
            property_name,
        )

        column = property_mapping.get(
            "column"
        )

        if not column:
            raise ValueError(
                f"Property '{entity}.{property_name}' "
                f"does not define column"
            )

        return column

    # ======================================================
    # Relations
    # ======================================================

    def get_relations(
        self,
        entity: str,
    ) -> dict[str, Any]:

        mapping = self.get_entity(entity)

        return mapping.get(
            "relations",
            {},
        )

    def get_relation(
        self,
        entity: str,
        relation_name: str,
    ) -> dict[str, Any]:

        relations = self.get_relations(
            entity
        )

        if relation_name not in relations:
            raise ValueError(
                f"Unknown relation: "
                f"{entity}.{relation_name}"
            )

        return relations[relation_name]