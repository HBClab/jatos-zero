from __future__ import annotations

from typing import Final

import pandas as pd
from pandas.testing import assert_frame_equal


CSV_FLOAT_RTOL: Final[float] = 1e-6
CSV_FLOAT_ATOL: Final[float] = 1e-8


def _stable_row_sort(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty or not list(df.columns):
        return df.reset_index(drop=True)

    key_columns = []
    for column in df.columns:
        series = df[column]
        key = series.map(lambda value: "<NA>" if pd.isna(value) else str(value))
        key_columns.append(key.rename(f"__key_{column}"))

    key_df = pd.concat(key_columns, axis=1)
    ordered_index = key_df.sort_values(
        by=list(key_df.columns),
        kind="mergesort",
        na_position="last",
    ).index
    return df.loc[ordered_index].reset_index(drop=True)


def normalize_for_semantic_compare(df: pd.DataFrame) -> pd.DataFrame:
    normalized = df.copy()
    normalized = normalized.reindex(sorted(normalized.columns), axis=1)
    normalized = _stable_row_sort(normalized)
    return normalized


def _normalize_column_pair(left_col: pd.Series, right_col: pd.Series) -> tuple[pd.Series, pd.Series]:
    left_num = pd.to_numeric(left_col, errors="coerce")
    right_num = pd.to_numeric(right_col, errors="coerce")

    left_non_null = left_col.notna()
    right_non_null = right_col.notna()
    left_is_numeric_like = left_num[left_non_null].notna().all()
    right_is_numeric_like = right_num[right_non_null].notna().all()

    if left_is_numeric_like and right_is_numeric_like:
        return left_num, right_num

    def _to_text(value):
        if pd.isna(value):
            return "<NA>"
        return str(value)

    return left_col.map(_to_text), right_col.map(_to_text)


def semantic_csv_equal(
    left: pd.DataFrame,
    right: pd.DataFrame,
    *,
    float_rtol: float = CSV_FLOAT_RTOL,
    float_atol: float = CSV_FLOAT_ATOL,
) -> bool:
    left_normalized = normalize_for_semantic_compare(left)
    right_normalized = normalize_for_semantic_compare(right)
    common_columns = sorted(set(left_normalized.columns) & set(right_normalized.columns))

    for column in common_columns:
        normalized_left_col, normalized_right_col = _normalize_column_pair(
            left_normalized[column],
            right_normalized[column],
        )
        left_normalized[column] = normalized_left_col
        right_normalized[column] = normalized_right_col

    try:
        assert_frame_equal(
            left_normalized,
            right_normalized,
            check_dtype=False,
            check_exact=False,
            rtol=float_rtol,
            atol=float_atol,
        )
    except AssertionError:
        return False
    return True
