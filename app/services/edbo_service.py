from __future__ import annotations

import math
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

import pandas as pd

from app.schemas.edbo import EdboTaskRequest
from edbo.plus.optimizer_botorch import EDBOplus


INPUT_FILENAME = "input.csv"


def run_edbo_recommendation(request: EdboTaskRequest, workdir: Path, task_id: str) -> Dict[str, Any]:
    workdir.mkdir(parents=True, exist_ok=True)
    input_path = workdir / INPUT_FILENAME

    objective_names = [objective.name for objective in request.objectives]
    objective_modes = [objective.mode for objective in request.objectives]

    df_input = _request_to_dataframe(request, objective_names)
    df_input.to_csv(input_path, index=False)

    optimizer = EDBOplus()
    columns_features = _resolve_feature_columns(request, df_input.columns, objective_names)
    result_df = optimizer.run(
        directory=str(workdir),
        filename=INPUT_FILENAME,
        objectives=objective_names,
        objective_mode=objective_modes,
        columns_features=columns_features,
        batch=request.batch,
        init_sampling_method=request.init_sampling_method,
        seed=request.seed,
        acquisition_function=request.acquisition_function,
        acquisition_function_sampler=request.acquisition_function_sampler,
    )

    prediction_df = _read_predictions(workdir, request.include_predictions)
    source_df = prediction_df if prediction_df is not None else result_df

    return {
        "task_id": request.task_id or task_id,
        "status": "completed",
        "batch": request.batch,
        "recommended_count": _count_recommendations(result_df),
        "recommendations": _build_recommendations(
            source_df=source_df,
            request=request,
            objective_names=objective_names,
            include_predictions=prediction_df is not None and request.include_predictions,
        ),
        "artifacts": {
            "input_csv": INPUT_FILENAME,
            "result_csv": INPUT_FILENAME,
            "prediction_csv": f"pred_{INPUT_FILENAME}" if prediction_df is not None else None,
        },
    }


def _request_to_dataframe(request: EdboTaskRequest, objective_names: List[str]) -> pd.DataFrame:
    if not request.candidates:
        raise ValueError("candidates must contain at least one row")
    if not request.objectives:
        raise ValueError("objectives must contain at least one item")

    df = pd.DataFrame(request.candidates)
    missing_objectives = [name for name in objective_names if name not in df.columns]
    for name in missing_objectives:
        df[name] = None

    if _all_objectives_are_empty(df, objective_names):
        return df.drop(columns=objective_names, errors="ignore")

    for name in objective_names:
        df[name] = df[name].map(_objective_value_to_csv)

    return df


def _all_objectives_are_empty(df: pd.DataFrame, objective_names: Iterable[str]) -> bool:
    for name in objective_names:
        if name not in df.columns:
            continue
        values = df[name]
        has_observed = values.map(lambda value: not _is_pending_value(value)).any()
        if has_observed:
            return False
    return True


def _objective_value_to_csv(value: Any) -> Any:
    if _is_pending_value(value):
        return "PENDING"
    return value


def _is_pending_value(value: Any) -> bool:
    if value is None:
        return True
    if isinstance(value, float) and math.isnan(value):
        return True
    if isinstance(value, str) and value.strip().upper() in {"", "PENDING", "NULL", "NONE"}:
        return True
    return False


def _resolve_feature_columns(
    request: EdboTaskRequest,
    dataframe_columns: Iterable[str],
    objective_names: List[str],
) -> Any:
    excluded = set(objective_names)
    excluded.add("priority")
    if request.id_column:
        excluded.add(request.id_column)

    if request.columns_features == "all":
        return [column for column in dataframe_columns if column not in excluded]

    if isinstance(request.columns_features, list):
        return [column for column in request.columns_features if column not in excluded]

    return request.columns_features


def _read_predictions(workdir: Path, include_predictions: bool) -> Optional[pd.DataFrame]:
    if not include_predictions:
        return None
    prediction_path = workdir / f"pred_{INPUT_FILENAME}"
    if not prediction_path.exists():
        return None
    return pd.read_csv(prediction_path)


def _count_recommendations(df: pd.DataFrame) -> int:
    if "priority" not in df.columns:
        return 0
    return int((pd.to_numeric(df["priority"], errors="coerce").fillna(0) == 1).sum())


def _build_recommendations(
    source_df: pd.DataFrame,
    request: EdboTaskRequest,
    objective_names: List[str],
    include_predictions: bool,
) -> List[Dict[str, Any]]:
    if "priority" not in source_df.columns:
        return []

    df = source_df.copy()
    df["_priority_numeric"] = pd.to_numeric(df["priority"], errors="coerce").fillna(0)
    recommendations_df = df[df["_priority_numeric"] == 1].copy()
    recommendations_df = recommendations_df.sort_values("_priority_numeric", ascending=False)

    prediction_columns = _prediction_columns(objective_names)
    excluded_conditions = set(objective_names) | {"priority", "_priority_numeric"} | prediction_columns
    if request.id_column:
        excluded_conditions.add(request.id_column)

    recommendations: List[Dict[str, Any]] = []
    for rank, (_, row) in enumerate(recommendations_df.iterrows(), start=1):
        candidate_id = _clean_json_value(row.get(request.id_column)) if request.id_column in row else None
        payload: Dict[str, Any] = {
            "rank": rank,
            "candidate_id": candidate_id,
            "priority": _clean_json_value(row.get("priority")),
            "conditions": {
                column: _clean_json_value(row[column])
                for column in source_df.columns
                if column not in excluded_conditions
            },
        }

        if include_predictions:
            payload["predictions"] = _extract_predictions(row, objective_names)

        recommendations.append(payload)

    return recommendations


def _prediction_columns(objective_names: Iterable[str]) -> set[str]:
    columns: set[str] = set()
    for name in objective_names:
        columns.update(
            {
                f"{name}_predicted_mean",
                f"{name}_predicted_std_dev",
                f"{name}_expected_improvement",
            }
        )
    return columns


def _extract_predictions(row: pd.Series, objective_names: Iterable[str]) -> Dict[str, Dict[str, Any]]:
    predictions: Dict[str, Dict[str, Any]] = {}
    for name in objective_names:
        objective_predictions = {
            "predicted_mean": _clean_json_value(row.get(f"{name}_predicted_mean")),
            "predicted_std_dev": _clean_json_value(row.get(f"{name}_predicted_std_dev")),
            "expected_improvement": _clean_json_value(row.get(f"{name}_expected_improvement")),
        }
        if any(value is not None for value in objective_predictions.values()):
            predictions[name] = objective_predictions
    return predictions


def _clean_json_value(value: Any) -> Any:
    if pd.isna(value):
        return None
    if hasattr(value, "item"):
        return value.item()
    return value
