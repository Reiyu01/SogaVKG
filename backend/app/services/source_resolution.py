"""Resolve the source adapter used by each mapped entity in a project."""

from pathlib import Path
from typing import Any

from app.adapters.source_adapter import SourceAdapter, create_source_adapter
from app.semantic.mapper import SemanticMapper


def mapping_table(mapping: dict[str, Any]) -> str | None:
    return mapping.get("ingestion", {}).get("source_table") or mapping.get("source", {}).get("table")


def source_contains_table(path: Path, table: str) -> bool:
    """Compatibility helper for callers that only have a SQLite path."""
    return source_profile_contains_table({"source_type": "sqlite", "config": {"path": str(path)}}, table)


def source_profile_contains_table(source: dict[str, Any], table: str) -> bool:
    try:
        return table in {item["name"] for item in create_source_adapter(source["source_type"], source["config"]).inspect_schema()["tables"]}
    except Exception:
        return False


def resolve_entity_source_adapters(mapper: SemanticMapper, sources: list[dict[str, Any]]) -> dict[str, SourceAdapter]:
    """Return one readable source adapter per entity.

    New mappings select ``ingestion.source_id`` explicitly. Older mappings keep
    working by selecting the first enabled project source containing their table.
    """
    usable = [source for source in sources if source.get("active", True)]
    by_id = {source["id"]: source for source in usable}
    adapters: dict[str, SourceAdapter] = {}
    adapter_cache: dict[str, SourceAdapter] = {}

    def adapter_for(source: dict[str, Any]) -> SourceAdapter:
        source_id = source["id"]
        if source_id not in adapter_cache:
            adapter_cache[source_id] = create_source_adapter(source["source_type"], source["config"])
        return adapter_cache[source_id]
    for entity, mapping in mapper.mappings.items():
        table = mapping_table(mapping)
        if not table:
            raise ValueError(f"{entity} has no source table")
        selected_id = mapping.get("ingestion", {}).get("source_id")
        if selected_id:
            source = by_id.get(selected_id)
            if source is None:
                raise ValueError(f"{entity} references unavailable source profile {selected_id!r}")
            if not source_profile_contains_table(source, table):
                raise ValueError(f"{entity} source profile does not contain table {table!r}")
            adapters[entity] = adapter_for(source)
            continue
        source = next((item for item in usable if source_profile_contains_table(item, table)), None)
        if source is None:
            raise ValueError(f"No enabled source contains {entity}.{table}")
        adapters[entity] = adapter_for(source)
    return adapters


def resolve_entity_source_paths(mapper: SemanticMapper, sources: list[dict[str, Any]]) -> dict[str, Path]:
    """Deprecated SQLite-only path resolver retained for compatibility."""
    adapters = resolve_entity_source_adapters(mapper, sources)
    paths: dict[str, Path] = {}
    for entity, adapter in adapters.items():
        if adapter.source_type != "sqlite":
            raise ValueError(f"{entity} is not backed by a SQLite source")
        paths[entity] = adapter.path  # type: ignore[attr-defined]
    return paths
