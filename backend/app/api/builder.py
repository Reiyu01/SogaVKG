from fastapi import APIRouter, BackgroundTasks, HTTPException
from pydantic import BaseModel, Field
from pathlib import Path
import os
import uuid
import json
from datetime import datetime, timezone

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
from app.services.data_quality import preview_mappings_by_source
from app.services.source_resolution import resolve_entity_source_adapters
from app.services.entity_alignment import preview_entity_alignment
from app.adapters.source_adapter import create_source_adapter
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
    config: dict[str, Any] = Field(default_factory=dict)

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
    import_legacy_mappings: bool = False

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

class EntityAlignmentRequest(BaseModel):
    project_id: str
    source_entity: str
    target_entity: str
    source_column: str
    target_column: str
    label: str = "同一概念"
    relation_type: str = "CONCEPT_EQUIVALENT_TO"
    normalization_rule: str = "exact"

class RelationRuleRequest(BaseModel):
    project_id: str
    source_entity: str
    relation_name: str = Field(min_length=1, max_length=120)
    target_entity: str
    source_column: str
    target_column: str
    display_property: str | None = None

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


def sources_for_request(request: BuildRequest, fallback_path: Path | None = None) -> list[dict[str, Any]]:
    sources = state_repository.list_sources(request.project_id)
    if request.source_id:
        if not any(source["id"] == request.source_id and source["active"] for source in sources):
            raise HTTPException(status_code=400, detail="Selected source profile is unavailable or disabled")
        return sources
    if fallback_path is None:
        fallback_path = resolve_sqlite_path(request.source_path)
    return [{"id": "__build_source__", "active": True, "source_type": "sqlite", "config": {"path": str(fallback_path)}}] + sources


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
def get_source_schema(request: SourceSchemaRequest):
    config = dict(request.config)
    if request.source_type == "sqlite":
        config["path"] = str(resolve_sqlite_path(request.path or config.get("path")))
    try:
        return create_source_adapter(request.source_type, config).inspect_schema()
    except (KeyError, RuntimeError, ValueError) as error:
        raise HTTPException(status_code=400, detail=str(error)) from error


# ======================================================
# Existing Semantic Mappings
# ======================================================

@router.get("/projects")
def list_projects():
    return {"projects": state_repository.list_projects()}

@router.post("/projects")
def create_project(request: ProjectRequest):
    project = state_repository.create_project({"id": str(uuid.uuid4()), "name": request.name, "description": request.description})
    if request.import_legacy_mappings:
        get_mapping_service(project["id"]).replace_all(mapping_service.list_mappings())
    return project

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
    mapper = get_mapper(project_id)
    try:
        source_adapters = resolve_entity_source_adapters(mapper, sources_for_request(request))
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    errors: list[str] = []
    warnings: list[str] = []
    for entity, mapping in mapper.mappings.items():
        adapter = source_adapters[entity]
        ingestion = mapping.get("ingestion", {}); table = ingestion.get("source_table")
        if not table:
            errors.append(f"{entity}: source_table is required"); continue
        try:
            columns = adapter.table_columns(table)
        except Exception as error:
            errors.append(f"{entity}: source_table '{table}' cannot be read: {error}"); continue
        primary_key = ingestion.get("primary_key", "id")
        if primary_key not in columns:
            errors.append(f"{entity}: primary_key '{primary_key}' does not exist in {table}")
        else:
            duplicates = adapter.duplicate_keys(table, primary_key)
            if duplicates["duplicate_key_count"]:
                warnings.append(f"{entity}: {duplicates['duplicate_key_count']} duplicate primary key value(s), affecting {duplicates['duplicate_row_count']} extra row(s)")
        for name, definition in mapping.get("properties", {}).items():
            if definition.get("column") not in columns: errors.append(f"{entity}.{name}: column '{definition.get('column')}' does not exist")
        for name, relation in mapping.get("relations", {}).items():
            target = relation.get("target", {}).get("entity"); foreign_key = relation.get("ingestion", {}).get("foreign_key")
            if target not in mapper.mappings: errors.append(f"{entity}.{name}: target entity '{target}' does not exist")
            if foreign_key not in columns: errors.append(f"{entity}.{name}: foreign_key '{foreign_key}' does not exist")
        if not mapping.get("properties"): warnings.append(f"{entity}: no properties are mapped")
    return {"valid": not errors, "errors": errors, "warnings": warnings}

