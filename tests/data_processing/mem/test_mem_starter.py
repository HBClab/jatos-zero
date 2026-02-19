from __future__ import annotations

from tests.data_processing.helpers.assertions import assert_required_columns
from tests.data_processing.helpers.fixture_factories import build_trial_frame


def test_mem_starter_uses_shared_helpers() -> None:
    rows = [
        {"block_c": 1, "response_time": 900, "correct": 1, "block": "test"},
        {"block_c": 2, "response_time": 1100, "correct": 0, "block": "test"},
    ]

    frame = build_trial_frame(rows, task="FN")
    assert_required_columns(
        frame,
        ["task", "subject_id", "session", "block_c", "correct"],
    )
    assert frame["task"].eq("FN").all()
