from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from data_processing.meta import META_RECREATE
from data_processing.utils import CONVERT_TO_CSV
from main_handler import Handler


def test_unknown_task_raises_before_side_effects(
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

    converter_called = {"called": False}
    meta_called = {"called": False}

    def patched_convert_to_csv(self, txt_dfs):
        converter_called["called"] = True
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
    monkeypatch.setattr(
        handler,
        "_run_meta_if_needed",
        lambda force=False: meta_called.__setitem__("called", True),
    )

    dummy_txt_frames = [pd.DataFrame([{"file_content": "[]"}])]
    with pytest.raises(ValueError, match="Unknown task 'AF_V2_UNKNOWN'"):
        handler.convert_to_csv(dummy_txt_frames, "AF_V2_UNKNOWN")

    assert converter_called["called"] is False
    assert meta_called["called"] is False
    assert not any(data_root.rglob("*"))
    assert not any(meta_root.rglob("*"))
