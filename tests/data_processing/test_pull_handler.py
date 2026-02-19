from __future__ import annotations

import pytest

from data_processing.pull_handler import Pull


def test_pull_accepts_single_task_id() -> None:
    pull = Pull([945], "tease", "token", "AF")
    assert pull.IDs == [945]


def test_pull_accepts_six_task_ids() -> None:
    task_ids = [945, 960, 990, 898, 919, 932]
    pull = Pull(task_ids, "tease", "token", "AF")
    assert pull.IDs == task_ids


def test_pull_rejects_empty_task_ids() -> None:
    with pytest.raises(ValueError, match="at least 1"):
        Pull([], "tease", "token", "AF")


def test_pull_rejects_more_than_six_task_ids() -> None:
    with pytest.raises(ValueError, match="at most 6"):
        Pull([1, 2, 3, 4, 5, 6, 7], "tease", "token", "AF")
