from __future__ import annotations

import threading
import uuid
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Optional

from app.schemas.edbo import EdboTaskRequest, TaskStatus
from app.services.edbo_service import run_edbo_recommendation


@dataclass
class TaskRecord:
    task_id: str
    status: TaskStatus = TaskStatus.PENDING
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    workdir: Optional[Path] = None
    lock: threading.Lock = field(default_factory=threading.Lock)


class TaskService:
    def __init__(self, work_root: Path, max_workers: int = 2) -> None:
        self.work_root = work_root
        self.work_root.mkdir(parents=True, exist_ok=True)
        self._tasks: Dict[str, TaskRecord] = {}
        self._tasks_lock = threading.Lock()
        self._executor = ThreadPoolExecutor(max_workers=max_workers)

    def submit(self, request: EdboTaskRequest) -> TaskRecord:
        task_id = str(uuid.uuid4())
        record = TaskRecord(task_id=task_id, workdir=self.work_root / task_id)
        with self._tasks_lock:
            self._tasks[task_id] = record

        self._executor.submit(self._run_task, record, request)
        return record

    def get(self, task_id: str) -> Optional[TaskRecord]:
        with self._tasks_lock:
            return self._tasks.get(task_id)

    def _run_task(self, record: TaskRecord, request: EdboTaskRequest) -> None:
        with record.lock:
            record.status = TaskStatus.PROCESSING

        try:
            if record.workdir is None:
                raise RuntimeError("Task workdir was not initialized")
            result = run_edbo_recommendation(request=request, workdir=record.workdir, task_id=record.task_id)
        except Exception as exc:  # noqa: BLE001 - errors are returned to the task status endpoint.
            with record.lock:
                record.error = str(exc)
                record.status = TaskStatus.FAILED
            return

        with record.lock:
            record.result = result
            record.status = TaskStatus.COMPLETED
