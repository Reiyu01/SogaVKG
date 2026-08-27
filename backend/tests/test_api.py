from pathlib import Path

from fastapi.testclient import TestClient

from app.adapters.read_only import DatabaseDependencyError
from app.core.config import Settings
from app.core.runtime import QueryRuntime
from app.main import create_app
from app.models.query import (
    QueryExecution,
    QueryStatus,
    QueryType,
    RowSource,
    SemanticQueryPlan,
)
from app.semantic.mapper import SemanticMapper
from app.services.query_policy import QueryPolicy
from app.services.query_service import QueryDependencyError


PROJECT_ROOT = Path(__file__).resolve().parents[2]


class StubDatabase:
    def __init__(self, ready: bool = True):
        self.ready = ready

    def execute(self, query: str, params: dict | None = None) -> list[dict]:
        return []

    def check_readiness(self) -> None:
        if not self.ready:
            raise DatabaseDependencyError("private database path must not leak")


class StubService:
    def query(self, question: str) -> QueryExecution:
        if question == "dependency":
            raise QueryDependencyError("internal provider details")
        if question == "unsupported":
            return QueryExecution(
                answer="目前 MVP 只支援唯讀 Asset 查詢",
                query_type=QueryType.UNSUPPORTED,
                status=QueryStatus.UNSUPPORTED,
                executed=False,
                insufficient=True,
                row_count=0,
                warnings=["目前 MVP 只支援唯讀 Asset 查詢"],
                elapsed_ms=1.0,
            )
        if question == "missing":
            return QueryExecution(
                answer="目前資料查無符合項目。",
                query_type=QueryType.ASSET_QUERY,
                status=QueryStatus.NO_RESULTS,
                executed=True,
                insufficient=True,
                plan=SemanticQueryPlan(
                    entity="Asset",
                    fields=["asset_code", "name"],
                    limit=20,
                ),
                row_count=0,
                elapsed_ms=1.0,
            )
        return QueryExecution(
            answer="找到 ESP32 [1]",
            query_type=QueryType.ASSET_QUERY,
            status=QueryStatus.ANSWERED,
            executed=True,
            insufficient=False,
            plan=SemanticQueryPlan(
                entity="Asset",
                fields=["asset_code", "name", "location"],
                filters={"location": "C217"},
                limit=20,
            ),
            row_count=1,
            elapsed_ms=2.0,
            sources=[
                RowSource(
                    number=1,
                    record_key="A001",
                    fields={
                        "asset_code": "A001",
                        "name": "ESP32",
                        "location": "C217",
                    },
                )
            ],
        )


def make_runtime(*, ready: bool = True) -> QueryRuntime:
    return QueryRuntime(
        settings=Settings(),
        mapper=SemanticMapper(PROJECT_ROOT / "semantic" / "mappings"),
        policy=QueryPolicy(),
        database=StubDatabase(ready=ready),  # type: ignore[arg-type]
        service=StubService(),  # type: ignore[arg-type]
    )


def test_query_contract_returns_required_public_fields() -> None:
    with TestClient(create_app(runtime=make_runtime())) as client:
        response = client.post("/api/v1/query", json={"question": "C217 有 ESP32 嗎"})
    assert response.status_code == 200
    body = response.json()
    required = {
        "answer",
        "query_type",
        "status",
        "executed",
        "insufficient",
        "plan",
        "row_count",
        "truncated",
        "warnings",
        "elapsed_ms",
        "trace",
        "sources",
    }
    assert required <= set(body)
    assert body["status"] == "answered"
    assert body["sources"][0]["record_key"] == "A001"
    assert "sql" not in str(body).casefold()


def test_query_request_is_strict_and_bounded() -> None:
    with TestClient(create_app(runtime=make_runtime())) as client:
        assert client.post("/api/v1/query", json={"question": "   "}).status_code == 422
        assert client.post(
            "/api/v1/query",
            json={"question": "x" * 8001},
        ).status_code == 422
        assert client.post(
            "/api/v1/query",
            json={"question": "valid", "history": []},
        ).status_code == 422
        assert client.post("/api/v1/query", json={"question": 123}).status_code == 422


def test_unsupported_and_no_results_are_http_200_domain_results() -> None:
    with TestClient(create_app(runtime=make_runtime())) as client:
        unsupported = client.post("/api/v1/query", json={"question": "unsupported"})
        no_results = client.post("/api/v1/query", json={"question": "missing"})
    assert unsupported.status_code == 200
    assert unsupported.json()["status"] == "unsupported"
    assert unsupported.json()["executed"] is False
    assert no_results.status_code == 200
    assert no_results.json()["status"] == "no_results"
    assert no_results.json()["sources"] == []


def test_query_dependency_failure_is_generic_503() -> None:
    with TestClient(create_app(runtime=make_runtime())) as client:
        response = client.post("/api/v1/query", json={"question": "dependency"})
    assert response.status_code == 503
    assert response.json() == {"detail": "query dependency unavailable"}
    assert "provider" not in response.text


def test_liveness_and_readiness_endpoints() -> None:
    with TestClient(create_app(runtime=make_runtime())) as client:
        live = client.get("/api/v1/health/live")
        ready = client.get("/api/v1/health/ready")
    assert live.status_code == 200
    assert live.json() == {"status": "ok"}
    assert ready.status_code == 200
    assert ready.json() == {"status": "ready"}


def test_readiness_dependency_failure_is_generic_503() -> None:
    with TestClient(create_app(runtime=make_runtime(ready=False))) as client:
        response = client.get("/api/v1/health/ready")
    assert response.status_code == 503
    assert response.json() == {"detail": "query dependency unavailable"}
    assert "path" not in response.text
