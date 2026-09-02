from fastapi import APIRouter

from app.adapters.sqlite_adapter import SQLiteAdapter
from app.core.config import (
    SQLITE_DB_PATH,
    MAPPING_DIR,
)
from app.schemas.semantic_query import SemanticQuery
from app.semantic.mapper import SemanticMapper
from app.services.query_service import QueryService

from pydantic import BaseModel
from app.services.nl_query_graph import NLQueryGraph

router = APIRouter(
    prefix="/query",
    tags=["Semantic Query"],
)


print(
    f"[API] SQLite DB = {SQLITE_DB_PATH}"
)

print(
    f"[API] Mapping Dir = {MAPPING_DIR}"
)


db = SQLiteAdapter(
    str(SQLITE_DB_PATH)
)

mapper = SemanticMapper(
    MAPPING_DIR
)

service = QueryService(
    db=db,
    mapper=mapper,
)

nl_graph = NLQueryGraph(
    mapper=mapper,
    query_service=service,
)

@router.post("/")
def query(
    request: SemanticQuery,
):
    return service.execute(request)

class NLQueryRequest(BaseModel):
    question: str


@router.post("/ask")
def ask(request: NLQueryRequest):
    return nl_graph.run(request.question)

@router.get("/graph")
def get_graph():
    nodes = []
    edges = []

    for entity, mapping in mapper.mappings.items():
        nodes.append({
            "id": entity,
            "label": mapping.get("label", entity),
            "properties": list(mapping.get("properties", {}).keys()),
        })

        for rel_name, rel in mapping.get("relations", {}).items():
            edges.append({
                "source": entity,
                "target": rel["target"]["entity"],
                "label": rel.get("label", rel_name),
            })

    return {"nodes": nodes, "edges": edges}

# from fastapi import APIRouter

# from app.adapters.sqlite_adapter import (
#     SQLiteAdapter,
# )

# from app.schemas.semantic_query import (
#     SemanticQuery,
# )

# from app.semantic.mapper import (
#     SemanticMapper,
# )

# from app.services.query_service import (
#     QueryService,
# )

# from pathlib import Path


# router = APIRouter(
#     prefix="/query",
#     tags=["Semantic Query"],
# )


# BASE_DIR = Path(__file__).resolve().parents[3]

# DB_PATH = (
#     BASE_DIR
#     / "data"
#     / "lab.db"
# )

# MAPPING_DIR = (
#     BASE_DIR
#     / "semantic"
#     / "mappings"
# )


# db = SQLiteAdapter(
#     str(DB_PATH)
# )

# mapper = SemanticMapper(
#     MAPPING_DIR
# )

# service = QueryService(
#     db=db,
#     mapper=mapper,
# )


# @router.post("/")
# def query(
#     request: SemanticQuery,
# ):

#     result = service.execute(
#         request
#     )

#     return result