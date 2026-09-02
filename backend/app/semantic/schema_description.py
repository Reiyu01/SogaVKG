"""
此程式碼負責將YAML映射轉換成AI看的說明文字
"""

from app.semantic.mapper import SemanticMapper


def build_schema_description(mapper: SemanticMapper) -> str:
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

    return "\n".join(lines)