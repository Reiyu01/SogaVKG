import time
from typing import Any

from app.adapters.read_only import (
    DatabaseDependencyError,
    QuerySafetyError,
    ReadOnlyDatabasePort,
)
from app.ai.answer_generator import GroundedAnswerGenerator
from app.ai.planner import NaturalLanguagePlanner
from app.ai.ports import ModelDependencyError
from app.models.query import (
    QueryExecution,
    QueryStatus,
    QueryTraceEvent,
    QueryType,
    RowSource,
    SemanticQueryPlan,
)
from app.semantic.query_builder import SemanticQueryBuilder
from app.services.query_policy import QueryPolicy, QueryPolicyError


class QueryDependencyError(RuntimeError):
    """A runtime dependency prevented a valid query from completing."""


class QueryService:
    """Transport-independent orchestration for every MVP query interface."""

    def __init__(
        self,
        *,
        planner: NaturalLanguagePlanner,
        policy: QueryPolicy,
        builder: SemanticQueryBuilder,
        database: ReadOnlyDatabasePort,
        answer_generator: GroundedAnswerGenerator,
    ):
        self.planner = planner
        self.policy = policy
        self.builder = builder
        self.database = database
        self.answer_generator = answer_generator

    @staticmethod
    def _elapsed_ms(started: float) -> float:
        return float(round((time.monotonic() - started) * 1000, 3))

    def _event(
        self,
        trace: list[QueryTraceEvent],
        started: float,
        stage: str,
        status: str,
        detail: str | None = None,
    ) -> None:
        trace.append(
            QueryTraceEvent(
                stage=stage,
                status=status,
                elapsed_ms=self._elapsed_ms(started),
                detail=detail,
            )
        )

    def _finish(
        self,
        *,
        started: float,
        trace: list[QueryTraceEvent],
        answer: str,
        query_type: QueryType,
        status: QueryStatus,
        executed: bool,
        insufficient: bool,
        plan: SemanticQueryPlan | None = None,
        row_count: int = 0,
        truncated: bool = False,
        warnings: list[str] | None = None,
        planning_calls: int = 0,
        sources: list[RowSource] | None = None,
    ) -> QueryExecution:
        self._event(trace, started, "complete", status.value)
        return QueryExecution(
            answer=answer,
            query_type=query_type,
            status=status,
            executed=executed,
            insufficient=insufficient,
            plan=plan,
            row_count=row_count,
            truncated=truncated,
            warnings=warnings or [],
            elapsed_ms=self._elapsed_ms(started),
            planning_calls=planning_calls,
            trace=trace,
            sources=sources or [],
        )

    def _row_sources(self, rows: list[dict[str, Any]]) -> list[RowSource]:
        sources: list[RowSource] = []
        for number, row in enumerate(rows, start=1):
            fields = {
                key: value
                for key, value in row.items()
                if key in self.policy.public_fields
            }
            record_key = fields.get("asset_code")
            if record_key is None or not str(record_key).strip():
                record_key = f"row-{number}"
            sources.append(
                RowSource(
                    number=number,
                    record_key=str(record_key),
                    fields=fields,
                )
            )
        return sources

    def query(self, question: str) -> QueryExecution:
        question = question.strip()
        if not question or len(question) > 8000:
            raise ValueError("question must contain 1 to 8000 characters")

        started = time.monotonic()
        trace: list[QueryTraceEvent] = []
        self._event(trace, started, "request", "accepted")
        try:
            planning = self.planner.plan(question)
        except ModelDependencyError as exc:
            raise QueryDependencyError("query dependency unavailable") from exc
        self._event(
            trace,
            started,
            "planning",
            "valid" if planning.valid else "invalid",
            f"calls={planning.calls}",
        )

        if not planning.valid:
            return self._finish(
                started=started,
                trace=trace,
                answer="無法建立安全且有效的查詢計畫。",
                query_type=planning.query_type,
                status=QueryStatus.INVALID_PLAN,
                executed=False,
                insufficient=True,
                warnings=[planning.warning or "查詢計畫無效"],
                planning_calls=planning.calls,
            )

        if planning.query_type == QueryType.CONVERSATION:
            return self._finish(
                started=started,
                trace=trace,
                answer="您好，我可以協助查詢實驗室的 Asset、Category 與 Location 公開資料。",
                query_type=planning.query_type,
                status=QueryStatus.CONVERSATION,
                executed=False,
                insufficient=False,
                planning_calls=planning.calls,
            )

        if planning.query_type in {QueryType.UNSUPPORTED, QueryType.WRITE}:
            warning = planning.warning or "目前 MVP 只支援唯讀 Asset 查詢"
            return self._finish(
                started=started,
                trace=trace,
                answer=warning,
                query_type=planning.query_type,
                status=QueryStatus.UNSUPPORTED,
                executed=False,
                insufficient=True,
                warnings=[warning],
                planning_calls=planning.calls,
            )

        if planning.plan is None:
            return self._finish(
                started=started,
                trace=trace,
                answer="無法建立安全且有效的查詢計畫。",
                query_type=QueryType.ASSET_QUERY,
                status=QueryStatus.INVALID_PLAN,
                executed=False,
                insufficient=True,
                warnings=["查詢計畫缺少必要內容"],
                planning_calls=planning.calls,
            )

        original_limit = planning.plan.limit
        try:
            plan = self.policy.validate(planning.plan)
            built = self.builder.build(
                plan.model_dump(mode="python"),
                fetch_one_extra=True,
            )
        except (QueryPolicyError, QuerySafetyError, ValueError):
            self._event(trace, started, "policy", "rejected")
            return self._finish(
                started=started,
                trace=trace,
                answer="查詢包含目前不支援的資料範圍或欄位。",
                query_type=QueryType.ASSET_QUERY,
                status=QueryStatus.INVALID_PLAN,
                executed=False,
                insufficient=True,
                warnings=["查詢計畫未通過 Asset-only policy"],
                planning_calls=planning.calls,
            )
        self._event(trace, started, "policy", "approved")

        try:
            fetched_rows = self.database.execute(built.sql, built.params)
        except DatabaseDependencyError as exc:
            raise QueryDependencyError("query dependency unavailable") from exc
        truncated = len(fetched_rows) > built.limit
        rows = fetched_rows[: built.limit]
        self._event(trace, started, "execution", "complete", f"rows={len(rows)}")

        warnings: list[str] = []
        if original_limit is not None and original_limit > self.policy.maximum_limit:
            warnings.append("要求筆數超過上限，已套用 maximum limit")
        if truncated:
            warnings.append("結果已截斷，目前只顯示部分資料")

        sources = self._row_sources(rows)
        if not sources:
            return self._finish(
                started=started,
                trace=trace,
                answer="目前資料查無符合項目。",
                query_type=QueryType.ASSET_QUERY,
                status=QueryStatus.NO_RESULTS,
                executed=True,
                insufficient=True,
                plan=plan,
                warnings=warnings,
                planning_calls=planning.calls,
            )

        try:
            grounded = self.answer_generator.generate(
                question=question,
                sources=sources,
                warnings=warnings,
                truncated=truncated,
            )
        except ModelDependencyError as exc:
            raise QueryDependencyError("query dependency unavailable") from exc
        self._event(
            trace,
            started,
            "grounding",
            "valid" if grounded.valid else "withheld",
            f"calls={grounded.calls}",
        )
        if not grounded.valid or grounded.answer is None:
            warnings.append(grounded.warning or "回答來源驗證失敗")
            return self._finish(
                started=started,
                trace=trace,
                answer="",
                query_type=QueryType.ASSET_QUERY,
                status=QueryStatus.REFUSED,
                executed=True,
                insufficient=True,
                plan=plan,
                row_count=len(rows),
                truncated=truncated,
                warnings=warnings,
                planning_calls=planning.calls,
                sources=sources,
            )

        return self._finish(
            started=started,
            trace=trace,
            answer=grounded.answer,
            query_type=QueryType.ASSET_QUERY,
            status=QueryStatus.ANSWERED,
            executed=True,
            insufficient=False,
            plan=plan,
            row_count=len(rows),
            truncated=truncated,
            warnings=warnings,
            planning_calls=planning.calls,
            sources=sources,
        )
