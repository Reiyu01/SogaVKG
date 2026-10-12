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
        return table in source_profile_tables(source)
    except Exception:
        return False


def source_profile_tables(source: dict[str, Any]) -> set[str]:
    """Inspect a source and retain its real failure for explicit mappings."""
    try:
        schema = create_source_adapter(source["source_type"], source["config"]).inspect_schema()
        return {item["name"] for item in schema["tables"]}
    except Exception as error:
        name = source.get("name") or source.get("id", "unknown")
        raise ValueError(f"Could not inspect source profile {name!r}: {error}") from error


def resolve_entity_source_adapters(mapper: SemanticMapper, sources: list[dict[str, Any]]) -> dict[str, SourceAdapter]:
    """Return one readable source adapter per entity.

    New mappings select ``ingestion.source_id`` explicitly. Older mappings keep
    working by selecting the first enabled project source containing their table.
    """
    usable = [source for source in sources if source.get("active", True)]
    by_id = {source["id"]: source for source in usable}
    adapters: dict[str, SourceAdapter] = {}
    adapter_cache: dict[str, SourceAdapter] = {}
    table_cache: dict[str, set[str]] = {}

    def adapter_for(source: dict[str, Any]) -> SourceAdapter:
        source_id = source["id"]
        if source_id not in adapter_cache:
            adapter_cache[source_id] = create_source_adapter(source["source_type"], source["config"])
        return adapter_cache[source_id]

    def tables_for(source: dict[str, Any]) -> set[str]:
        source_id = source["id"]
        if source_id not in table_cache:
            try:
                table_cache[source_id] = {item["name"] for item in adapter_for(source).inspect_schema()["tables"]}
            except Exception as error:
                name = source.get("name") or source_id
                raise ValueError(f"Could not inspect source profile {name!r}: {error}") from error
        return table_cache[source_id]
    for entity, mapping in mapper.mappings.items():
        table = mapping_table(mapping)
        if not table:
            raise ValueError(f"{entity} has no source table")
        selected_id = mapping.get("ingestion", {}).get("source_id")
        if selected_id:
            source = by_id.get(selected_id)
            if source is None:
                raise ValueError(f"{entity} references unavailable source profile {selected_id!r}")
            # An explicit source selection is the usual Builder path.  Do not
            # call inspect_schema() here: for Google Sheets it reads every tab
            # even though this mapping only needs one.  Looking up its mapped
            # table directly keeps validation/build reads proportional to the
            # Mapping, rather than the size of the entire spreadsheet.
            try:
                adapter_for(source).table_columns(table)
            except Exception as error:
                name = source.get("name") or selected_id
                raise ValueError(
                    f"{entity} is mapped to table {table!r}, but source profile {name!r} "
                    f"(id {selected_id}) cannot read that table: {error}"
                ) from error
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
