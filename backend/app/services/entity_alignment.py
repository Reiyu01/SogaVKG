"""Preview and validate concept-level Identity Mappings."""

from collections import Counter
from typing import Any

from app.adapters.source_adapter import SourceAdapter
from app.services.source_resolution import mapping_table


def _is_empty(value: Any) -> bool:
    return value is None or value == ""


def normalize_identity_key(value: Any, rule: str = "exact") -> Any:
    """Apply only explicit, safe normalizations selected by the user."""
    if _is_empty(value) or rule == "exact":
        return value
    if not isinstance(value, str):
        return value
    if rule == "trim":
        return value.strip()
    if rule == "trim_casefold":
        return value.strip().casefold()
    raise ValueError(f"Unsupported identity normalization rule: {rule}")


def _summary(rows: list[dict[str, Any]], column: str, normalization_rule: str) -> dict[str, Any]:
    values = [normalize_identity_key(row.get(column), normalization_rule) for row in rows]
    non_empty = [value for value in values if not _is_empty(value)]
    counts = Counter(non_empty)
    duplicates = [(value, occurrences) for value, occurrences in counts.items() if occurrences > 1]
    duplicates.sort(key=lambda item: (-item[1], str(item[0])))
    return {
        "rows": len(rows),
        "null_key_count": len(values) - len(non_empty),
        "null_key_samples": [row for row in rows if _is_empty(row.get(column))][:20],
        "keys": set(counts),
        "duplicate_key_count": len(duplicates),
        "duplicate_row_count": sum(occurrences - 1 for _, occurrences in duplicates),
        "duplicate_key_samples": [{"key": value, "occurrences": occurrences} for value, occurrences in duplicates[:20]],
    }


def preview_entity_alignment(
    source_mapping: dict[str, Any],
    target_mapping: dict[str, Any],
    source_adapter: SourceAdapter,
    target_adapter: SourceAdapter,
    source_column: str,
    target_column: str,
    normalization_rule: str = "exact",
) -> dict[str, Any]:
    """Return source-neutral match statistics for a proposed identity mapping.

    Empty keys are never matched. A mapping is publishable only when each
    non-empty key occurs once or less on both sides. Unmatched keys are useful
    diagnostics but do not make a one-to-one mapping unsafe.
    """
    source_rows = source_adapter.read_rows(mapping_table(source_mapping) or "")
    target_rows = target_adapter.read_rows(mapping_table(target_mapping) or "")
    source = _summary(source_rows, source_column, normalization_rule)
    target = _summary(target_rows, target_column, normalization_rule)
    matched_keys = source["keys"] & target["keys"]
    source_only = source["keys"] - target["keys"]
    target_only = target["keys"] - source["keys"]
    safe = not source["duplicate_key_count"] and not target["duplicate_key_count"]
    return {
        "source": {key: value for key, value in source.items() if key != "keys"},
        "target": {key: value for key, value in target.items() if key != "keys"},
        "exact_match_count": len(matched_keys),
        "source_unmatched_count": len(source_only),
        "target_unmatched_count": len(target_only),
        "source_unmatched_samples": [{"key": value} for value in sorted(source_only, key=str)[:20]],
        "target_unmatched_samples": [{"key": value} for value in sorted(target_only, key=str)[:20]],
        "one_to_one_valid": safe,
        "normalization_rule": normalization_rule,
        "blocking_errors": ([] if safe else ["Identity Mapping 的非空比對鍵必須在兩個 Entity 中都唯一。"]),
    }
