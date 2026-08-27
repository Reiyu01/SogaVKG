import sqlite3
from pathlib import Path

import pytest
from pydantic import ValidationError

from app.adapters.read_only import SQLiteReadOnlyAdapter
from app.ai.answer_generator import GroundedAnswerGenerator
from app.ai.planner import NaturalLanguagePlanner
from app.evaluation.models import EvaluationCase, EvaluationDataset
from app.evaluation.runner import EvaluationRunner, load_dataset
from app.models.query import (
    QueryExecution,
    QueryStatus,
    QueryType,
    RowSource,
    SemanticQueryPlan,
)
from app.semantic.mapper import SemanticMapper
from app.semantic.query_builder import SemanticQueryBuilder
from app.services.query_policy import QueryPolicy
from app.services.query_service import QueryDependencyError, QueryService


PROJECT_ROOT = Path(__file__).resolve().parents[2]
FIXTURE_PATH = PROJECT_ROOT / "backend" / "evaluation" / "lab_mvp.json"


class StubService:
    def __init__(self, responses: dict[str, QueryExecution | Exception]):
        self.responses = responses
        self.calls: list[str] = []

    def query(self, question: str) -> QueryExecution:
        self.calls.append(question)
        response = self.responses[question]
        if isinstance(response, Exception):
            raise response
        return response


class FakeChatModel:
    def __init__(self, responses: list[str]):
        self.responses = list(responses)

    def complete(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        timeout_seconds: float,
    ) -> str:
        return self.responses.pop(0)


def answered_execution(*, citation: str = "[1]") -> QueryExecution:
    return QueryExecution(
        answer=f"找到 A001 {citation}",
        query_type=QueryType.ASSET_QUERY,
        status=QueryStatus.ANSWERED,
        executed=True,
        insufficient=False,
        plan=SemanticQueryPlan(
            entity="Asset",
            fields=["asset_code", "name"],
            limit=10,
        ),
        row_count=1,
        elapsed_ms=6.0,
        planning_calls=1,
        sources=[
            RowSource(
                number=1,
                record_key="A001",
                fields={"asset_code": "A001", "name": "ESP32"},
            )
        ],
    )


def unsupported_execution() -> QueryExecution:
    return QueryExecution(
        answer="目前 MVP 只支援唯讀 Asset 查詢",
        query_type=QueryType.UNSUPPORTED,
        status=QueryStatus.UNSUPPORTED,
        executed=False,
        insufficient=True,
        row_count=0,
        warnings=["目前 MVP 只支援唯讀 Asset 查詢"],
        elapsed_ms=3.0,
    )


def test_dataset_rejects_empty_invalid_and_duplicate_cases() -> None:
    with pytest.raises(ValidationError):
        EvaluationDataset(name="empty", version="1", cases=[])
    with pytest.raises(ValidationError):
        EvaluationCase.model_validate(
            {"id": "bad", "question": "x", "unknown": True}
        )
    case = EvaluationCase(
        id="duplicate",
        question="x",
        expected_status=QueryStatus.UNSUPPORTED,
    )
    with pytest.raises(ValidationError):
        EvaluationDataset(name="bad", version="1", cases=[case, case])


def test_lab_fixture_is_strict_and_covers_required_safety_cases() -> None:
    dataset = load_dataset(FIXTURE_PATH)
    case_ids = {case.id for case in dataset.cases}
    assert {
        "asset-location-normal",
        "asset-required-code",
        "no-results",
        "unknown-field",
        "raw-sql",
        "sql-injection-value",
        "borrow-record-pii",
        "write-request",
        "invalid-citation",
        "dependency-failure",
    } <= case_ids


