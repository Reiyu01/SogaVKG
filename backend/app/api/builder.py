from fastapi import APIRouter, BackgroundTasks, HTTPException
from pydantic import BaseModel, Field
from pathlib import Path
import os
import sqlite3
import uuid
import json

from app.core.config import (
    SQLITE_DB_PATH,
    MAPPING_DIR,
    PROJECT_MAPPING_ROOT,
    PLATFORM_STATE_DB_PATH,
)

from app.semantic.mapper import SemanticMapper
from app.semantic.ingestion_pipeline import (
    IngestionPipeline,
    SQLiteSourceReader,
)

from app.services.ingestion_job import (
    create_job,
    get_job,
    run_ingestion_job,
)
from typing import Any
from app.services.mapping_service import MappingService
from app.repositories.platform_state import PlatformStateRepository

router = APIRouter(
    prefix="/builder",
    tags=["Knowledge Builder"],
)

mapping_service = MappingService(
    MAPPING_DIR
)
state_repository = PlatformStateRepository(PLATFORM_STATE_DB_PATH)
# ======================================================
# Request Models
# ======================================================

class SourceSchemaRequest(BaseModel):
    source_type: str = "sqlite"
    path: str | None = None

class BuildRequest(BaseModel):
    reset: bool = True
    mode: str = "full"
    source_path: str | None = None
    source_id: str | None = None
    project_id: str | None = None

class SourceProfileRequest(BaseModel):
    project_id: str | None = None
    name: str = Field(min_length=1, max_length=120)
    source_type: str = "sqlite"
    config: dict[str, Any]