@router.post("/projects/{project_id}/build-preview")
def build_preview(project_id: str, request: BuildRequest):
    mapper = get_mapper(project_id)
    try:
        source_adapters = resolve_entity_source_adapters(mapper, sources_for_request(request))
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    return {"entities": preview_mappings_by_source(mapper, source_adapters)}

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
    if request.source_type == "sqlite":
        config = {"path": str(resolve_sqlite_path(request.config.get("path")))}
    elif request.source_type == "postgresql":
        required = {"host", "database", "username", "credential_ref"}
        if missing := required - request.config.keys():
            raise HTTPException(status_code=400, detail=f"PostgreSQL config is missing: {', '.join(sorted(missing))}")
        config = {key: request.config[key] for key in ("host", "port", "database", "username", "credential_ref") if key in request.config}
    elif request.source_type == "google_sheets":
        required = {"spreadsheet_id", "credential_ref"}
        if missing := required - request.config.keys():
            raise HTTPException(status_code=400, detail=f"Google Sheets config is missing: {', '.join(sorted(missing))}")
        config = {key: request.config[key] for key in required}
    else:
        raise HTTPException(status_code=400, detail=f"Unsupported source type: {request.source_type}")
    return state_repository.save_source({
        "id": str(uuid.uuid4()),
        "project_id": request.project_id,
        "name": request.name,
        "source_type": request.source_type,
        "config": config,
    })


