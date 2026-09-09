from dotenv import load_dotenv
load_dotenv()

from fastapi import FastAPI
from app.api.builder import router as builder_router
from app.api.query import router as query_router
app = FastAPI(
    title="Laboratory Data Platform",
    version="0.1.0",
)
from fastapi.middleware.cors import CORSMiddleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(query_router)
app.include_router(builder_router)


@app.get("/health")
def health():

    return {
        "status": "ok"
    }