"""
此程式碼負責將YAML映射轉換成AI看的說明文字
"""

from app.semantic.mapper import SemanticMapper


def build_schema_description(mapper: SemanticMapper, entity_alignments: list[dict] | None = None) -> str:
    """
    把所有已載入的語義映射，轉成給 AI 看的純文字說明，
    讓 AI 知道有哪些 entity、property、relation 可以查詢。
    """
    lines = []

    for entity, mapping in mapper.mappings.items():
        label = mapping.get("label", entity)
        lines.append(f"## Entity: {entity}（{label}）")

        properties = mapping.get("properties", {})
        if properties:
            lines.append("屬性欄位（properties）：")
            for name, info in properties.items():
                prop_label = info.get("label", name)
                prop_type = info.get("type", "string")
                lines.append(f"  - {name}（{prop_label}, type={prop_type}）")

        relations = mapping.get("relations", {})
        if relations:
            lines.append("關聯欄位（relations，會自動 JOIN）：")
            for name, info in relations.items():
                rel_label = info.get("label", name)
                target_entity = info["target"]["entity"]
                lines.append(
                    f"  - {name}（{rel_label}, 關聯到 {target_entity}）"
                )

        lines.append("")  # 空行分隔

    if entity_alignments:
        lines.append("## 概念對應（不是資料列關係）")
        for alignment in entity_alignments:
            lines.append(
                f"  - {alignment['source_entity']} 與 {alignment['target_entity']} 是同一概念的不同來源版本"
                f"（{alignment['source_column']} = {alignment['target_column']}，{alignment['label']}）。"
                "需要比對個別資料時，使用此欄位規則；保留兩邊來源資料，不可自行覆寫衝突值。"
            )
        lines.append("")
    return "\n".join(lines)
