# app/services/ingestion_job.py

import threading
import uuid
from datetime import datetime, timezone
from enum import Enum


class JobStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    DONE = "done"
    FAILED = "failed"


class IngestionJob:
    """記錄一次建置任務的狀態，讓前端可以輪詢查詢進度。"""

    def __init__(self):
        self.id = str(uuid.uuid4())
        self.status = JobStatus.PENDING
        self.logs: list[dict] = []
        self.error: str | None = None
        self.started_at = datetime.now(timezone.utc).isoformat()
        self.finished_at: str | None = None

    def log(self, step: str, message: str):
        self.logs.append({
            "step": step,
            "message": message,
            "time": datetime.now(timezone.utc).isoformat(),
        })

    def to_dict(self):
        return {
            "id": self.id,
            "status": self.status,
            "logs": self.logs,
            "error": self.error,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
        }


# 簡單版：存在記憶體裡（單機開發夠用；正式環境建議換成 Redis 等外部儲存）
_jobs: dict[str, IngestionJob] = {}


def create_job() -> IngestionJob:
    job = IngestionJob()
    _jobs[job.id] = job
    return job


def get_job(job_id: str) -> IngestionJob | None:
    return _jobs.get(job_id)

def run_ingestion_job(
    job: IngestionJob,
    pipeline_factory,
    reset: bool = True,
):
    """在背景執行緒跑建置流程，邊跑邊更新 job 狀態。"""

    job.status = JobStatus.RUNNING

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

        pipeline.run(
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