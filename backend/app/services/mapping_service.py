from pathlib import Path
from typing import Any

import yaml


class MappingService:
    def __init__(self, mapping_dir: str | Path):
        self.mapping_dir = Path(mapping_dir)
        self.mapping_dir.mkdir(
            parents=True,
            exist_ok=True,
        )

    def list_mappings(self) -> list[dict[str, Any]]:
        result = []

        for file_path in sorted(
            self.mapping_dir.glob("*.yaml")
        ):
            with open(
                file_path,
                "r",
                encoding="utf-8",
            ) as f:
                data = yaml.safe_load(f)

            if data:
                result.append(data)

        return result

    def get_mapping(
        self,
        entity: str,
    ) -> dict[str, Any] | None:

        file_path = self.mapping_dir / f"{entity.lower()}.yaml"

        if not file_path.exists():
            return None

        with open(
            file_path,
            "r",
            encoding="utf-8",
        ) as f:
            return yaml.safe_load(f)

    def save_mapping(
        self,
        mapping: dict[str, Any],
    ) -> Path:

        entity = mapping.get("entity")

        if not entity:
            raise ValueError(
                "mapping.entity is required"
            )

        file_name = f"{entity.lower()}.yaml"
        file_path = self.mapping_dir / file_name

        with open(
            file_path,
            "w",
            encoding="utf-8",
        ) as f:
            yaml.safe_dump(
                mapping,
                f,
                allow_unicode=True,
                sort_keys=False,
            )

        return file_path

    def delete_mapping(
        self,
        entity: str,
    ) -> bool:

        file_path = self.mapping_dir / f"{entity.lower()}.yaml"

        if not file_path.exists():
            return False

        file_path.unlink()

        return True