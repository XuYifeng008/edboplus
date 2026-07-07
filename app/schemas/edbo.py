from __future__ import annotations

from enum import Enum
from typing import Any, Dict, Generic, List, Literal, Optional, TypeVar

from pydantic import BaseModel, Field


class Objective(BaseModel):
    name: str = Field(..., description="Objective column name in candidates.")
    mode: Literal["max", "min"] = Field(..., description="Whether to maximize or minimize the objective.")
    weight: Optional[float] = Field(default=None, description="Reserved for future weighted scoring.")


class EdboTaskRequest(BaseModel):
    task_id: Optional[str] = Field(default=None, description="Optional client task id for display/tracing.")
    batch: int = Field(default=5, ge=1, description="Number of recommendations to return.")
    seed: int = Field(default=0, description="Random seed used by EDBO+.")
    columns_features: Any = Field(
        default="all",
        description="Feature columns. Use 'all' to use every non-objective, non-id column.",
    )
    init_sampling_method: Literal["random", "lhs", "cvt"] = Field(default="cvt")
    acquisition_function: str = Field(default="NoisyEHVI")
    acquisition_function_sampler: str = Field(default="SobolQMCNormalSampler")
    objectives: List[Objective]
    candidates: List[Dict[str, Any]]
    include_predictions: bool = Field(default=True)
    id_column: str = Field(default="candidate_id")


class TaskStatus(str, Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class TaskSubmissionData(BaseModel):
    task_id: str
    status: TaskStatus
    status_url: str
    result_url: str


class TaskStatusData(BaseModel):
    task_id: str
    status: TaskStatus
    progress: Optional[float] = None
    result_url: Optional[str] = None


class ErrorData(BaseModel):
    task_id: Optional[str] = None
    status: Optional[TaskStatus] = None


T = TypeVar("T")


class ApiResponse(BaseModel, Generic[T]):
    code: int
    message: str
    data: Optional[T] = None
