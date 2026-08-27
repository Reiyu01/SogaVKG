from typing import Annotated, Literal

from pydantic import Field, StrictStr, StringConstraints

from app.models.query import QueryExecution, StrictModel


Question = Annotated[
    StrictStr,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=8000),
]


class QueryRequest(StrictModel):
    question: Question


class QueryResponse(QueryExecution):
    pass


class HealthResponse(StrictModel):
    status: Literal["ok", "ready"]


class DependencyErrorResponse(StrictModel):
    detail: str = Field(min_length=1)
