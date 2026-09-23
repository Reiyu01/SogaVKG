from fastapi import APIRouter, BackgroundTasks, HTTPException
from pydantic import BaseModel
import os
import sqlite3
from functools import lru_cache
from pathlib import Path

from app.core.config import (
    SQLITE_DB_PATH,
    MAPPING_DIR,
    PROJECT_MAPPING_ROOT,
    PLATFORM_STATE_DB_PATH,
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
from app.services.graph_projection import GraphProjectionService
from app.services.sqlite_semantic_query import SQLiteSemanticQueryService
from app.repositories.platform_state import PlatformStateRepository


router = APIRouter(
    prefix="/query",
    tags=["Semantic Query"],
)


print(f"[API] SQLite DB = {SQLITE_DB_PATH}")
print(f"[API] Mapping Dir = {MAPPING_DIR}")

state_repository = PlatformStateRepository(PLATFORM_STATE_DB_PATH)


# ======================================================
# Semantic Mapping
# ======================================================

def get_mapper(project_id: str | None = None) -> SemanticMapper:
    """Load mappings at request time so saved Builder changes take effect."""
    return SemanticMapper(PROJECT_MAPPING_ROOT / project_id / "mappings" if project_id else MAPPING_DIR)


def get_projection_service(project_id: str) -> GraphProjectionService:
    """Resolve the project's active SQLite source for read-only graph projection."""
    if state_repository.get_project(project_id) is None:
        raise HTTPException(status_code=404, detail="Project not found")
    sources = [source for source in state_repository.list_sources(project_id)
               if source["active"] and source["source_type"] == "sqlite"]
    if not sources:
        raise HTTPException(
            status_code=400,
            detail="Add and enable a SQLite source before exploring this project's graph.",
        )
    mapper = get_mapper(project_id)
    database_path = next((
        source["config"].get("path") for source in sources
        if source["config"].get("path") and os.path.exists(source["config"]["path"])
        and _source_matches_mapping(Path(source["config"]["path"]), mapper)
    ), None)
    if not database_path:
        raise HTTPException(
            status_code=400,
            detail="No enabled SQLite source contains every table required by this project's Mapping.",
        )
    try:
        return GraphProjectionService(mapper, Path(database_path))
    except (FileNotFoundError, ValueError) as error:
        raise HTTPException(status_code=400, detail=str(error)) from error


def _source_matches_mapping(database_path: Path, mapper: SemanticMapper) -> bool:
    """Avoid projecting a project's Mapping from an unrelated saved source."""
    required_tables = {
        mapping.get("ingestion", {}).get("source_table") or mapping.get("source", {}).get("table")
        for mapping in mapper.mappings.values()
    }
    if not required_tables or None in required_tables:
        return False
    try:
        with sqlite3.connect(database_path) as connection:
            available = {row[0] for row in connection.execute("SELECT name FROM sqlite_master WHERE type = 'table'")}
        return required_tables <= available
    except sqlite3.Error:
        return False


# ======================================================
# Query Service
# ======================================================

def required_environment(*names: str) -> dict[str, str]:
    values = {name: os.getenv(name) for name in names}
    missing = [name for name, value in values.items() if not value]
    if missing:
        raise HTTPException(
            status_code=503,
            detail=f"Service is not configured; missing: {', '.join(missing)}",
        )
    return values  # type: ignore[return-value]


@lru_cache
def get_db() -> Neo4jAdapter:
    config = required_environment("NEO4J_URI", "NEO4J_USER", "NEO4J_PASSWORD")
    return Neo4jAdapter(
        uri=config["NEO4J_URI"],
        user=config["NEO4J_USER"],
        password=config["NEO4J_PASSWORD"],
    )


def get_service(project_id: str) -> SQLiteSemanticQueryService:
    projection = get_projection_service(project_id)
    return SQLiteSemanticQueryService(get_mapper(project_id), projection.database_path)


def get_nl_graph(project_id: str) -> NLQueryGraph:
    required_environment("MY_MODEL_BASE_URL", "MY_MODEL_NAME")
    mapper = get_mapper(project_id)
    return NLQueryGraph(
        mapper=mapper, query_service=get_service(project_id), project_id=project_id,
    )


# ======================================================
# Structured Semantic Query
# ======================================================

@router.post("/")
def query(
    request: SemanticQuery,
    project_id: str,
):
    return get_service(project_id).execute(request, project_id=project_id)


# ======================================================
# Natural Language Query
# ======================================================

class NLQueryRequest(BaseModel):
    question: str
    project_id: str

class DeactivateNodesRequest(BaseModel):
    project_id: str
    entity: str
    source_ids: list[str | int]


@router.post("/ask")
def ask(
    request: NLQueryRequest,
):
    return get_nl_graph(request.project_id).run(
        request.question
    )

@router.post("/graph/deactivate")
def deactivate_nodes(request: DeactivateNodesRequest):
    mapper = get_mapper(request.project_id)
    label = mapper.get_source(request.entity)["node_label"]
    get_db().execute_write(
        f"""MATCH (n:{label} {{ _project_id: $project_id }})
        WHERE n._source_id IN $source_ids
        SET n._inactive = true, n._inactive_at = datetime()""",
        {"project_id": request.project_id, "source_ids": request.source_ids},
    )
    return {"status": "deactivated", "count": len(request.source_ids)}


# ======================================================
# Semantic Graph Schema
# ======================================================

@router.get("/graph")
def get_graph(project_id: str):

    mapper = get_mapper(project_id)

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
                "searchable_properties": [
                    name
                    for name, definition in mapping.get("properties", {}).items()
                    if definition.get("searchable") or definition.get("fulltext")
                ],
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


@router.get("/graph/projection")
def get_graph_projection(project_id: str, limit: int = 120):
    """Return a bounded data graph projected from the source using its Mapping."""
    try:
        return get_projection_service(project_id).project(limit)
    except (sqlite3.Error, ValueError) as error:
        raise HTTPException(status_code=400, detail=f"Could not project graph: {error}") from error


@router.get("/graph/projection/records")
def get_projection_records(project_id: str, entity: str, limit: int = 50, keyword: str | None = None):
    try:
        return get_projection_service(project_id).records(entity, limit, keyword)
    except (sqlite3.Error, ValueError) as error:
        raise HTTPException(status_code=400, detail=f"Could not read mapped records: {error}") from error


@router.get("/graph/projection/entity")
def get_projection_entity(project_id: str, entity: str, limit: int = 12):
    try:
        return get_projection_service(project_id).entity_nodes(entity, limit)
    except (sqlite3.Error, ValueError) as error:
        raise HTTPException(status_code=400, detail=f"Could not expand entity: {error}") from error


@router.get("/graph/projection/neighbors")
def get_projection_neighbors(project_id: str, entity: str, source_id: str, limit: int = 20):
    try:
        return get_projection_service(project_id).neighbors(entity, source_id, limit)
    except (sqlite3.Error, ValueError) as error:
        raise HTTPException(status_code=400, detail=f"Could not expand node: {error}") from error

@router.get("/graph/stats")
def get_graph_stats(project_id: str):
    rows = get_db().execute("""
        MATCH (n { _project_id: $project_id })
        OPTIONAL MATCH (n)-[r]->()
        RETURN count(DISTINCT n) AS nodes, count(DISTINCT r) AS edges
    """, {"project_id": project_id})
    return rows[0] if rows else {"nodes": 0, "edges": 0}

@router.get("/graph/data")
def get_graph_data(
    project_id: str,
    entity: str | None = None,
    limit: int = 100,
):
    if limit < 1:
        limit = 1

    if limit > 500:
        limit = 500

    params = {
        "limit": limit,
        "project_id": project_id,
    }

    if entity:
        query = """
        MATCH (n)
        WHERE $entity IN labels(n) AND n._project_id = $project_id

        WITH n
        LIMIT $limit

        OPTIONAL MATCH (n)-[r]->(m)

        RETURN
            elementId(n) AS node_id,
            labels(n) AS node_labels,
            properties(n) AS node_properties,

            CASE
                WHEN r IS NULL
                THEN NULL
                ELSE elementId(r)
            END AS relationship_id,

            CASE
                WHEN r IS NULL
                THEN NULL
                ELSE type(r)
            END AS relationship_type,

            CASE
                WHEN m IS NULL
                THEN NULL
                ELSE elementId(m)
            END AS target_id,

            CASE
                WHEN m IS NULL
                THEN NULL
                ELSE labels(m)
            END AS target_labels,

            CASE
                WHEN m IS NULL
                THEN NULL
                ELSE properties(m)
            END AS target_properties
        """

        params["entity"] = entity

    else:
        query = """
        MATCH (n { _project_id: $project_id })

        WITH n
        LIMIT $limit

        OPTIONAL MATCH (n)-[r]->(m)

        RETURN
            elementId(n) AS node_id,
            labels(n) AS node_labels,
            properties(n) AS node_properties,

            CASE
                WHEN r IS NULL
                THEN NULL
                ELSE elementId(r)
            END AS relationship_id,

            CASE
                WHEN r IS NULL
                THEN NULL
                ELSE type(r)
            END AS relationship_type,

            CASE
                WHEN m IS NULL
                THEN NULL
                ELSE elementId(m)
            END AS target_id,

            CASE
                WHEN m IS NULL
                THEN NULL
                ELSE labels(m)
            END AS target_labels,

            CASE
                WHEN m IS NULL
                THEN NULL
                ELSE properties(m)
            END AS target_properties
        """

    rows = get_db().execute(
        query,
        params,
    )

    nodes = {}
    edges = {}

    for row in rows:
        node_id = row["node_id"]

        if node_id not in nodes:
            labels = row.get("node_labels") or []
            props = row.get("node_properties") or {}

            nodes[node_id] = {
                "id": node_id,
                "labels": labels,
                "label": (
                    props.get("name")
                    or props.get("asset_code")
                    or props.get("_source_id")
                    or labels[0]
                    if labels
                    else node_id
                ),
                "properties": props,
            }

        target_id = row.get("target_id")

        if target_id:
            if target_id not in nodes:
                target_labels = (
                    row.get("target_labels")
                    or []
                )

                target_props = (
                    row.get("target_properties")
                    or {}
                )

                nodes[target_id] = {
                    "id": target_id,
                    "labels": target_labels,
                    "label": (
                        target_props.get("name")
                        or target_props.get("asset_code")
                        or target_props.get("_source_id")
                        or target_labels[0]
                        if target_labels
                        else target_id
                    ),
                    "properties": target_props,
                }

        relationship_id = row.get(
            "relationship_id"
        )

        if (
            relationship_id
            and target_id
        ):
            edges[relationship_id] = {
                "id": relationship_id,
                "source": node_id,
                "target": target_id,
                "type": row.get(
                    "relationship_type"
                ),
            }

    return {
        "nodes": list(nodes.values()),
        "edges": list(edges.values()),
        "count": {
            "nodes": len(nodes),
            "edges": len(edges),
        },
    }


# ======================================================
# Ingestion
# ======================================================

@router.post("/ingest")
def start_ingestion(
    background_tasks: BackgroundTasks,
):

    if SQLITE_DB_PATH is None:
        raise HTTPException(
            status_code=400,
            detail="SQLITE_DB_PATH must be configured before starting ingestion.",
        )

    job = create_job()

    def pipeline_factory(
        on_progress,
    ):

        pipeline = IngestionPipeline(
            mapper=get_mapper(),
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
