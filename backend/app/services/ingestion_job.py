# app/services/ingestion_job.py

import uuid
from datetime import datetime, timezone
from enum import Enum

from app.core.config import PLATFORM_STATE_DB_PATH
from app.repositories.platform_state import PlatformStateRepository


repository = PlatformStateRepository(PLATFORM_STATE_DB_PATH)


class JobStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    DONE = "done"
    FAILED = "failed"


class IngestionJob:
    """記錄一次建置任務的狀態，讓前端可以輪詢查詢進度。"""

    def __init__(self, source_id: str | None = None, project_id: str | None = None, data: dict | None = None):
        data = data or {}
        self.id = data.get("id", str(uuid.uuid4()))
        self.source_id = data.get("source_id", source_id)
        self.project_id = data.get("project_id", project_id)
        self.status = JobStatus(data.get("status", JobStatus.PENDING))
        self.logs: list[dict] = data.get("logs", [])
        self.error: str | None = data.get("error")
        self.started_at = data.get("started_at", datetime.now(timezone.utc).isoformat())
        self.finished_at: str | None = data.get("finished_at")
        self.result = data.get("result")

    def log(self, step: str, message: str):
        self.logs.append({
            "step": step,
            "message": message,
            "time": datetime.now(timezone.utc).isoformat(),
        })
        repository.update_job(self.to_dict())

    def to_dict(self):
        return {
            "id": self.id,
            "status": self.status,
            "logs": self.logs,
            "error": self.error,
            "source_id": self.source_id,
            "project_id": self.project_id,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "result": self.result,
        }


def create_job(source_id: str | None = None, project_id: str | None = None) -> IngestionJob:
    job = IngestionJob(source_id=source_id, project_id=project_id)
    repository.create_job(job.to_dict())
    return job


def get_job(job_id: str) -> IngestionJob | None:
    data = repository.get_job(job_id)
    return IngestionJob(data=data) if data else None

def run_ingestion_job(
    job: IngestionJob,
    pipeline_factory,
    reset: bool = True,
):
    """在背景執行緒跑建置流程，邊跑邊更新 job 狀態。"""

    job.status = JobStatus.RUNNING
    repository.update_job(job.to_dict())

    def on_progress(
        step: str,
        message: str,
    ):
        job.log(
            step,
            message,
        )

    try:
        pipeline = pipeline_factory(
            on_progress
        )

        job.result = pipeline.run(
            reset=reset
        )

        pipeline.close()

        job.status = JobStatus.DONE

    except Exception as exc:
        job.status = JobStatus.FAILED
        job.error = str(exc)

    finally:
        job.finished_at = (
            datetime.now(
                timezone.utc
            ).isoformat()
        )
        repository.update_job(job.to_dict())
