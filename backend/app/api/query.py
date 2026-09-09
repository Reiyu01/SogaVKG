from fastapi import APIRouter, BackgroundTasks, HTTPException
from pydantic import BaseModel
import os

from app.core.config import (
    SQLITE_DB_PATH,
    MAPPING_DIR,
)

from app.schemas.semantic_query import SemanticQuery

from app.adapters.neo4j_adapter import Neo4jAdapter

from app.semantic.mapper import SemanticMapper
from app.semantic.ingestion_pipeline import (
    IngestionPipeline,
    SQLiteSourceReader,
)

from app.services.query_service import QueryService
from app.services.nl_query_graph import NLQueryGraph
from app.services.ingestion_job import (
    create_job,
    get_job,
    run_ingestion_job,
)


router = APIRouter(
    prefix="/query",
    tags=["Semantic Query"],
)


print(f"[API] SQLite DB = {SQLITE_DB_PATH}")
print(f"[API] Mapping Dir = {MAPPING_DIR}")


# ======================================================
# Runtime Query DB
# ======================================================

db = Neo4jAdapter(
    uri=os.environ["NEO4J_URI"],
    user=os.environ["NEO4J_USER"],
    password=os.environ["NEO4J_PASSWORD"],
)


# ======================================================
# Semantic Mapping
# ======================================================

mapper = SemanticMapper(
    MAPPING_DIR
)


# ======================================================
# Query Service
# ======================================================

service = QueryService(
    db=db,
    mapper=mapper,
)


nl_graph = NLQueryGraph(
    mapper=mapper,
    query_service=service,
)


# ======================================================
# Structured Semantic Query
# ======================================================

@router.post("/")
def query(
    request: SemanticQuery,
):
    return service.execute(request)


# ======================================================
# Natural Language Query
# ======================================================

class NLQueryRequest(BaseModel):
    question: str


@router.post("/ask")
def ask(
    request: NLQueryRequest,
):
    return nl_graph.run(
        request.question
    )


# ======================================================
# Semantic Graph Schema
# ======================================================

@router.get("/graph")
def get_graph():

    nodes = []
    edges = []

    for entity, mapping in mapper.mappings.items():

        nodes.append(
            {
                "id": entity,
                "label": mapping.get(
                    "label",
                    entity,
                ),
                "properties": list(
                    mapping.get(
                        "properties",
                        {},
                    ).keys()
                ),
            }
        )

        for rel_name, rel in mapping.get(
            "relations",
            {},
        ).items():

            edges.append(
                {
                    "source": entity,
                    "target": rel["target"]["entity"],
                    "label": rel.get(
                        "label",
                        rel_name,
                    ),
                }
            )

    return {
        "nodes": nodes,
        "edges": edges,
    }


# ======================================================
# Ingestion
# ======================================================

@router.post("/ingest")
def start_ingestion(
    background_tasks: BackgroundTasks,
):

    job = create_job()

    def pipeline_factory(
        on_progress,
    ):

        pipeline = IngestionPipeline(
            mapper=mapper,
            neo4j_uri=os.environ["NEO4J_URI"],
            neo4j_user=os.environ["NEO4J_USER"],
            neo4j_password=os.environ["NEO4J_PASSWORD"],
            on_progress=on_progress,
        )

        # 修正：
        # 原本使用不存在的 DB_PATH
        pipeline.register_reader(
            "sqlite",
            SQLiteSourceReader(
                str(SQLITE_DB_PATH)
            ),
        )

        return pipeline

    background_tasks.add_task(
        run_ingestion_job,
        job,
        pipeline_factory,
    )

    return {
        "job_id": job.id
    }


# ======================================================
# Ingestion Status
# ======================================================

@router.get("/ingest/{job_id}")
def get_ingestion_status(
    job_id: str,
):

    job = get_job(job_id)

    if job is None:
        raise HTTPException(
            status_code=404,
            detail="Job not found",
        )

    return job.to_dict()