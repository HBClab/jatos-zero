from __future__ import annotations

from tests.data_processing.helpers.assertions import assert_required_columns
from tests.data_processing.helpers.fixture_factories import build_trial_frame


def test_wl_starter_uses_shared_helpers() -> None:
    rows = [
        {
            "block_c": "learn_1",
            "correct": 1,
            "response": "apple",
            "block": "test",
        },
        {
            "block_c": "learn_2",
            "correct": 0,
            "response": "pear",
            "block": "test",
        },
    ]

    frame = build_trial_frame(rows, task="WL")
    assert_required_columns(frame, ["task", "block_c", "response", "correct"])
    assert frame["task"].eq("WL").all()
