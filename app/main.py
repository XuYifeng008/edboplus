from __future__ import annotations

import os
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.edbo import router as edbo_router
from app.services.task_service import TaskService


def create_app() -> FastAPI:
    service = FastAPI(title="EDBO+ HTTP Service", version="1.0.0")

    cors_origins = _parse_csv_env("EDBO_CORS_ORIGINS", default=["*"])
    service.add_middleware(
        CORSMiddleware,
        allow_origins=cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    work_root = Path(os.getenv("EDBO_WORK_ROOT", "runtime/edbo_tasks")).resolve()
    max_workers = int(os.getenv("EDBO_MAX_WORKERS", "2"))
    service.state.task_service = TaskService(work_root=work_root, max_workers=max_workers)

    service.include_router(edbo_router)

    @service.get("/health")
    async def health() -> dict[str, object]:
        return {"code": 0, "message": "ok", "data": {"status": "ok"}}

    @service.exception_handler(RequestValidationError)
    async def validation_exception_handler(_: Request, exc: RequestValidationError) -> JSONResponse:
        return JSONResponse(
            status_code=422,
            content={"code": 40001, "message": str(exc), "data": None},
        )

    return service


def _parse_csv_env(name: str, default: list[str]) -> list[str]:
    value = os.getenv(name)
    if value is None:
        return default
    items = [item.strip() for item in value.split(",") if item.strip()]
    return items or default


app = create_app()
