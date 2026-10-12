from dotenv import load_dotenv
from pathlib import Path

# Resolve credentials relative to the backend itself, rather than the shell's
# current directory.  This keeps source credential references working whether
# uvicorn is launched from `backend/` or from the repository root.
load_dotenv(Path(__file__).resolve().parents[1] / ".env")

from fastapi import FastAPI
from app.api.builder import router as builder_router
from app.api.query import router as query_router
app = FastAPI(
    title="Laboratory Data Platform",
    version="0.1.0",
)
import os

from fastapi.middleware.cors import CORSMiddleware


def configured_origins() -> list[str]:
    """Read allowed browser origins from environment instead of source code."""
    value = os.getenv("CORS_ALLOW_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173")
    return [origin.strip() for origin in value.split(",") if origin.strip()]


app.add_middleware(
    CORSMiddleware,
    allow_origins=configured_origins(),
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(query_router)
app.include_router(builder_router)


@app.get("/health")
def health():
    return {
        "status": "ok",
        "service": "knowledge-graph-platform",
    }
