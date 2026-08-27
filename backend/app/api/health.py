from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status

from app.api.dependencies import get_runtime
from app.api.models import HealthResponse
from app.core.readiness import ReadinessError, check_query_readiness
from app.core.runtime import QueryRuntime


router = APIRouter(prefix="/api/v1/health", tags=["health"])


@router.get("/live", response_model=HealthResponse)
def liveness() -> HealthResponse:
    return HealthResponse(status="ok")


@router.get(
    "/ready",
    response_model=HealthResponse,
    responses={503: {"description": "Required query dependency unavailable"}},
)
def readiness(
    runtime: Annotated[QueryRuntime, Depends(get_runtime)],
) -> HealthResponse:
    try:
        check_query_readiness(runtime.database, runtime.mapper, runtime.policy)
    except ReadinessError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="query dependency unavailable",
        ) from exc
    return HealthResponse(status="ready")
