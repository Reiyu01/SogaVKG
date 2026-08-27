from typing import Annotated

from pydantic import Field, StrictStr, StringConstraints, model_validator

from app.models.query import NonEmptyStr, QueryStatus, QueryType, StrictModel


Question = Annotated[
    StrictStr,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=8000),
]
CheckValue = str | bool | int | float | list[str] | None


class EvaluationCase(StrictModel):
    id: NonEmptyStr
    question: Question
    expected_query_type: QueryType | None = Field(default=None, strict=False)
    expected_status: QueryStatus | None = Field(default=None, strict=False)
    required_record_keys: list[NonEmptyStr] = Field(default_factory=list)
    expected_fields: list[NonEmptyStr] = Field(default_factory=list)
    expect_plan_valid: bool | None = None
    expect_refusal: bool | None = None
    expect_warning: bool | None = None

    @model_validator(mode="after")
    def validate_expectations(self) -> "EvaluationCase":
        expectations = (
            self.expected_query_type,
            self.expected_status,
            self.required_record_keys,
            self.expected_fields,
            self.expect_plan_valid,
            self.expect_refusal,
            self.expect_warning,
        )
        if not any(value is not None and value != [] for value in expectations):
            raise ValueError("evaluation case requires at least one expectation")
        if len(self.required_record_keys) != len(set(self.required_record_keys)):
            raise ValueError("required_record_keys must be unique")
        if len(self.expected_fields) != len(set(self.expected_fields)):
            raise ValueError("expected_fields must be unique")
        return self


class EvaluationDataset(StrictModel):
    name: NonEmptyStr
    version: NonEmptyStr
    cases: list[EvaluationCase] = Field(min_length=1)

    @model_validator(mode="after")
    def case_ids_must_be_unique(self) -> "EvaluationDataset":
        case_ids = [case.id for case in self.cases]
        if len(case_ids) != len(set(case_ids)):
            raise ValueError("evaluation case ids must be unique")
        return self


class EvaluationCheck(StrictModel):
    name: NonEmptyStr
    passed: bool
    expected: CheckValue = None
    actual: CheckValue = None


class EvaluationCaseResult(StrictModel):
    case_id: NonEmptyStr
    expected_query_type: QueryType | None = Field(default=None, strict=False)
    actual_query_type: QueryType | None = Field(default=None, strict=False)
    expected_status: QueryStatus | None = Field(default=None, strict=False)
    actual_status: QueryStatus = Field(strict=False)
    executed: bool
    dependency_failure: bool
    record_keys: list[str]
    fields: list[str]
    warnings: list[str]
    elapsed_ms: float = Field(ge=0)
    planning_calls: int = Field(ge=0)
    checks: list[EvaluationCheck]
    passed: bool


class EvaluationMetrics(StrictModel):
    case_count: int = Field(ge=1)
    query_type_accuracy: float = Field(ge=0, le=1)
    plan_validity: float = Field(ge=0, le=1)
    required_record_recall: float = Field(ge=0, le=1)
    expected_field_coverage: float = Field(ge=0, le=1)
    status_accuracy: float = Field(ge=0, le=1)
    citation_validity: float = Field(ge=0, le=1)
    average_planning_calls: float = Field(ge=0)
    average_elapsed_ms: float = Field(ge=0)


class EvaluationReport(StrictModel):
    dataset_name: NonEmptyStr
    dataset_version: NonEmptyStr
    metrics: EvaluationMetrics
    results: list[EvaluationCaseResult]
