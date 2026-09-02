'''
此處將filter變成陣列處理
'''
from typing import Any, Literal

from pydantic import BaseModel, Field


class QueryFilter(BaseModel):
    field: str
    operator: Literal[
        "=",
        "!=",
        ">",
        ">=",
        "<",
        "<=",
        "LIKE",
        "IN",
    ] = "="
    value: Any


class OrderBy(BaseModel):
    field: str
    direction: Literal["ASC", "DESC"] = "ASC"


class SemanticQuery(BaseModel):
    entity: str

    fields: list[str] = Field(
        default_factory=list
    )

    filters: list[QueryFilter] = Field(
        default_factory=list
    )

    order_by: OrderBy | None = None

    limit: int = Field(
        default=20,
        gt=0,
        le=500,
    )