class ProjectRequest(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    description: str | None = Field(default=None, max_length=500)

class MappingRequest(BaseModel):
    project_id: str
    entity: str
    label: str | None = None
    source: dict[str, Any]
    ingestion: dict[str, Any]
    properties: dict[str, Any]
    relations: dict[str, Any] = Field(default_factory=dict)

class MappingReplaceRequest(BaseModel):
    project_id: str
    mappings: list[MappingRequest] = Field(min_length=1)

# ======================================================
# Helpers
# ======================================================

def project_mapping_dir(project_id: str) -> Path:
    if state_repository.get_project(project_id) is None:
        raise HTTPException(status_code=404, detail="Project not found")
    return PROJECT_MAPPING_ROOT / project_id / "mappings"


def get_mapper(project_id: str | None = None) -> SemanticMapper:
    """
    每次重新建立 mapper。

    原因：
    SemanticMapper 只會在 __init__ 時讀取 YAML。
    未來 Builder 修改 YAML 後，
    如果繼續使用舊 mapper，
    就不會看到新的 mapping。
    """
    return SemanticMapper(project_mapping_dir(project_id) if project_id else MAPPING_DIR)


def get_mapping_service(project_id: str) -> MappingService:
    return MappingService(project_mapping_dir(project_id))


def resolve_sqlite_path(
    requested_path: str | None,
) -> Path:

    if requested_path:
        db_path = Path(requested_path)

        if not db_path.is_absolute():
            db_path = Path.cwd() / db_path
    else:
        if SQLITE_DB_PATH is None:
            raise HTTPException(
                status_code=400,
                detail="SQLite path is required. Provide it in the request or SQLITE_DB_PATH.",
            )
        db_path = SQLITE_DB_PATH

    db_path = db_path.resolve()

    if not db_path.exists():
        raise HTTPException(
            status_code=404,
            detail=f"SQLite database not found: {db_path}",
        )

    return db_path


def resolve_source_path(request: BuildRequest) -> Path:
    if request.source_id:
        source = state_repository.get_source(request.source_id)
        if source is None:
            raise HTTPException(status_code=404, detail="Source profile not found")
        if not source["active"]:
            raise HTTPException(status_code=400, detail="Source profile is disabled")
        if source["source_type"] != "sqlite":
            raise HTTPException(status_code=400, detail="Only sqlite sources are supported for builds")
        return resolve_sqlite_path(source["config"].get("path"))
    return resolve_sqlite_path(request.source_path)


# ======================================================
# Health
# ======================================================

@router.get("/health")
def builder_health():

    return {
        "status": "ok",
        "mapping_dir": str(MAPPING_DIR),
        "sqlite_db": str(SQLITE_DB_PATH) if SQLITE_DB_PATH else None,
    }


# ======================================================
# Source Schema Discovery
# ======================================================

@router.post("/source/schema")
def get_source_schema(
    request: SourceSchemaRequest,
):

    if request.source_type != "sqlite":
        raise HTTPException(
            status_code=400,
            detail=(
                f"Unsupported source type: "
                f"{request.source_type}"
            ),
        )

    db_path = resolve_sqlite_path(
        request.path
    )

    conn = sqlite3.connect(
        str(db_path)
    )

    conn.row_factory = sqlite3.Row

    try:

        table_rows = conn.execute(
            """
            SELECT name
            FROM sqlite_master
            WHERE type = 'table'
              AND name NOT LIKE 'sqlite_%'
            ORDER BY name
            """
        ).fetchall()

        tables = []

        for table_row in table_rows:

            table_name = table_row["name"]

            columns_raw = conn.execute(
                f'PRAGMA table_info("{table_name}")'
            ).fetchall()

            foreign_keys_raw = conn.execute(
                f'PRAGMA foreign_key_list("{table_name}")'
            ).fetchall()

            columns = []

            for column in columns_raw:

                columns.append(
                    {
                        "name": column["name"],
                        "type": column["type"],
                        "nullable": (
                            column["notnull"] == 0
                        ),
                        "default": column["dflt_value"],
                        "primary_key": (
                            column["pk"] > 0
                        ),
                    }
                )

            foreign_keys = []

            for fk in foreign_keys_raw:

                foreign_keys.append(
                    {
                        "column": fk["from"],
                        "target_table": fk["table"],
                        "target_column": fk["to"],
                    }
                )

            sample_rows_raw = conn.execute(
                f'''
                SELECT *
                FROM "{table_name}"
                LIMIT 5
                '''
            ).fetchall()

            sample_rows = [
                dict(row)
                for row in sample_rows_raw
            ]

            count_row = conn.execute(
                f'''
                SELECT COUNT(*) AS count
                FROM "{table_name}"
                '''
            ).fetchone()

            tables.append(
                {
                    "name": table_name,
                    "row_count": (
                        count_row["count"]
                        if count_row
                        else 0
                    ),
                    "columns": columns,
                    "foreign_keys": foreign_keys,
                    "sample_rows": sample_rows,
                }
            )

        return {
            "source_type": "sqlite",
            "path": str(db_path),
            "tables": tables,
        }

    finally:
        conn.close()


# ======================================================
# Existing Semantic Mappings
# ======================================================

@router.get("/projects")
def list_projects():
    return {"projects": state_repository.list_projects()}

@router.post("/projects")
def create_project(request: ProjectRequest):
    return state_repository.create_project({"id": str(uuid.uuid4()), "name": request.name, "description": request.description})

@router.get("/projects/{project_id}/overview")
def project_overview(project_id: str):
    project = state_repository.get_project(project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")
    try:
        entities = get_mapper(project_id).mappings
        entity_count = len(entities)
        relation_count = sum(len(item.get("relations", {})) for item in entities.values())
    except FileNotFoundError:
        entities = {}
        entity_count = relation_count = 0
    latest_version = state_repository.latest_mapping_version(project_id)
    latest_snapshot = state_repository.get_mapping_version(project_id, latest_version["version"]) if latest_version else None
    draft_mappings = list(entities.values()) if entity_count else []
    draft_status = "no_draft" if not draft_mappings else "unpublished" if not latest_snapshot or json.dumps(draft_mappings, sort_keys=True) != json.dumps(latest_snapshot["mappings"], sort_keys=True) else "published"
    return {"project": project, "source_count": len(state_repository.list_sources(project_id)), "entity_count": entity_count, "relation_count": relation_count, "latest_mapping_version": latest_version, "draft_status": draft_status, "latest_job": state_repository.latest_job(project_id), "builds": state_repository.list_jobs(project_id)}

@router.get("/projects/{project_id}/mapping-versions")
def mapping_versions(project_id: str):
    if state_repository.get_project(project_id) is None:
        raise HTTPException(status_code=404, detail="Project not found")
    return {"versions": state_repository.list_mapping_versions(project_id)}

@router.get("/projects/{project_id}/mapping-versions/{version}")
def mapping_version(project_id: str, version: int):
    result = state_repository.get_mapping_version(project_id, version)
    if result is None:
        raise HTTPException(status_code=404, detail="Mapping version not found")
    return result

@router.post("/projects/{project_id}/validate-mappings")
def validate_mappings(project_id: str, request: BuildRequest):
    db_path = resolve_source_path(request)
    mapper = get_mapper(project_id)
    errors: list[str] = []
    warnings: list[str] = []
    with sqlite3.connect(db_path) as connection:
        tables = {row[0] for row in connection.execute("SELECT name FROM sqlite_master WHERE type = 'table'")}
        for entity, mapping in mapper.mappings.items():
            ingestion = mapping.get("ingestion", {})
            table = ingestion.get("source_table")
            if not table or table not in tables:
                errors.append(f"{entity}: source_table '{table}' does not exist")
                continue
            columns = {row[1] for row in connection.execute(f'PRAGMA table_info("{table}")')}
            primary_key = ingestion.get("primary_key", "id")
            if primary_key not in columns:
                errors.append(f"{entity}: primary_key '{primary_key}' does not exist in {table}")
            for name, definition in mapping.get("properties", {}).items():
                if definition.get("column") not in columns:
                    errors.append(f"{entity}.{name}: column '{definition.get('column')}' does not exist")
            for name, relation in mapping.get("relations", {}).items():
                target = relation.get("target", {}).get("entity")
                foreign_key = relation.get("ingestion", {}).get("foreign_key")
                if target not in mapper.mappings:
                    errors.append(f"{entity}.{name}: target entity '{target}' does not exist")
                if foreign_key not in columns:
                    errors.append(f"{entity}.{name}: foreign_key '{foreign_key}' does not exist")
            if not mapping.get("properties"):
                warnings.append(f"{entity}: no properties are mapped")
    return {"valid": not errors, "errors": errors, "warnings": warnings}

@router.post("/projects/{project_id}/build-preview")
def build_preview(project_id: str, request: BuildRequest):
    db_path = resolve_source_path(request)
    mapper = get_mapper(project_id)
    preview = []
    with sqlite3.connect(db_path) as connection:
        connection.row_factory = sqlite3.Row
        for entity, mapping in mapper.mappings.items():
            ingestion = mapping.get("ingestion", {})
            table = ingestion.get("source_table")
            primary_key = ingestion.get("primary_key", "id")
            rows = [dict(row) for row in connection.execute(f'SELECT * FROM "{table}"')]
            valid_rows = [row for row in rows if row.get(primary_key) is not None]
            missing_primary_key_samples = [row for row in rows if row.get(primary_key) is None][:20]
            relations = []
            for name, relation in mapping.get("relations", {}).items():
                foreign_key = relation.get("ingestion", {}).get("foreign_key")
                target = relation.get("target", {}).get("entity")
                target_mapping = mapper.get_entity(target)
                target_table = target_mapping.get("ingestion", {}).get("source_table")
                target_key = relation.get("ingestion", {}).get("target_key") or target_mapping.get("ingestion", {}).get("primary_key", "id")
                target_ids = {row[0] for row in connection.execute(f'SELECT "{target_key}" FROM "{target_table}"')}
                candidates = [row for row in valid_rows if row.get(foreign_key) is not None]
                matched = sum(row.get(foreign_key) in target_ids for row in candidates)
                unmatched_samples = [{"foreign_key": row.get(foreign_key), "primary_key": row.get(primary_key)} for row in candidates if row.get(foreign_key) not in target_ids][:20]
                relations.append({"name": name, "candidates": len(candidates), "matched": matched, "unmatched": len(candidates) - matched, "unmatched_samples": unmatched_samples})
            preview.append({"entity": entity, "source_table": table, "rows": len(rows), "nodes": len(valid_rows), "skipped_missing_primary_key": len(rows) - len(valid_rows), "missing_primary_key_samples": missing_primary_key_samples, "relations": relations})
    return {"entities": preview}

@router.post("/projects/{project_id}/mapping-versions/{version}/restore")
def restore_mapping_version(project_id: str, version: int):
    snapshot = state_repository.get_mapping_version(project_id, version)
    if snapshot is None:
        raise HTTPException(status_code=404, detail="Mapping version not found")
    get_mapping_service(project_id).replace_all(snapshot["mappings"])
    return {"status": "restored_to_draft", "project_id": project_id, "version": version, "mapping_count": len(snapshot["mappings"])}

@router.get("/sources")
def list_sources(project_id: str | None = None):
    return {"sources": state_repository.list_sources(project_id)}


@router.post("/sources")
def save_source(request: SourceProfileRequest):
    if request.project_id and state_repository.get_project(request.project_id) is None:
        raise HTTPException(status_code=404, detail="Project not found")
    if request.source_type != "sqlite":
        raise HTTPException(status_code=400, detail="Only sqlite sources are currently supported")

    path = resolve_sqlite_path(request.config.get("path"))
    return state_repository.save_source({
        "id": str(uuid.uuid4()),
        "project_id": request.project_id,
        "name": request.name,
        "source_type": request.source_type,
        "config": {"path": str(path)},
    })


@router.delete("/sources/{source_id}")
def delete_source(source_id: str):
    if not state_repository.delete_source(source_id):
        raise HTTPException(status_code=404, detail="Source profile not found")
    return {"status": "deleted", "id": source_id}

@router.post("/sources/{source_id}/active")
def set_source_active(source_id: str, active: bool):
    source = state_repository.set_source_active(source_id, active)
    if source is None:
        raise HTTPException(status_code=404, detail="Source profile not found")
    return source

@router.get("/mappings")
def get_mappings(project_id: str):

    mapper = get_mapper(project_id)

    result = []

    for entity, mapping in mapper.mappings.items():

        result.append(
            {
                "entity": entity,
                "label": mapping.get(
                    "label",
                    entity,
                ),
                "source": mapping.get(
                    "source",
                    {},
                ),
                "ingestion": mapping.get(
                    "ingestion",
                    {},
                ),
                "properties": mapping.get(
                    "properties",
                    {},
                ),
                "relations": mapping.get(
                    "relations",
                    {},
                ),
            }
        )

    return {
        "count": len(result),
        "mappings": result,
    }

@router.put("/mappings")
def replace_mappings(request: MappingReplaceRequest):
    if state_repository.get_project(request.project_id) is None:
        raise HTTPException(status_code=404, detail="Project not found")
    if any(mapping.project_id != request.project_id for mapping in request.mappings):
        raise HTTPException(status_code=400, detail="Every mapping must belong to project_id")

    mappings = [mapping.model_dump() for mapping in request.mappings]
    get_mapping_service(request.project_id).replace_all(mappings)
    return {"status": "replaced", "project_id": request.project_id, "count": len(mappings)}


# ======================================================
# Graph Preview
# ======================================================

@router.get("/preview")
def preview_graph():

    mapper = get_mapper()

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
                "node_label": mapping.get(
                    "source",
                    {},
                ).get(
                    "node_label",
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

        for relation_name, relation in (
            mapping.get(
                "relations",
                {},
            ).items()
        ):

            target = (
                relation
                .get("target", {})
                .get("entity")
            )

            if not target:
                continue

            edges.append(
                {
                    "source": entity,
                    "target": target,
                    "name": relation_name,
                    "label": relation.get(
                        "label",
                        relation_name,
                    ),
                    "relationship_type": (
                        relation.get(
                            "relationship_type",
                            relation_name.upper(),
                        )
                    ),
                }
            )

    return {
        "nodes": nodes,
        "edges": edges,
    }


# ======================================================
# Build
# ======================================================

@router.post("/build")
def start_build(
    request: BuildRequest,
    background_tasks: BackgroundTasks,
):

    if not request.project_id:
        raise HTTPException(status_code=400, detail="project_id is required")
    db_path = resolve_source_path(request)
    mapper = get_mapper(request.project_id)
    version = state_repository.create_mapping_version(request.project_id, list(mapper.mappings.values()))

    job = create_job(source_id=request.source_id, project_id=request.project_id)

    def pipeline_factory(
        on_progress,
    ):

        # 重新讀 YAML
        #
        # 未來前端儲存 mapping 後，
        # build 一定要吃最新 mapping。
        mapper = get_mapper(request.project_id)

        pipeline = IngestionPipeline(
            mapper=mapper,
            neo4j_uri=os.environ["NEO4J_URI"],
            neo4j_user=os.environ["NEO4J_USER"],
            neo4j_password=os.environ["NEO4J_PASSWORD"],
            project_id=request.project_id,
            on_progress=on_progress,
        )

        pipeline.register_reader(
            "sqlite",
            SQLiteSourceReader(
                str(db_path)
            ),
        )

        return pipeline

    background_tasks.add_task(
        run_ingestion_job,
        job,
        pipeline_factory,
        request.mode == "full",
    )

    return {
        "job_id": job.id,
        "status": job.status,
        "mapping_version": version,
    }


# ======================================================
# Build Status
# ======================================================

@router.get("/build/{job_id}")
def get_build_status(
    job_id: str,
):

    job = get_job(
        job_id
    )

    if job is None:
        raise HTTPException(
            status_code=404,
            detail="Build job not found",
        )

    return job.to_dict()

@router.get("/mapping/{entity}")
def get_mapping(
    entity: str,
    project_id: str,
):
    mapping = get_mapping_service(project_id).get_mapping(
        entity
    )

    if mapping is None:
        raise HTTPException(
            status_code=404,
            detail=f"Mapping not found: {entity}",
        )

    return mapping


@router.post("/mapping")
def save_mapping(
    request: MappingRequest,
):
    try:
        mapping = request.model_dump()

        file_path = get_mapping_service(request.project_id).save_mapping(
            mapping
        )

        return {
            "status": "saved",
            "entity": request.entity,
            "file": str(file_path),
        }

    except ValueError as e:
        raise HTTPException(
            status_code=400,
            detail=str(e),
        )


@router.delete("/mapping/{entity}")
def delete_mapping(
    entity: str,
):
    deleted = mapping_service.delete_mapping(
        entity
    )

    if not deleted:
        raise HTTPException(
            status_code=404,
            detail=f"Mapping not found: {entity}",
        )

    return {
        "status": "deleted",
        "entity": entity,
    }
