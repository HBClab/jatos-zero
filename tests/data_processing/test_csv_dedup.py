from __future__ import annotations

import time
from pathlib import Path

import pandas as pd

from data_processing.save_utils import SAVE_EVERYTHING


def _artifact_path(root: Path) -> Path:
    return root / "9001" / "1" / "AF" / "data" / "9001_ses-1_cat-1.csv"


def test_csv_save_skips_when_semantically_equivalent(tmp_path: Path) -> None:
    saver = SAVE_EVERYTHING()
    saver.datadir = str(tmp_path)

    df_first = pd.DataFrame(
        [
            {"subject_id": "9001", "session_number": 1, "trial": 2, "score": 0.5},
            {"subject_id": "9001", "session_number": 1, "trial": 1, "score": 0.7},
        ]
    )
    # Row order changed, content equivalent.
    df_second = pd.DataFrame(
        [
            {"subject_id": "9001", "session_number": 1, "trial": 1, "score": 0.7},
            {"subject_id": "9001", "session_number": 1, "trial": 2, "score": 0.5},
        ]
    )

    saver.save_dfs(categories=[("9001", 1, df_first)], task="AF")
    csv_path = _artifact_path(tmp_path)
    first_mtime = csv_path.stat().st_mtime_ns

    time.sleep(0.01)
    saver.save_dfs(categories=[("9001", 1, df_second)], task="AF")
    second_mtime = csv_path.stat().st_mtime_ns

    assert second_mtime == first_mtime


def test_csv_save_rewrites_when_content_changes(tmp_path: Path) -> None:
    saver = SAVE_EVERYTHING()
    saver.datadir = str(tmp_path)

    df_first = pd.DataFrame(
        [{"subject_id": "9001", "session_number": 1, "trial": 1, "score": 0.5}]
    )
    df_changed = pd.DataFrame(
        [{"subject_id": "9001", "session_number": 1, "trial": 1, "score": 0.9}]
    )

    saver.save_dfs(categories=[("9001", 1, df_first)], task="AF")
    csv_path = _artifact_path(tmp_path)
    first_mtime = csv_path.stat().st_mtime_ns

    time.sleep(0.01)
    saver.save_dfs(categories=[("9001", 1, df_changed)], task="AF")
    second_mtime = csv_path.stat().st_mtime_ns

    assert second_mtime > first_mtime
    reloaded = pd.read_csv(csv_path)
    assert float(reloaded["score"].iloc[0]) == 0.9


def test_csv_save_treats_minor_float_jitter_as_unchanged(tmp_path: Path) -> None:
    saver = SAVE_EVERYTHING()
    saver.datadir = str(tmp_path)

    df_first = pd.DataFrame(
        [{"subject_id": "9001", "session_number": 1, "trial": 1, "score": 1.000000001}]
    )
    df_jitter = pd.DataFrame(
        [{"subject_id": "9001", "session_number": 1, "trial": 1, "score": 1.0000000015}]
    )

    saver.save_dfs(categories=[("9001", 1, df_first)], task="AF")
    csv_path = _artifact_path(tmp_path)
    first_mtime = csv_path.stat().st_mtime_ns

    time.sleep(0.01)
    saver.save_dfs(categories=[("9001", 1, df_jitter)], task="AF")
    second_mtime = csv_path.stat().st_mtime_ns

    assert second_mtime == first_mtime
