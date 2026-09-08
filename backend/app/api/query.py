from fastapi import APIRouter

# from app.adapters.sqlite_adapter import SQLiteAdapter
from app.core.config import (
    SQLITE_DB_PATH,
    MAPPING_DIR,
)
from app.schemas.semantic_query import SemanticQuery
from app.semantic.mapper import SemanticMapper
from app.services.query_service import QueryService

from pydantic import BaseModel
from app.services.nl_query_graph import NLQueryGraph

#0907
from app.adapters.neo4j_adapter import Neo4jAdapter
from app.semantic.cypher_query_builder import CypherQueryBuilder
import os
from fastapi import BackgroundTasks
from app.semantic.ingestion_pipeline import IngestionPipeline, SQLiteSourceReader
from app.services.ingestion_job import create_job, get_job, run_ingestion_job


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


# db = SQLiteAdapter(
#     str(SQLITE_DB_PATH)
# )

#0907
db = Neo4jAdapter(
    uri=os.environ["NEO4J_URI"],
    user=os.environ["NEO4J_USER"],
    password=os.environ["NEO4J_PASSWORD"],
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



@router.post("/ingest")
def start_ingestion(background_tasks: BackgroundTasks):
    job = create_job()

    def pipeline_factory(on_progress):
        pipeline = IngestionPipeline(
            mapper=mapper,
            neo4j_uri=os.environ["NEO4J_URI"],
            neo4j_user=os.environ["NEO4J_USER"],
            neo4j_password=os.environ["NEO4J_PASSWORD"],
            on_progress=on_progress,
        )
        pipeline.register_reader("sqlite", SQLiteSourceReader(str(DB_PATH)))
        return pipeline

    background_tasks.add_task(run_ingestion_job, job, pipeline_factory)

    return {"job_id": job.id}


@router.get("/ingest/{job_id}")
def get_ingestion_status(job_id: str):
    job = get_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    return job.to_dict()

    
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