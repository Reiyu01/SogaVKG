from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.health import router as health_router
from app.api.query import router as query_router
from app.core.runtime import QueryRuntime, build_runtime


RuntimeFactory = Callable[[], QueryRuntime]


def create_app(
    *,
    runtime: QueryRuntime | None = None,
    runtime_factory: RuntimeFactory = build_runtime,
) -> FastAPI:
    @asynccontextmanager
    async def lifespan(application: FastAPI) -> AsyncIterator[None]:
        if runtime is not None:
            application.state.runtime = runtime
        else:
            application.state.runtime = runtime_factory()
        yield

    application = FastAPI(
        title="SogaVKG Lab Query MVP",
        version="1.0.0",
        lifespan=lifespan,
    )
    application.include_router(query_router)
    application.include_router(health_router)
    return application


app = create_app()
