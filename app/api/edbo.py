from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request, status

from app.schemas.edbo import EdboTaskRequest, TaskStatus
from app.services.task_service import TaskService


router = APIRouter(prefix="/api/v1/edbo", tags=["edbo"])


def api_success(data: object, message: str = "ok") -> dict[str, object]:
    return {"code": 0, "message": message, "data": data}


def api_error(code: int, message: str, data: object = None) -> dict[str, object]:
    return {"code": code, "message": message, "data": data}


def task_service(request: Request) -> TaskService:
    return request.app.state.task_service


@router.post("/tasks", status_code=status.HTTP_202_ACCEPTED)
async def submit_task(payload: EdboTaskRequest, request: Request) -> dict[str, object]:
    record = task_service(request).submit(payload)
    return api_success(
        {
            "task_id": record.task_id,
            "status": record.status.value,
            "status_url": f"/api/v1/edbo/tasks/{record.task_id}",
            "result_url": f"/api/v1/edbo/tasks/{record.task_id}/result",
        }
    )


@router.get("/tasks/{task_id}")
async def get_task_status(task_id: str, request: Request) -> dict[str, object]:
    record = task_service(request).get(task_id)
    if record is None:
        raise HTTPException(status_code=404, detail=api_error(40401, "task not found"))

    with record.lock:
        status_value = record.status
        error = record.error

    if status_value == TaskStatus.FAILED:
        return api_error(50001, error or "EDBO optimization failed", {"task_id": task_id, "status": status_value.value})

    data = {"task_id": task_id, "status": status_value.value, "progress": None}
    if status_value == TaskStatus.COMPLETED:
        data["result_url"] = f"/api/v1/edbo/tasks/{task_id}/result"
    return api_success(data)


@router.get("/tasks/{task_id}/result")
async def get_task_result(task_id: str, request: Request) -> dict[str, object]:
    record = task_service(request).get(task_id)
    if record is None:
        raise HTTPException(status_code=404, detail=api_error(40401, "task not found"))

    with record.lock:
        status_value = record.status
        result = record.result
        error = record.error

    if status_value == TaskStatus.FAILED:
        return api_error(50001, error or "EDBO optimization failed", {"task_id": task_id, "status": status_value.value})
    if status_value != TaskStatus.COMPLETED:
        return api_error(40901, "task is not completed", {"task_id": task_id, "status": status_value.value})

    return api_success(result)
