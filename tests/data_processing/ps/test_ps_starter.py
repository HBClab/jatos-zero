from __future__ import annotations

from tests.data_processing.helpers.assertions import normalize_frame
from tests.data_processing.helpers.fixture_factories import build_trial_frame


def test_ps_starter_uses_shared_helpers() -> None:
    rows = [
        {"block_c": 1, "correct": 1, "response_time": 300},
        {"block_c": 2, "correct": 1, "response_time": 325},
    ]

    frame = build_trial_frame(rows, task="PC")
    normalized = normalize_frame(frame, sort_by=["response_time"])
    assert list(normalized["response_time"]) == [300, 325]
    assert normalized["task"].eq("PC").all()