def test_runner_reports_traceable_checks_and_correct_aggregates() -> None:
    answered = EvaluationCase(
        id="answered",
        question="answered",
        expected_query_type=QueryType.ASSET_QUERY,
        expected_status=QueryStatus.ANSWERED,
        required_record_keys=["A001"],
        expected_fields=["asset_code", "name"],
        expect_plan_valid=True,
        expect_refusal=False,
    )
    unsupported = EvaluationCase(
        id="unsupported",
        question="unsupported",
        expected_query_type=QueryType.UNSUPPORTED,
        expected_status=QueryStatus.UNSUPPORTED,
        expect_refusal=True,
        expect_warning=True,
    )
    dependency = EvaluationCase(
        id="dependency",
        question="dependency",
        expected_status=QueryStatus.DEPENDENCY_ERROR,
        expect_warning=True,
    )
    dataset = EvaluationDataset(
        name="unit",
        version="1",
        cases=[answered, unsupported, dependency],
    )
    service = StubService(
        {
            "answered": answered_execution(),
            "unsupported": unsupported_execution(),
            "dependency": QueryDependencyError("private detail"),
        }
    )
    report = EvaluationRunner(service).run(dataset)  # type: ignore[arg-type]
    assert service.calls == ["answered", "unsupported", "dependency"]
    assert report.metrics.case_count == 3
    assert report.metrics.query_type_accuracy == 1.0
    assert report.metrics.plan_validity == 1.0
    assert report.metrics.required_record_recall == 1.0
    assert report.metrics.expected_field_coverage == 1.0
    assert report.metrics.status_accuracy == 1.0
    assert report.metrics.citation_validity == 1.0
    assert report.metrics.average_planning_calls == pytest.approx(1 / 3)
    assert all(result.checks for result in report.results)
    assert all(result.passed for result in report.results)


def test_invalid_citation_is_visible_in_case_and_aggregate() -> None:
    dataset = EvaluationDataset(
        name="citation",
        version="1",
        cases=[
            EvaluationCase(
                id="bad-citation",
                question="bad",
                expected_status=QueryStatus.ANSWERED,
            )
        ],
    )
    report = EvaluationRunner(
        StubService({"bad": answered_execution(citation="[99]")})  # type: ignore[arg-type]
    ).run(dataset)
    assert report.metrics.citation_validity == 0.0
    assert report.results[0].passed is False
    citation_check = next(
        check for check in report.results[0].checks if check.name == "citation_validity"
    )
    assert citation_check.passed is False


def test_production_query_service_evaluation_keeps_database_unchanged(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "evaluation.db"
    with sqlite3.connect(database_path) as connection:
        connection.executescript(
            """
            CREATE TABLE categories (id INTEGER PRIMARY KEY, name TEXT);
            CREATE TABLE locations (id INTEGER PRIMARY KEY, name TEXT);
            CREATE TABLE assets (
                id INTEGER PRIMARY KEY,
                asset_code TEXT,
                name TEXT,
                quantity REAL,
                status TEXT,
                specification TEXT,
                note TEXT,
                category_id INTEGER,
                location_id INTEGER
            );
            INSERT INTO locations(id, name) VALUES (1, 'C217');
            INSERT INTO assets(id, asset_code, name, quantity, status, location_id)
            VALUES (1, 'A001', 'ESP32', 1, 'available', 1);
            """
        )

    mapper = SemanticMapper(PROJECT_ROOT / "semantic" / "mappings")
    policy = QueryPolicy(default_limit=10, maximum_limit=10)
    planner_model = FakeChatModel(
        [
            '{"query_type":"asset_query","plan":{"entity":"Asset",'
            '"fields":["name","location"],"filters":{"asset_code":"A001"},"limit":10}}',
            '{"query_type":"asset_query","plan":{"entity":"Asset",'
            '"fields":["name"],"filters":{"name":"missing"},"limit":10}}',
        ]
    )
    service = QueryService(
        planner=NaturalLanguagePlanner(planner_model),
        policy=policy,
        builder=SemanticQueryBuilder(
            mapper,
            default_fields=policy.public_default_fields,
            default_limit=policy.default_limit,
            maximum_limit=policy.maximum_limit,
        ),
        database=SQLiteReadOnlyAdapter(database_path),
        answer_generator=GroundedAnswerGenerator(
            FakeChatModel(['{"answer":"找到 ESP32 [1]"}'])
        ),
    )
    dataset = EvaluationDataset(
        name="read-only",
        version="1",
        cases=[
            EvaluationCase(
                id="found",
                question="find",
                expected_status=QueryStatus.ANSWERED,
                required_record_keys=["A001"],
            ),
            EvaluationCase(
                id="missing",
                question="missing",
                expected_status=QueryStatus.NO_RESULTS,
            ),
        ],
    )
    with sqlite3.connect(database_path) as connection:
        before = connection.execute("SELECT * FROM assets ORDER BY id").fetchall()
    report = EvaluationRunner(service).run(dataset)
    with sqlite3.connect(database_path) as connection:
        after = connection.execute("SELECT * FROM assets ORDER BY id").fetchall()
    assert before == after
    assert report.metrics.status_accuracy == 1.0
    assert report.metrics.required_record_recall == 1.0