@router.put("/sources/{source_id}")
def update_source(source_id: str, request: SourceProfileRequest):
    existing = state_repository.get_source(source_id)
    if existing is None:
        raise HTTPException(status_code=404, detail="Source profile not found")
    if request.project_id != existing["project_id"]:
        raise HTTPException(status_code=400, detail="A source profile cannot be moved between projects")
    if request.source_type != "sqlite":
        raise HTTPException(status_code=400, detail="Only sqlite sources are currently supported")
    path = resolve_sqlite_path(request.config.get("path"))
    return state_repository.save_source({
        "id": source_id,
        "project_id": existing["project_id"],
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
    # A Builder run describes one source-backed model. Keep previously created
    # entity types in the project so a second source can add GoogleSheetAsset
    # beside the existing Asset model.
    existing = {item["entity"]: item for item in get_mapping_service(request.project_id).list_mappings()}
    existing.update({item["entity"]: item for item in mappings})
    get_mapping_service(request.project_id).replace_all(list(existing.values()))
    return {"status": "saved", "project_id": request.project_id, "count": len(mappings), "project_entity_count": len(existing)}


@router.get("/entity-alignments")
def list_entity_alignments(project_id: str):
    if state_repository.get_project(project_id) is None:
        raise HTTPException(status_code=404, detail="Project not found")
    return {"alignments": state_repository.list_entity_alignments(project_id)}


@router.get("/entity-alignments/audit-events")
def list_entity_alignment_audit_events(project_id: str):
    if state_repository.get_project(project_id) is None:
        raise HTTPException(status_code=404, detail="Project not found")
    return {"events": state_repository.list_entity_alignment_audit_events(project_id)}


def entity_alignment_preview(request: EntityAlignmentRequest) -> dict[str, Any]:
    if state_repository.get_project(request.project_id) is None:
        raise HTTPException(status_code=404, detail="Project not found")
    if request.source_entity == request.target_entity:
        raise HTTPException(status_code=400, detail="Identity mapping must connect two different entity types")
    mapper = get_mapper(request.project_id)
    try:
        source_mapping = mapper.get_entity(request.source_entity)
        target_mapping = mapper.get_entity(request.target_entity)
        adapters = resolve_entity_source_adapters(mapper, state_repository.list_sources(request.project_id))
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    source_columns = {item.get("column") for item in source_mapping.get("properties", {}).values()} | {source_mapping.get("ingestion", {}).get("primary_key", "id")}
    target_columns = {item.get("column") for item in target_mapping.get("properties", {}).values()} | {target_mapping.get("ingestion", {}).get("primary_key", "id")}
    if request.source_column not in source_columns or request.target_column not in target_columns:
        raise HTTPException(status_code=400, detail="Identity mapping fields must be mapped source columns")
    try:
        return preview_entity_alignment(source_mapping, target_mapping, adapters[request.source_entity], adapters[request.target_entity], request.source_column, request.target_column, request.normalization_rule)
    except Exception as error:
        raise HTTPException(status_code=400, detail=f"Could not preview Identity Mapping: {error}") from error


@router.post("/entity-alignments/preview")
def preview_entity_alignment_endpoint(request: EntityAlignmentRequest):
    return entity_alignment_preview(request)


@router.post("/entity-alignments")
def save_entity_alignment(request: EntityAlignmentRequest):
    preview = entity_alignment_preview(request)
    if not preview["one_to_one_valid"]:
        raise HTTPException(status_code=409, detail={"message": "Identity Mapping 未通過一對一驗證。", "preview": preview})
    return state_repository.save_entity_alignment({
        "id": str(uuid.uuid4()), "project_id": request.project_id,
        "source_entity": request.source_entity, "target_entity": request.target_entity,
        "source_column": request.source_column, "target_column": request.target_column,
        "label": request.label, "relation_type": request.relation_type,
        "normalization_rule": request.normalization_rule,
    })


@router.delete("/entity-alignments/{alignment_id}")
def delete_entity_alignment(alignment_id: str, project_id: str):
    if not state_repository.delete_entity_alignment(project_id, alignment_id):
        raise HTTPException(status_code=404, detail="Identity mapping not found")
    return {"status": "deleted", "id": alignment_id}


def validate_relation_rule(request: RelationRuleRequest) -> None:
    if state_repository.get_project(request.project_id) is None:
        raise HTTPException(status_code=404, detail="Project not found")
    if request.source_entity == request.target_entity:
        raise HTTPException(status_code=400, detail="Relation rule must connect two different entity types")
    try:
        mapper = get_mapper(request.project_id)
        source_mapping = mapper.get_entity(request.source_entity)
        target_mapping = mapper.get_entity(request.target_entity)
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    source_columns = {item.get("column") for item in source_mapping.get("properties", {}).values()} | {source_mapping.get("ingestion", {}).get("primary_key", "id")}
    target_columns = {item.get("column") for item in target_mapping.get("properties", {}).values()} | {target_mapping.get("ingestion", {}).get("primary_key", "id")}
    if request.source_column not in source_columns or request.target_column not in target_columns:
        raise HTTPException(status_code=400, detail="Relation rule fields must be mapped source columns")
    if request.display_property and request.display_property not in target_mapping.get("properties", {}):
        raise HTTPException(status_code=400, detail="Relation display_property must be a mapped target property")


@router.get("/relation-rules")
def list_relation_rules(project_id: str):
    if state_repository.get_project(project_id) is None:
        raise HTTPException(status_code=404, detail="Project not found")
    return {"relation_rules": state_repository.list_relation_rules(project_id)}


@router.post("/relation-rules")
def save_relation_rule(request: RelationRuleRequest):
    validate_relation_rule(request)
    return state_repository.save_relation_rule({"id": str(uuid.uuid4()), **request.model_dump()})


@router.delete("/relation-rules/{rule_id}")
def delete_relation_rule(rule_id: str, project_id: str):
    if not state_repository.delete_relation_rule(project_id, rule_id):
        raise HTTPException(status_code=404, detail="Relation rule not found")
    return {"status": "deleted", "id": rule_id}


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
):
    """Publish a validated Mapping for direct, read-only graph projection.

    This endpoint deliberately replaces the former Neo4j ingestion job. Source
    rows remain in the configured source; the graph is projected from
    those rows whenever it is explored.
    """
    if not request.project_id:
        raise HTTPException(status_code=400, detail="project_id is required")
    # A Mapping can be validated with an ad-hoc path in the builder. Persist that
    # path as a project source at publish time so the graph projection has an
    # explicit, enabled source to read afterwards.
    source_id = request.source_id
    if not source_id:
        db_path = resolve_sqlite_path(request.source_path)
        existing_source = next((
            source for source in state_repository.list_sources(request.project_id)
            if source["source_type"] == "sqlite" and source["config"].get("path") == str(db_path)
        ), None)
        if existing_source:
            source_id = existing_source["id"]
            if not existing_source["active"]:
                state_repository.set_source_active(source_id, True)
        else:
            source_id = str(uuid.uuid4())
            state_repository.save_source({
                "id": source_id,
                "project_id": request.project_id,
                "name": f"Published SQLite source ({db_path.name})",
                "source_type": "sqlite",
                "config": {"path": str(db_path)},
            })
    mapper = get_mapper(request.project_id)
    data_quality = preview_mappings_by_source(
        mapper,
        resolve_entity_source_adapters(mapper, state_repository.list_sources(request.project_id)),
    )
    version = state_repository.create_mapping_version(request.project_id, list(mapper.mappings.values()), state_repository.list_entity_alignments(request.project_id), state_repository.list_relation_rules(request.project_id))
    job = create_job(source_id=source_id, project_id=request.project_id)
    job.mapping_version_id = version["id"]
    job.status = "done"
    job.finished_at = datetime.now(timezone.utc).isoformat()
    job.result = {"mode": "projection", "mapping_version": version["version"], "data_quality": data_quality}
    job.logs = [{
        "step": "publish_mapping",
        "message": "Mapping 已發布；知識圖譜會直接由資料來源投影，不會匯入 Neo4j。",
        "time": job.finished_at,
    }]
    state_repository.update_job(job.to_dict())

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
