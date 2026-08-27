from pathlib import Path

import pytest

from app.models.query import SemanticQueryPlan
from app.semantic.mapper import SemanticMapper
from app.semantic.query_builder import SemanticQueryBuilder
from app.services.query_policy import QueryPolicy, QueryPolicyError


PROJECT_ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture
def mapper() -> SemanticMapper:
    return SemanticMapper(PROJECT_ROOT / "semantic" / "mappings")


def test_policy_applies_public_defaults_and_clamps_limit() -> None:
    policy = QueryPolicy(default_limit=2, maximum_limit=3)
    validated = policy.validate(SemanticQueryPlan(entity="Asset", limit=99))
    assert validated.fields == list(policy.public_default_fields)
    assert validated.limit == 3


@pytest.mark.parametrize(
    "plan",
    [
        SemanticQueryPlan(entity="BorrowRecord"),
        SemanticQueryPlan(entity="Asset", fields=["borrower_email"]),
        SemanticQueryPlan(entity="Asset", fields=["id"]),
        SemanticQueryPlan(entity="Asset", fields=["category_id"]),
        SemanticQueryPlan(entity="Asset", fields=["source_sheet"]),
        SemanticQueryPlan(entity="Asset", fields=["unknown_relation"]),
        SemanticQueryPlan(entity="Asset", filters={"borrower_email": "x@example.test"}),
    ],
)
def test_policy_rejects_out_of_scope_entity_pii_and_internal_fields(
    plan: SemanticQueryPlan,
) -> None:
    with pytest.raises(QueryPolicyError):
        QueryPolicy().validate(plan)


def test_builder_uses_safe_defaults_and_mandatory_limit(mapper: SemanticMapper) -> None:
    builder = SemanticQueryBuilder(mapper, default_limit=2, maximum_limit=3)
    result = builder.build({"entity": "Asset"})
    assert "a.*" not in result.sql
    assert "a.asset_code AS asset_code" in result.sql
    assert "c.name AS category" in result.sql
    assert "l.name AS location" in result.sql
    assert "LIMIT 2;" in result.sql
    assert result.limit == 2


def test_builder_clamps_excess_limit_and_joins_relation_sort(mapper: SemanticMapper) -> None:
    builder = SemanticQueryBuilder(mapper, default_limit=2, maximum_limit=3)
    result = builder.build(
        {
            "entity": "Asset",
            "fields": ["name"],
            "order_by": {"field": "location", "direction": "ASC"},
            "limit": 999,
        }
    )
    assert "LEFT JOIN locations l" in result.sql
    assert "ORDER BY location ASC" in result.sql
    assert "LIMIT 3;" in result.sql
    assert result.limit_was_clamped is True


def test_builder_parameterizes_sql_injection_value(mapper: SemanticMapper) -> None:
    payload = "ESP32%'; DROP TABLE assets; --"
    result = SemanticQueryBuilder(mapper).build(
        {
            "entity": "Asset",
            "fields": ["asset_code", "name"],
            "filters": {"name": payload},
        }
    )
    assert payload not in result.sql
    assert result.params == {"filter_0": f"%{payload}%"}
    assert result.sql.count(";") == 1
