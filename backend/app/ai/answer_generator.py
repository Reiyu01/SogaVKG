import json
import re
import time
from pathlib import Path

from app.ai.ports import ChatModelPort, ModelDependencyError
from app.ai.structured_output import load_json_output
from app.models.query import RowSource, StrictModel


PROMPT_PATH = Path(__file__).resolve().parent / "prompts" / "answer_v1.md"
CITATION_PATTERN = re.compile(r"\[(\d+)\]")


class AnswerDraft(StrictModel):
    answer: str


class AnswerResult(StrictModel):
    answer: str | None = None
    calls: int
    valid: bool
    warning: str | None = None


def citations_are_valid(answer: str, sources: list[RowSource]) -> bool:
    citations = [int(value) for value in CITATION_PATTERN.findall(answer)]
    source_numbers = {source.number for source in sources}
    return bool(citations) and set(citations) <= source_numbers


class GroundedAnswerGenerator:
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

    def generate(
        self,
        *,
        question: str,
        sources: list[RowSource],
        warnings: list[str],
        truncated: bool,
    ) -> AnswerResult:
        if not sources:
            raise ValueError("grounded answer requires sources")
        started = time.monotonic()
        calls = 0
        for attempt in range(self.max_calls):
            remaining = self.deadline_seconds - (time.monotonic() - started)
            if remaining <= 0:
                break
            payload = {
                "question": question,
                "warnings": warnings,
                "truncated": truncated,
                "sources": [source.model_dump(mode="json") for source in sources],
                "attempt": attempt + 1,
                "repair": attempt > 0,
            }
            try:
                raw = self.model.complete(
                    system_prompt=self.system_prompt,
                    user_prompt=json.dumps(payload, ensure_ascii=False),
                    timeout_seconds=remaining,
                )
                calls += 1
            except ModelDependencyError:
                raise
            if time.monotonic() - started > self.deadline_seconds:
                break
            try:
                draft = AnswerDraft.model_validate(load_json_output(raw))
                answer = draft.answer.strip()
                if citations_are_valid(answer, sources):
                    if truncated:
                        answer = f"結果已截斷，目前只顯示部分資料。{answer}"
                    return AnswerResult(answer=answer, calls=calls, valid=True)
            except (json.JSONDecodeError, ValueError):
                pass
        return AnswerResult(
            calls=calls,
            valid=False,
            warning="回答來源驗證失敗，已停止交付未驗證答案",
        )
