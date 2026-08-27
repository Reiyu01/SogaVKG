from fastapi import Request

from app.core.runtime import QueryRuntime


def get_runtime(request: Request) -> QueryRuntime:
    return request.app.state.runtime
