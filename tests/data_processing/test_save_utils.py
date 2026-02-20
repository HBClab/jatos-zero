from __future__ import annotations

from pathlib import Path

import pandas as pd

from data_processing.save_utils import SAVE_EVERYTHING


def test_save_dfs_writes_to_canonical_subject_session_task_layout(
    tmp_path: Path,
) -> None:
    saver = SAVE_EVERYTHING()
    saver.datadir = str(tmp_path)

    df = pd.DataFrame(
        [
            {
                "subject_id": "9001",
                "session_number": 1,
                "correct": 1,
            }
        ]
    )
    saver.save_dfs(categories=[("9001", 1, df)], task="AF")

    data_dir = tmp_path / "9001" / "1" / "AF" / "data"
    files = sorted(data_dir.glob("*.csv"))
    assert len(files) == 1
    assert files[0].name == "9001_ses-1_cat-1.csv"


def test_save_dfs_skips_malformed_subject_or_session_without_raising(
    tmp_path: Path,
) -> None:
    saver = SAVE_EVERYTHING()
    saver.datadir = str(tmp_path)

    missing_session_df = pd.DataFrame([{"subject_id": "9001", "correct": 1}])
    saver.save_dfs(categories=[("9001", 1, missing_session_df)], task="AF")

    assert not any(tmp_path.rglob("*.csv"))
