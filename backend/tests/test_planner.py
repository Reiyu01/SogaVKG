import time

import pytest

from app.ai.planner import NaturalLanguagePlanner
from app.models.query import QueryType


VALID_PLAN = (
    '{"query_type":"asset_query","plan":{"entity":"Asset",'
    '"fields":["asset_code","name","location"],'
    '"filters":{"location":"C217","name":"ESP32"},"limit":20}}'
)


class FakeModel:
    def __init__(self, responses: list[str], delay_seconds: float = 0):
        self.responses = list(responses)
        self.delay_seconds = delay_seconds
        self.calls: list[dict[str, object]] = []

    def complete(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        timeout_seconds: float,
    ) -> str:
        self.calls.append(
            {
                "system_prompt": system_prompt,
                "user_prompt": user_prompt,
                "timeout_seconds": timeout_seconds,
            }
        )
        if self.delay_seconds:
            time.sleep(self.delay_seconds)
        return self.responses.pop(0)


def test_planner_returns_valid_asset_plan() -> None:
    model = FakeModel([VALID_PLAN])
    result = NaturalLanguagePlanner(model).plan("C217 是否有 ESP32？")
    assert result.valid is True
    assert result.query_type == QueryType.ASSET_QUERY
    assert result.plan is not None
    assert result.plan.filters == {"location": "C217", "name": "ESP32"}
    assert result.calls == 1
    assert "SELECT" not in str(model.calls[0]["system_prompt"])
    assert "C217 5-3-1" in str(model.calls[0]["system_prompt"])


def test_planner_accepts_full_response_json_fence() -> None:
    model = FakeModel([f"```json\n{VALID_PLAN}\n```"])
    result = NaturalLanguagePlanner(model).plan("查詢資產 A001")

    assert result.valid is True
    assert result.plan is not None
    assert result.calls == 1


def test_planner_rejects_json_with_surrounding_prose() -> None:
    model = FakeModel([f"Here is the result:\n{VALID_PLAN}"])
    result = NaturalLanguagePlanner(model, max_calls=1).plan("查詢資產 A001")

    assert result.valid is False
    assert result.plan is None


@pytest.mark.parametrize(
    "invalid_output",
    [
        '{"query_type":"asset_query","plan":{"entity":"Asset","unknown":"name"}}',
        '{"query_type":"asset_query","plan":{"entity":"Asset","sql":"SELECT * FROM assets"}}',
        "not json",
    ],
)
def test_planner_repairs_invalid_unknown_raw_sql_and_malformed_output(
    invalid_output: str,
) -> None:
    model = FakeModel([invalid_output, VALID_PLAN])
    result = NaturalLanguagePlanner(model, max_calls=2).plan("查詢 C217 的 ESP32")
    assert result.valid is True
    assert result.calls == 2
    assert len(model.calls) == 2


def test_planner_fails_closed_when_repair_fails() -> None:
    model = FakeModel(["not json", '{"query_type":"asset_query","sql":"DELETE"}'])
    result = NaturalLanguagePlanner(model, max_calls=2).plan("查詢資產")
    assert result.valid is False
    assert result.plan is None
    assert result.calls == 2
    assert result.warning == "invalid planner output"


def test_planner_stops_after_wall_clock_deadline() -> None:
    model = FakeModel([VALID_PLAN, VALID_PLAN], delay_seconds=0.02)
    result = NaturalLanguagePlanner(
        model,
        max_calls=2,
        deadline_seconds=0.001,
    ).plan("查詢資產")
    assert result.valid is False
    assert result.calls == 1
    assert len(model.calls) == 1
    assert result.warning == "planning deadline exceeded"


@pytest.mark.parametrize(
    ("question", "expected_type"),
    [
        ("你好", QueryType.CONVERSATION),
        ("請給我 BorrowRecord 的 borrower_email", QueryType.UNSUPPORTED),
        ("請統計各地點的資產", QueryType.UNSUPPORTED),
        ("請更新 A001 的狀態", QueryType.WRITE),
        ("DELETE FROM assets", QueryType.WRITE),
    ],
)
def test_non_asset_classification_never_calls_model(
    question: str,
    expected_type: QueryType,
) -> None:
    model = FakeModel([VALID_PLAN])
    result = NaturalLanguagePlanner(model).plan(question)
    assert result.valid is True
    assert result.query_type == expected_type
    assert result.plan is None
    assert result.calls == 0
    assert model.calls == []
