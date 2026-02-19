from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from data_processing.meta import META_RECREATE
from data_processing.utils import CONVERT_TO_CSV
from main_handler import Handler


@pytest.mark.xfail(
    reason=(
        "Checkpoint 4 guardrail: unknown tasks should be ignored "
        "as full no-op. "
        "Current main_handler routing is hardcoded and still triggers "
        "meta rebuild in convert_to_csv. Future task-id/API mapping "
        "changes should preserve canonical task behavior while unknown "
        "labels remain ignored."
    ),
    strict=False,
)
def test_unknown_task_is_full_noop_expected_contract(
    tmp_path: Path,
    monkeypatch,
) -> None:
    data_root = tmp_path / "data"
    meta_root = tmp_path / "meta"
    data_root.mkdir(parents=True, exist_ok=True)
    meta_root.mkdir(parents=True, exist_ok=True)

    af_like_df = pd.DataFrame(
        [
            {
                "subject_id": "9001",
                "task": "AF",
                "session": 1,
                "session_number": 1,
                "block": "test",
                "condition": "congruent",
                "response_time": 500,
                "correct": 1,
            }
        ]
    )

    def patched_convert_to_csv(self, txt_dfs):
        return [af_like_df.copy()]

    monkeypatch.setattr(
        CONVERT_TO_CSV,
        "convert_to_csv",
        patched_convert_to_csv,
    )

    handler = Handler()
    handler._meta_recreator = META_RECREATE(
        data_root=data_root,
        meta_root=meta_root,
    )

    dummy_txt_frames = [pd.DataFrame([{"file_content": "[]"}])]
    csv_dfs, result = handler.convert_to_csv(dummy_txt_frames, "AF_V2_UNKNOWN")

    assert len(csv_dfs) == 1
    assert result is None
    assert not any(data_root.rglob("*"))
    assert not any(meta_root.rglob("*"))
