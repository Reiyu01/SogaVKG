"""Persistent metadata for the platform itself, not for ingested data."""

import json
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


class PlatformStateRepository:
    def __init__(self, path: Path):
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    def _connection(self):
        connection = sqlite3.connect(self.path)
        connection.row_factory = sqlite3.Row
        return connection

    def _initialize(self):
        with self._connection() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS source_profiles (
                    id TEXT PRIMARY KEY,
                    project_id TEXT,
                    active INTEGER NOT NULL DEFAULT 1,
                    name TEXT NOT NULL,
                    source_type TEXT NOT NULL,
                    config_json TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS ingestion_jobs (
                    id TEXT PRIMARY KEY,
                    project_id TEXT,
                    status TEXT NOT NULL,
                    logs_json TEXT NOT NULL,
                    error TEXT,
                    source_id TEXT,
                    started_at TEXT NOT NULL,
                    finished_at TEXT
                    , result_json TEXT
                    , mapping_version_id TEXT
                );
                CREATE TABLE IF NOT EXISTS projects (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    description TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS mapping_versions (
                    id TEXT PRIMARY KEY,
                    project_id TEXT NOT NULL,
                    version INTEGER NOT NULL,
                    mappings_json TEXT NOT NULL,
                    entity_alignments_json TEXT NOT NULL DEFAULT '[]',
                    created_at TEXT NOT NULL,
                    UNIQUE(project_id, version)
                );
                CREATE TABLE IF NOT EXISTS entity_alignments (
                    id TEXT PRIMARY KEY,
                    project_id TEXT NOT NULL,
                    source_entity TEXT NOT NULL,
                    target_entity TEXT NOT NULL,
                    source_column TEXT NOT NULL,
                    target_column TEXT NOT NULL,
                    relation_type TEXT NOT NULL,
                    label TEXT NOT NULL,
                    normalization_rule TEXT NOT NULL DEFAULT 'exact',
                    created_at TEXT NOT NULL,
                    UNIQUE(project_id, source_entity, target_entity)
                );
                CREATE TABLE IF NOT EXISTS entity_alignment_audit_events (
                    id TEXT PRIMARY KEY,
                    project_id TEXT NOT NULL,
                    alignment_id TEXT NOT NULL,
                    action TEXT NOT NULL,
                    alignment_json TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );
                """
            )
            self._add_column_if_missing(connection, "source_profiles", "project_id", "TEXT")
            self._add_column_if_missing(connection, "source_profiles", "active", "INTEGER NOT NULL DEFAULT 1")
            self._add_column_if_missing(connection, "ingestion_jobs", "project_id", "TEXT")
            self._add_column_if_missing(connection, "ingestion_jobs", "result_json", "TEXT")
            self._add_column_if_missing(connection, "ingestion_jobs", "mapping_version_id", "TEXT")
            self._add_column_if_missing(connection, "mapping_versions", "entity_alignments_json", "TEXT NOT NULL DEFAULT '[]'")
            self._add_column_if_missing(connection, "entity_alignments", "normalization_rule", "TEXT NOT NULL DEFAULT 'exact'")

    @staticmethod
    def _add_column_if_missing(connection, table: str, column: str, definition: str):
        columns = {row["name"] for row in connection.execute(f"PRAGMA table_info({table})")}
        if column not in columns:
            connection.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")

    def create_project(self, project: dict[str, Any]) -> dict[str, Any]:
        now = datetime.now(timezone.utc).isoformat()
        with self._connection() as connection:
            connection.execute("INSERT INTO projects VALUES (?, ?, ?, ?, ?)", (project["id"], project["name"], project.get("description"), now, now))
        return self.get_project(project["id"])

    def list_projects(self) -> list[dict[str, Any]]:
        with self._connection() as connection:
            rows = connection.execute("SELECT * FROM projects ORDER BY updated_at DESC").fetchall()
        return [dict(row) for row in rows]

    def get_project(self, project_id: str) -> dict[str, Any] | None:
        with self._connection() as connection:
            row = connection.execute("SELECT * FROM projects WHERE id = ?", (project_id,)).fetchone()
        return dict(row) if row else None

    def create_mapping_version(self, project_id: str, mappings: list[dict[str, Any]], entity_alignments: list[dict[str, Any]] | None = None) -> dict[str, Any]:
        now = datetime.now(timezone.utc).isoformat()
        with self._connection() as connection:
            version = connection.execute("SELECT COALESCE(MAX(version), 0) + 1 FROM mapping_versions WHERE project_id = ?", (project_id,)).fetchone()[0]
            version_id = f"{project_id}:v{version}"
            connection.execute("INSERT INTO mapping_versions (id, project_id, version, mappings_json, entity_alignments_json, created_at) VALUES (?, ?, ?, ?, ?, ?)", (version_id, project_id, version, json.dumps(mappings), json.dumps(entity_alignments or []), now))
        return {"id": version_id, "version": version, "created_at": now}

    def latest_mapping_version(self, project_id: str) -> dict[str, Any] | None:
        with self._connection() as connection:
            row = connection.execute("SELECT id, version, created_at FROM mapping_versions WHERE project_id = ? ORDER BY version DESC LIMIT 1", (project_id,)).fetchone()
        return dict(row) if row else None

    def list_mapping_versions(self, project_id: str) -> list[dict[str, Any]]:
        with self._connection() as connection:
            rows = connection.execute("SELECT id, version, created_at FROM mapping_versions WHERE project_id = ? ORDER BY version DESC", (project_id,)).fetchall()
        return [dict(row) for row in rows]

    def get_mapping_version(self, project_id: str, version: int) -> dict[str, Any] | None:
        with self._connection() as connection:
            row = connection.execute("SELECT * FROM mapping_versions WHERE project_id = ? AND version = ?", (project_id, version)).fetchone()
        if not row:
            return None
        return {"id": row["id"], "version": row["version"], "created_at": row["created_at"], "mappings": json.loads(row["mappings_json"]), "entity_alignments": json.loads(row["entity_alignments_json"] or "[]")}

    def list_entity_alignments(self, project_id: str) -> list[dict[str, Any]]:
        with self._connection() as connection:
            rows = connection.execute("SELECT * FROM entity_alignments WHERE project_id = ? ORDER BY created_at", (project_id,)).fetchall()
        return [dict(row) for row in rows]

    def save_entity_alignment(self, alignment: dict[str, Any]) -> dict[str, Any]:
        now = datetime.now(timezone.utc).isoformat()
        with self._connection() as connection:
            existing = connection.execute("SELECT * FROM entity_alignments WHERE project_id = ? AND source_entity = ? AND target_entity = ?", (alignment["project_id"], alignment["source_entity"], alignment["target_entity"])).fetchone()
            connection.execute(
                """INSERT INTO entity_alignments
                (id, project_id, source_entity, target_entity, source_column, target_column, relation_type, label, normalization_rule, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(project_id, source_entity, target_entity) DO UPDATE SET
                    source_column = excluded.source_column, target_column = excluded.target_column,
                    relation_type = excluded.relation_type, label = excluded.label, normalization_rule = excluded.normalization_rule""",
                (alignment["id"], alignment["project_id"], alignment["source_entity"], alignment["target_entity"],
                 alignment["source_column"], alignment["target_column"], alignment.get("relation_type", "CONCEPT_EQUIVALENT_TO"),
                 alignment.get("label", "同一概念"), alignment.get("normalization_rule", "exact"), now),
            )
            row = connection.execute("SELECT * FROM entity_alignments WHERE project_id = ? AND source_entity = ? AND target_entity = ?", (alignment["project_id"], alignment["source_entity"], alignment["target_entity"])).fetchone()
            saved = dict(row)
            self._record_entity_alignment_audit(connection, saved, "updated" if existing else "created")
        return saved

    def delete_entity_alignment(self, project_id: str, alignment_id: str) -> bool:
        with self._connection() as connection:
            existing = connection.execute("SELECT * FROM entity_alignments WHERE project_id = ? AND id = ?", (project_id, alignment_id)).fetchone()
            cursor = connection.execute("DELETE FROM entity_alignments WHERE project_id = ? AND id = ?", (project_id, alignment_id))
            if existing:
                self._record_entity_alignment_audit(connection, dict(existing), "deleted")
        return cursor.rowcount > 0

    def list_entity_alignment_audit_events(self, project_id: str, limit: int = 100) -> list[dict[str, Any]]:
        with self._connection() as connection:
            rows = connection.execute("SELECT * FROM entity_alignment_audit_events WHERE project_id = ? ORDER BY created_at DESC LIMIT ?", (project_id, limit)).fetchall()
        return [{**dict(row), "alignment": json.loads(row["alignment_json"])} for row in rows]

    @staticmethod
    def _record_entity_alignment_audit(connection, alignment: dict[str, Any], action: str) -> None:
        connection.execute("INSERT INTO entity_alignment_audit_events VALUES (?, ?, ?, ?, ?, ?)", (str(uuid.uuid4()), alignment["project_id"], alignment["id"], action, json.dumps(alignment), datetime.now(timezone.utc).isoformat()))

    def latest_job(self, project_id: str) -> dict[str, Any] | None:
        with self._connection() as connection:
            row = connection.execute("SELECT * FROM ingestion_jobs WHERE project_id = ? ORDER BY started_at DESC LIMIT 1", (project_id,)).fetchone()
        return self.get_job(row["id"]) if row else None

    def list_jobs(self, project_id: str, limit: int = 10) -> list[dict[str, Any]]:
        with self._connection() as connection:
            rows = connection.execute("SELECT id FROM ingestion_jobs WHERE project_id = ? ORDER BY started_at DESC LIMIT ?", (project_id, limit)).fetchall()
        return [self.get_job(row["id"]) for row in rows]

    def list_sources(self, project_id: str | None = None) -> list[dict[str, Any]]:
        with self._connection() as connection:
            if project_id:
                rows = connection.execute("SELECT * FROM source_profiles WHERE project_id = ? ORDER BY updated_at DESC", (project_id,)).fetchall()
            else:
                rows = connection.execute("SELECT * FROM source_profiles ORDER BY updated_at DESC").fetchall()
        return [self._source_from_row(row) for row in rows]

    def get_source(self, source_id: str) -> dict[str, Any] | None:
        with self._connection() as connection:
            row = connection.execute(
                "SELECT * FROM source_profiles WHERE id = ?", (source_id,)
            ).fetchone()
        return self._source_from_row(row) if row else None

    def save_source(self, source: dict[str, Any]) -> dict[str, Any]:
        now = datetime.now(timezone.utc).isoformat()
        with self._connection() as connection:
            connection.execute(
                """
                INSERT INTO source_profiles (id, project_id, name, source_type, config_json, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    name = excluded.name,
                    source_type = excluded.source_type,
                    config_json = excluded.config_json,
                    updated_at = excluded.updated_at
                """,
                (
                    source["id"], source.get("project_id"), source["name"], source["source_type"],
                    json.dumps(source["config"]), now, now,
                ),
            )
        return self.get_source(source["id"])  # type: ignore[return-value]

    def delete_source(self, source_id: str) -> bool:
        with self._connection() as connection:
            cursor = connection.execute("DELETE FROM source_profiles WHERE id = ?", (source_id,))
        return cursor.rowcount > 0

    def set_source_active(self, source_id: str, active: bool) -> dict[str, Any] | None:
        with self._connection() as connection:
            connection.execute("UPDATE source_profiles SET active = ?, updated_at = ? WHERE id = ?", (int(active), datetime.now(timezone.utc).isoformat(), source_id))
        return self.get_source(source_id)

    def create_job(self, job: dict[str, Any]) -> None:
        with self._connection() as connection:
            connection.execute(
                """INSERT INTO ingestion_jobs
                (id, project_id, status, logs_json, error, source_id, started_at, finished_at, result_json, mapping_version_id)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    job["id"], job.get("project_id"), job["status"], json.dumps(job["logs"]), job["error"],
                    job.get("source_id"), job["started_at"], job["finished_at"], json.dumps(job.get("result")), job.get("mapping_version_id"),
                ),
            )

    def update_job(self, job: dict[str, Any]) -> None:
        with self._connection() as connection:
            connection.execute(
                """UPDATE ingestion_jobs
                SET status = ?, logs_json = ?, error = ?, finished_at = ?, result_json = ?, mapping_version_id = ?
                WHERE id = ?""",
                (job["status"], json.dumps(job["logs"]), job["error"], job["finished_at"], json.dumps(job.get("result")), job.get("mapping_version_id"), job["id"]),
            )

    def get_job(self, job_id: str) -> dict[str, Any] | None:
        with self._connection() as connection:
            row = connection.execute("SELECT * FROM ingestion_jobs WHERE id = ?", (job_id,)).fetchone()
        if not row:
            return None
        return {
            "id": row["id"], "status": row["status"], "logs": json.loads(row["logs_json"]),
            "error": row["error"], "source_id": row["source_id"], "project_id": row["project_id"],
            "started_at": row["started_at"], "finished_at": row["finished_at"], "result": json.loads(row["result_json"]) if row["result_json"] else None,
            "mapping_version_id": row["mapping_version_id"],
        }

    @staticmethod
    def _source_from_row(row: sqlite3.Row) -> dict[str, Any]:
        return {
            "id": row["id"], "project_id": row["project_id"], "name": row["name"], "source_type": row["source_type"], "active": bool(row["active"]),
            "config": json.loads(row["config_json"]), "created_at": row["created_at"],
            "updated_at": row["updated_at"],
        }
