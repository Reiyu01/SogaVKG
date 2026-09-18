"""Persistent metadata for the platform itself, not for ingested data."""

import json
import sqlite3
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
                    created_at TEXT NOT NULL,
                    UNIQUE(project_id, version)
                );
                """
            )
            self._add_column_if_missing(connection, "source_profiles", "project_id", "TEXT")
            self._add_column_if_missing(connection, "source_profiles", "active", "INTEGER NOT NULL DEFAULT 1")
            self._add_column_if_missing(connection, "ingestion_jobs", "project_id", "TEXT")
            self._add_column_if_missing(connection, "ingestion_jobs", "result_json", "TEXT")

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

    def create_mapping_version(self, project_id: str, mappings: list[dict[str, Any]]) -> dict[str, Any]:
        now = datetime.now(timezone.utc).isoformat()
        with self._connection() as connection:
            version = connection.execute("SELECT COALESCE(MAX(version), 0) + 1 FROM mapping_versions WHERE project_id = ?", (project_id,)).fetchone()[0]
            version_id = f"{project_id}:v{version}"
            connection.execute("INSERT INTO mapping_versions VALUES (?, ?, ?, ?, ?)", (version_id, project_id, version, json.dumps(mappings), now))
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
        return {"id": row["id"], "version": row["version"], "created_at": row["created_at"], "mappings": json.loads(row["mappings_json"])}

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
                (id, project_id, status, logs_json, error, source_id, started_at, finished_at, result_json)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    job["id"], job.get("project_id"), job["status"], json.dumps(job["logs"]), job["error"],
                    job.get("source_id"), job["started_at"], job["finished_at"], json.dumps(job.get("result")),
                ),
            )

    def update_job(self, job: dict[str, Any]) -> None:
        with self._connection() as connection:
            connection.execute(
                """UPDATE ingestion_jobs
                SET status = ?, logs_json = ?, error = ?, finished_at = ?, result_json = ?
                WHERE id = ?""",
                (job["status"], json.dumps(job["logs"]), job["error"], job["finished_at"], json.dumps(job.get("result")), job["id"]),
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
        }

    @staticmethod
    def _source_from_row(row: sqlite3.Row) -> dict[str, Any]:
        return {
            "id": row["id"], "project_id": row["project_id"], "name": row["name"], "source_type": row["source_type"], "active": bool(row["active"]),
            "config": json.loads(row["config_json"]), "created_at": row["created_at"],
            "updated_at": row["updated_at"],
        }
