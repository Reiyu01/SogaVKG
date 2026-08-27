import json
import time
from pathlib import Path

from pydantic import Field, model_validator

from app.ai.ports import ChatModelPort, ModelDependencyError
from app.ai.structured_output import load_json_output
from app.models.query import QueryType, SemanticQueryPlan, StrictModel


PROMPT_PATH = Path(__file__).resolve().parent / "prompts" / "planner_v1.md"


class PlannerDecision(StrictModel):
    query_type: QueryType = Field(strict=False)
    plan: SemanticQueryPlan | None = None

    @model_validator(mode="after")
    def validate_plan_presence(self) -> "PlannerDecision":
        if self.query_type == QueryType.ASSET_QUERY and self.plan is None:
            raise ValueError("asset_query requires plan")
        if self.query_type != QueryType.ASSET_QUERY and self.plan is not None:
            raise ValueError("non-asset query must not include plan")
        return self


class PlanningResult(StrictModel):
    query_type: QueryType = Field(strict=False)
    plan: SemanticQueryPlan | None = None
    calls: int = Field(ge=0)
    valid: bool
    warning: str | None = None


class NaturalLanguagePlanner:
    def __init__(
        self,
        model: ChatModelPort,
        *,
        max_calls: int = 2,
        deadline_seconds: float = 15.0,
        prompt_path: Path = PROMPT_PATH,
    ):
        if max_calls < 1 or max_calls > 2:
            raise ValueError("max_calls must be between 1 and 2")
        if deadline_seconds <= 0:
            raise ValueError("deadline_seconds must be positive")
        self.model = model
        self.max_calls = max_calls
        self.deadline_seconds = deadline_seconds
        self.system_prompt = prompt_path.read_text(encoding="utf-8")

    @staticmethod
    def _guarded_classification(question: str) -> QueryType | None:
        normalized = question.casefold().strip()
        write_terms = (
            "新增",
            "修改",
            "更新",
            "刪除",
            "借出",
            "歸還",
            "insert ",
            "update ",
            "delete ",
            "create ",
            "drop ",
        )
        pii_terms = (
            "borrowrecord",
            "borrow_record",
            "borrower_email",
            "借用紀錄",
            "借用人",
            "電子郵件",
            "email",
        )
        aggregation_terms = ("統計", "平均", "總和", "group by", "count(", "聚合")
        conversations = {"你好", "您好", "嗨", "hello", "hi", "謝謝", "thanks"}
        if any(term in normalized for term in write_terms):
            return QueryType.WRITE
        if any(term in normalized for term in pii_terms + aggregation_terms):
            return QueryType.UNSUPPORTED
        if normalized in conversations:
            return QueryType.CONVERSATION
        return None

    def plan(self, question: str) -> PlanningResult:
        guarded_type = self._guarded_classification(question)
        if guarded_type is not None:
            return PlanningResult(
                query_type=guarded_type,
                calls=0,
                valid=True,
                warning=(
                    None
                    if guarded_type == QueryType.CONVERSATION
                    else "目前 MVP 只支援唯讀 Asset 查詢"
                ),
            )

        started = time.monotonic()
        calls = 0
        last_error = "invalid planner output"
        for attempt in range(self.max_calls):
            remaining = self.deadline_seconds - (time.monotonic() - started)
            if remaining <= 0:
                break
            user_payload = {
                "question": question,
                "attempt": attempt + 1,
                "repair": attempt > 0,
            }
            try:
                raw = self.model.complete(
                    system_prompt=self.system_prompt,
                    user_prompt=json.dumps(user_payload, ensure_ascii=False),
                    timeout_seconds=remaining,
                )
                calls += 1
            except ModelDependencyError:
                raise

            if time.monotonic() - started > self.deadline_seconds:
                last_error = "planning deadline exceeded"
                break
            try:
                data = load_json_output(raw)
                decision = PlannerDecision.model_validate(data)
                return PlanningResult(
                    query_type=decision.query_type,
                    plan=decision.plan,
                    calls=calls,
                    valid=True,
                )
            except (json.JSONDecodeError, ValueError):
                last_error = "invalid planner output"

        return PlanningResult(
            query_type=QueryType.ASSET_QUERY,
            calls=calls,
            valid=False,
            warning=last_error,
        )
