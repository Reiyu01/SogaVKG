"""Source-neutral Mapping preview and data-quality summaries."""

from pathlib import Path
from typing import Any

from app.adapters.source_adapter import SQLiteSourceAdapter, SourceAdapter
from app.semantic.mapper import SemanticMapper


def preview_mappings_by_source(mapper: SemanticMapper, sources: dict[str, SourceAdapter] | dict[str, Path]) -> list[dict[str, Any]]:
    """Preview mappings through adapters; Path values remain SQLite-compatible."""
    adapters: dict[str, SourceAdapter] = {
        entity: SQLiteSourceAdapter(value) if isinstance(value, Path) else value
        for entity, value in sources.items()
    }
    preview = []
    for entity, mapping in mapper.mappings.items():
        adapter = adapters[entity]
        ingestion = mapping.get("ingestion", {}); table = ingestion.get("source_table"); primary_key = ingestion.get("primary_key", "id")
        rows = adapter.read_rows(table)
        valid_rows = [row for row in rows if row.get(primary_key) is not None]
        relations = []
        for name, relation in mapping.get("relations", {}).items():
            foreign_key = relation.get("ingestion", {}).get("foreign_key"); target = relation.get("target", {}).get("entity")
            target_mapping = mapper.get_entity(target); target_table = target_mapping.get("ingestion", {}).get("source_table")
            target_key = relation.get("ingestion", {}).get("target_key") or target_mapping.get("ingestion", {}).get("primary_key", "id")
            target_ids = adapters[target].values(target_table, target_key)
            candidates = [row for row in valid_rows if row.get(foreign_key) is not None]
            unmatched = [row for row in candidates if row.get(foreign_key) not in target_ids]
            unmatched_samples = [{"foreign_key": row.get(foreign_key), "primary_key": row.get(primary_key)} for row in candidates if row.get(foreign_key) not in target_ids][:20]
            relations.append({"name": name, "candidates": len(candidates), "matched": len(candidates) - len(unmatched), "unmatched": len(unmatched), "unmatched_samples": unmatched_samples})
        preview.append({"entity": entity, "source_table": table, "rows": len(rows), "nodes": len(valid_rows), "skipped_missing_primary_key": len(rows) - len(valid_rows), "missing_primary_key_samples": [row for row in rows if row.get(primary_key) is None][:20], "duplicate_primary_keys": adapter.duplicate_keys(table, primary_key), "relations": relations})
    return preview


def preview_mappings(mapper: SemanticMapper, db_path: Path) -> list[dict[str, Any]]:
    return preview_mappings_by_source(mapper, {entity: db_path for entity in mapper.mappings})
