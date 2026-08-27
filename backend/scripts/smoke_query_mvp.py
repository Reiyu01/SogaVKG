import hashlib
import json

from fastapi.testclient import TestClient

from app.adapters.read_only import SQLiteReadOnlyAdapter
from app.ai.answer_generator import GroundedAnswerGenerator
from app.ai.planner import NaturalLanguagePlanner
from app.core.config import Settings
from app.core.runtime import QueryRuntime
from app.main import create_app
from app.models.query import QueryStatus
from app.semantic.mapper import SemanticMapper
from app.semantic.query_builder import SemanticQueryBuilder
from app.services.query_policy import QueryPolicy
from app.services.query_service import QueryService


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


def database_digest(settings: Settings) -> str:
    return hashlib.sha256(settings.database_path.read_bytes()).hexdigest()


def main() -> None:
    settings = Settings()
    before_digest = database_digest(settings)
    mapper = SemanticMapper(settings.mapping_dir)
    policy = QueryPolicy(
        public_default_fields=settings.public_default_fields,
        default_limit=settings.default_limit,
        maximum_limit=settings.maximum_limit,
    )
    database = SQLiteReadOnlyAdapter(settings.database_path)
    planner = NaturalLanguagePlanner(
        FakeChatModel(
            [
                '{"query_type":"asset_query","plan":{"entity":"Asset",'
                '"fields":["name","location"],"filters":{"asset_code":"PCB-001"},"limit":20}}',
                '{"query_type":"asset_query","plan":{"entity":"Asset",'
                '"fields":["name"],"filters":{"name":"__SOGAVKG_NO_SUCH_ASSET__"},"limit":20}}',
            ]
        )
    )
    answer_generator = GroundedAnswerGenerator(
        FakeChatModel(['{"answer":"找到 PCB-001 的資產資料 [1]"}'])
    )
    service = QueryService(
        planner=planner,
        policy=policy,
        builder=SemanticQueryBuilder(
            mapper,
            default_fields=policy.public_default_fields,
            default_limit=policy.default_limit,
            maximum_limit=policy.maximum_limit,
        ),
        database=database,
        answer_generator=answer_generator,
    )

    asset = service.query("請查詢資產 PCB-001 的名稱與位置")
    no_results = service.query("查詢不存在的測試資產")
    pii = service.query("請列出 BorrowRecord 的 borrower_email")

    runtime = QueryRuntime(
        settings=settings,
        mapper=mapper,
        policy=policy,
        database=database,
        service=service,
    )
    with TestClient(create_app(runtime=runtime)) as client:
        live_status = client.get("/api/v1/health/live").status_code
        ready_status = client.get("/api/v1/health/ready").status_code

    after_digest = database_digest(settings)
    assert asset.status == QueryStatus.ANSWERED
    assert asset.executed is True
    assert asset.sources
    assert asset.sources[0].record_key == "PCB-001"
    assert "[1]" in asset.answer
    assert no_results.status == QueryStatus.NO_RESULTS
    assert no_results.executed is True
    assert no_results.sources == []
    assert pii.status == QueryStatus.UNSUPPORTED
    assert pii.executed is False
    assert pii.sources == []
    assert live_status == 200
    assert ready_status == 200
    assert before_digest == after_digest

    print(
        json.dumps(
            {
                "asset_status": asset.status.value,
                "asset_record_key": asset.sources[0].record_key,
                "no_results_status": no_results.status.value,
                "pii_status": pii.status.value,
                "pii_executed": pii.executed,
                "liveness_http": live_status,
                "readiness_http": ready_status,
                "database_unchanged": before_digest == after_digest,
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
