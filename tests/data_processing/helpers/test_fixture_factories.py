from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from tests.data_processing.helpers.assertions import (
    assert_required_columns,
    assert_task_values,
    normalize_frame,
    normalize_scalar,
)
from tests.data_processing.helpers.fixture_factories import (
    build_trial_frame,
    fixture_path,
    load_dataframe_fixture,
)


def test_load_af_fixture_dataframe() -> None:
    fixture = fixture_path("af_known_task", "af_minimal_trials.csv")
    assert fixture.exists()

    df = load_dataframe_fixture("af_known_task", "af_minimal_trials.csv")
    assert not df.empty
    assert_required_columns(
        df,
        [
            "subject_id",
            "task",
            "session",
            "condition",
            "response_time",
            "correct",
        ],
    )
    assert_task_values(df, "AF")


def test_build_trial_frame_applies_defaults() -> None:
    rows = [
        {"condition": "congruent", "response_time": 550, "correct": 1},
        {"condition": "incongruent", "response_time": 720, "correct": 0},
    ]

    df = build_trial_frame(rows, task="AF")
    assert len(df) == 2
    assert set(df["task"].unique()) == {"AF"}
    assert set(df["subject_id"].astype(str).unique()) == {"9001"}


def test_normalize_scalar_with_numpy_value() -> None:
    assert normalize_scalar(np.int64(3)) == 3


def test_normalize_frame_and_required_columns() -> None:
    raw = pd.DataFrame(
        [
            {" Condition ": "incongruent", "response_time": 720, "task": "AF"},
            {" Condition ": "congruent", "response_time": 550, "task": "AF"},
        ]
    )

    normalized = normalize_frame(raw, sort_by=["response_time"])
    assert list(normalized.columns) == ["condition", "response_time", "task"]
    assert normalized.iloc[0]["response_time"] == 550


def test_required_columns_raises_for_missing() -> None:
    df = pd.DataFrame([{"task": "AF"}])

    with pytest.raises(AssertionError, match="Missing required columns"):
        assert_required_columns(df, ["task", "response_time"])
