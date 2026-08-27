from enum import StrEnum
from typing import Annotated, Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StrictBool,
    StrictFloat,
    StrictInt,
    StrictStr,
    StringConstraints,
    field_validator,
)


NonEmptyStr = Annotated[StrictStr, StringConstraints(strip_whitespace=True, min_length=1)]
Scalar = StrictStr | StrictInt | StrictFloat | StrictBool | None
FilterScalar = StrictStr | StrictInt | StrictFloat | StrictBool


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class QueryType(StrEnum):
    ASSET_QUERY = "asset_query"
    CONVERSATION = "conversation"
    UNSUPPORTED = "unsupported"
    WRITE = "write"


class QueryStatus(StrEnum):
    ANSWERED = "answered"
    CONVERSATION = "conversation"
    UNSUPPORTED = "unsupported"
    INVALID_PLAN = "invalid_plan"
    NO_RESULTS = "no_results"
    REFUSED = "refused"
    DEPENDENCY_ERROR = "dependency_error"


class OrderBy(StrictModel):
    field: NonEmptyStr
    direction: Literal["ASC", "DESC"] = "ASC"


class SemanticQueryPlan(StrictModel):
    entity: NonEmptyStr
    fields: list[NonEmptyStr] = Field(default_factory=list)
    filters: dict[NonEmptyStr, FilterScalar] = Field(default_factory=dict)
    order_by: OrderBy | None = None
    limit: StrictInt | None = Field(default=None, gt=0)

    @field_validator("fields")
    @classmethod
    def fields_must_be_unique(cls, fields: list[str]) -> list[str]:
        if len(fields) != len(set(fields)):
            raise ValueError("fields must be unique")
        return fields


class QueryTraceEvent(StrictModel):
    stage: NonEmptyStr
    status: NonEmptyStr
    elapsed_ms: StrictFloat = Field(ge=0)
    detail: NonEmptyStr | None = None


class RowSource(StrictModel):
    number: StrictInt = Field(ge=1)
    entity: Literal["Asset"] = "Asset"
    record_key: NonEmptyStr
    fields: dict[NonEmptyStr, Scalar]


class QueryExecution(StrictModel):
    answer: StrictStr
    query_type: QueryType = Field(strict=False)
    status: QueryStatus = Field(strict=False)
    executed: StrictBool
    insufficient: StrictBool
    plan: SemanticQueryPlan | None = None
    row_count: StrictInt = Field(ge=0)
    truncated: StrictBool = False
    warnings: list[NonEmptyStr] = Field(default_factory=list)
    elapsed_ms: StrictFloat = Field(ge=0)
    planning_calls: StrictInt = Field(default=0, ge=0)
    trace: list[QueryTraceEvent] = Field(default_factory=list)
    sources: list[RowSource] = Field(default_factory=list)
