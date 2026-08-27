from dataclasses import dataclass

from app.adapters.read_only import SQLiteReadOnlyAdapter
from app.ai.answer_generator import GroundedAnswerGenerator
from app.ai.llm import OpenAICompatibleChatModel
from app.ai.planner import NaturalLanguagePlanner
from app.core.config import Settings
from app.semantic.mapper import SemanticMapper
from app.semantic.query_builder import SemanticQueryBuilder
from app.services.query_policy import QueryPolicy
from app.services.query_service import QueryService


@dataclass(frozen=True)
class QueryRuntime:
    settings: Settings
    mapper: SemanticMapper
    policy: QueryPolicy
    database: SQLiteReadOnlyAdapter
    service: QueryService


def build_runtime(settings: Settings | None = None) -> QueryRuntime:
    settings = settings or Settings()
    mapper = SemanticMapper(settings.mapping_dir)
    policy = QueryPolicy(
        public_default_fields=settings.public_default_fields,
        default_limit=settings.default_limit,
        maximum_limit=settings.maximum_limit,
    )
    database = SQLiteReadOnlyAdapter(settings.database_path)
    model = OpenAICompatibleChatModel(
        api_key=(
            settings.model_api_key.get_secret_value()
            if settings.model_api_key is not None
            else ""
        ),
        base_url=settings.model_base_url,
        model=settings.model_name,
    )
    planner = NaturalLanguagePlanner(
        model,
        max_calls=settings.planning_max_calls,
        deadline_seconds=settings.planning_deadline_seconds,
    )
    answer_generator = GroundedAnswerGenerator(
        model,
        max_calls=settings.answer_max_calls,
        deadline_seconds=settings.answer_deadline_seconds,
    )
    builder = SemanticQueryBuilder(
        mapper,
        default_fields=policy.public_default_fields,
        default_limit=policy.default_limit,
        maximum_limit=policy.maximum_limit,
    )
    service = QueryService(
        planner=planner,
        policy=policy,
        builder=builder,
        database=database,
        answer_generator=answer_generator,
    )
    return QueryRuntime(
        settings=settings,
        mapper=mapper,
        policy=policy,
        database=database,
        service=service,
    )
