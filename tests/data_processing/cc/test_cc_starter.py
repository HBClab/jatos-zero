from __future__ import annotations

from tests.data_processing.helpers.assertions import assert_task_values
from tests.data_processing.helpers.fixture_factories import build_trial_frame


def test_cc_starter_uses_shared_helpers() -> None:
    rows = [
        {
            "condition": "congruent",
            "response_time": 500,
            "correct": 1,
            "block": "test",
        },
        {
            "condition": "incongruent",
            "response_time": 710,
            "correct": 0,
            "block": "test",
        },
    ]

    frame = build_trial_frame(rows, task="AF")
    assert_task_values(frame, "AF")
    assert set(frame["condition"].tolist()) == {"congruent", "incongruent"}
