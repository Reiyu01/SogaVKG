from fastapi import APIRouter, BackgroundTasks, HTTPException
from pydantic import BaseModel, Field
from pathlib import Path
import os
import sqlite3

from app.core.config import (
    SQLITE_DB_PATH,
    MAPPING_DIR,
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

router = APIRouter(
    prefix="/builder",
    tags=["Knowledge Builder"],
)

mapping_service = MappingService(
    MAPPING_DIR
)
# ======================================================
# Request Models
# ======================================================

class SourceSchemaRequest(BaseModel):
    source_type: str = "sqlite"
    path: str | None = None

class MappingRequest(BaseModel):
    entity: str
    label: str | None = None
    source: dict[str, Any]
    ingestion: dict[str, Any]
    properties: dict[str, Any]
    relations: dict[str, Any] = Field(default_factory=dict)

# ======================================================
# Helpers
# ======================================================

def get_mapper() -> SemanticMapper:
    """
    每次重新建立 mapper。

    原因：
    SemanticMapper 只會在 __init__ 時讀取 YAML。
    未來 Builder 修改 YAML 後，
    如果繼續使用舊 mapper，
    就不會看到新的 mapping。
    """
    return SemanticMapper(MAPPING_DIR)


def resolve_sqlite_path(
    requested_path: str | None,
) -> Path:

    if requested_path:
        db_path = Path(requested_path)

        if not db_path.is_absolute():
            db_path = Path.cwd() / db_path
    else:
        db_path = Path(SQLITE_DB_PATH)

    db_path = db_path.resolve()

    if not db_path.exists():
        raise HTTPException(
            status_code=404,
            detail=f"SQLite database not found: {db_path}",
        )

    return db_path


# ======================================================
# Health
# ======================================================

@router.get("/health")
def builder_health():

    return {
        "status": "ok",
        "mapping_dir": str(MAPPING_DIR),
        "sqlite_db": str(SQLITE_DB_PATH),
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

@router.get("/mappings")
def get_mappings():

    mapper = get_mapper()

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
    background_tasks: BackgroundTasks,
):

    job = create_job()

    def pipeline_factory(
        on_progress,
    ):

        # 重新讀 YAML
        #
        # 未來前端儲存 mapping 後，
        # build 一定要吃最新 mapping。
        mapper = get_mapper()

        pipeline = IngestionPipeline(
            mapper=mapper,
            neo4j_uri=os.environ["NEO4J_URI"],
            neo4j_user=os.environ["NEO4J_USER"],
            neo4j_password=os.environ["NEO4J_PASSWORD"],
            on_progress=on_progress,
        )

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
        "job_id": job.id,
        "status": job.status,
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
):
    mapping = mapping_service.get_mapping(
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

        file_path = mapping_service.save_mapping(
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