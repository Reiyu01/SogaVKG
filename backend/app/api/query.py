from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status

from app.api.dependencies import get_runtime
from app.api.models import QueryRequest, QueryResponse
from app.core.runtime import QueryRuntime
from app.services.query_service import QueryDependencyError


router = APIRouter(prefix="/api/v1", tags=["query"])


@router.post(
    "/query",
    response_model=QueryResponse,
    responses={503: {"description": "Required query dependency unavailable"}},
)
def query_assets(
    request: QueryRequest,
    runtime: Annotated[QueryRuntime, Depends(get_runtime)],
) -> QueryResponse:
    try:
        execution = runtime.service.query(request.question)
    except QueryDependencyError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="query dependency unavailable",
        ) from exc
    return QueryResponse.model_validate(execution.model_dump())
