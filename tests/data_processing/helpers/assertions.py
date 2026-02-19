from __future__ import annotations

from typing import Any, Iterable

import pandas as pd


def normalize_scalar(value: Any) -> Any:
    if hasattr(value, "item"):
        try:
            return value.item()
        except Exception:
            return value
    return value


def assert_required_columns(
    df: pd.DataFrame,
    required_columns: Iterable[str],
) -> None:
    missing = [
        column for column in required_columns if column not in df.columns
    ]
    if missing:
        raise AssertionError(f"Missing required columns: {missing}")


def assert_task_values(df: pd.DataFrame, expected_task: str) -> None:
    assert_required_columns(df, ["task"])
    actual_tasks = set(df["task"].astype(str).unique().tolist())
    if actual_tasks != {expected_task}:
        raise AssertionError(
            f"Expected task set {{{expected_task}}}, got {actual_tasks}"
        )


def normalize_frame(
    df: pd.DataFrame,
    *,
    sort_by: list[str] | None = None,
) -> pd.DataFrame:
    normalized = df.copy()
    normalized.columns = [
        str(column).strip().lower() for column in normalized.columns
    ]

    if sort_by:
        normalized = normalized.sort_values(sort_by).reset_index(drop=True)

    return normalized
