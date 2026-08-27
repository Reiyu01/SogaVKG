import pytest
from pydantic import ValidationError

from app.models.query import OrderBy, QueryExecution, SemanticQueryPlan


def test_semantic_plan_forbids_unknown_and_raw_sql_fields() -> None:
    with pytest.raises(ValidationError):
        SemanticQueryPlan.model_validate({"entity": "Asset", "sql": "SELECT * FROM assets"})


@pytest.mark.parametrize(
    "payload",
    [
        {"entity": "Asset", "limit": "20"},
        {"entity": "Asset", "limit": 0},
        {"entity": "Asset", "fields": [1]},
        {"entity": "Asset", "filters": {"quantity": [1]}},
    ],
)
def test_semantic_plan_rejects_invalid_types_and_limit(payload: dict) -> None:
    with pytest.raises(ValidationError):
        SemanticQueryPlan.model_validate(payload)


def test_order_by_is_strict_and_extra_forbid() -> None:
    with pytest.raises(ValidationError):
        OrderBy.model_validate({"field": "name", "direction": "down"})
    with pytest.raises(ValidationError):
        OrderBy.model_validate({"field": "name", "direction": "ASC", "sql": "name"})


def test_query_execution_is_extra_forbid() -> None:
    with pytest.raises(ValidationError):
        QueryExecution.model_validate(
            {
                "answer": "",
                "query_type": "unsupported",
                "status": "unsupported",
                "executed": False,
                "insufficient": True,
                "row_count": 0,
                "elapsed_ms": 0.0,
                "raw_sql": "SELECT 1",
            }
        )
