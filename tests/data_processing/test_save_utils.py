from __future__ import annotations

import json
from pathlib import Path

import matplotlib.pyplot as plt
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


def test_save_dfs_persists_missing_session_with_placeholder_assignment(
    tmp_path: Path,
) -> None:
    saver = SAVE_EVERYTHING()
    saver.datadir = str(tmp_path)

    missing_session_df = pd.DataFrame([{"subject_id": "9001", "correct": 1}])
    saver.save_dfs(categories=[("9001", 1, missing_session_df)], task="AF")

    data_dir = tmp_path / "9001" / "1" / "AF" / "data"
    files = sorted(data_dir.glob("*.csv"))
    assert len(files) == 1
    assert files[0].name == "9001_ses-1_cat-1.csv"


def test_save_plots_uses_placeholder_session_assigned_during_csv_save(
    tmp_path: Path,
) -> None:
    saver = SAVE_EVERYTHING()
    saver.datadir = str(tmp_path)

    missing_session_df = pd.DataFrame([{"subject_id": "9001", "correct": 1}])
    saver.save_dfs(categories=[("9001", 1, missing_session_df)], task="AF")

    fig, ax = plt.subplots()
    ax.plot([1, 2], [3, 4])

    saver.save_plots(plots=[("9001", ax)], task="AF")

    plot_dir = tmp_path / "9001" / "1" / "AF" / "plot"
    files = sorted(plot_dir.glob("*.png"))
    assert len(files) == 1
    assert files[0].name == "9001_ses-1.png"


def test_save_dfs_warns_and_writes_missing_session_report(
    tmp_path: Path,
    monkeypatch,
) -> None:
    saver = SAVE_EVERYTHING()
    saver.datadir = str(tmp_path)

    logs: list[tuple[str, str]] = []
    monkeypatch.setattr(
        "data_processing.save_utils.cprint",
        lambda message, color: logs.append((message, color)),
    )

    missing_session_df = pd.DataFrame([{"subject_id": "9001", "correct": 1}])
    saver.save_dfs(categories=[("9001", 1, missing_session_df)], task="AF")

    warning_logs = [message for message, color in logs if color == "yellow"]
    assert any("task=AF" in message for message in warning_logs)
    assert any("subject=9001" in message for message in warning_logs)
    assert any("placeholder session 1" in message for message in warning_logs)
    assert any("Human review and adjustment required." in message for message in warning_logs)

    report_files = sorted((tmp_path / "_reports").glob("missing_session_assignments_*.json"))
    assert len(report_files) == 1

    payload = json.loads(report_files[0].read_text(encoding="utf-8"))
    assert payload["run_started_at"]
    assert payload["generated_at"]
    assert len(payload["events"]) == 1
    assert payload["events"][0]["task"] == "AF"
    assert payload["events"][0]["subject_id"] == "9001"
    assert payload["events"][0]["assigned_session"] == "1"
    assert payload["events"][0]["reason"] == "missing session value at save boundary"
    assert payload["events"][0]["run_started_at"] == payload["run_started_at"]
    assert payload["events"][0]["assigned_at"]


def test_missing_session_report_write_failure_is_non_fatal(
    tmp_path: Path,
    monkeypatch,
) -> None:
    saver = SAVE_EVERYTHING()
    saver.datadir = str(tmp_path)

    logs: list[tuple[str, str]] = []
    monkeypatch.setattr(
        "data_processing.save_utils.cprint",
        lambda message, color: logs.append((message, color)),
    )

    original_atomic_write_text = SAVE_EVERYTHING._atomic_write_text

    def failing_atomic_write_text(content: str, target_path: Path) -> None:
        if target_path.name.startswith("missing_session_assignments_"):
            raise OSError("disk full")
        original_atomic_write_text(content, target_path)

    monkeypatch.setattr(
        SAVE_EVERYTHING,
        "_atomic_write_text",
        staticmethod(failing_atomic_write_text),
    )

    missing_session_df = pd.DataFrame([{"subject_id": "9001", "correct": 1}])
    saver.save_dfs(categories=[("9001", 1, missing_session_df)], task="AF")

    data_files = sorted((tmp_path / "9001" / "1" / "AF" / "data").glob("*.csv"))
    assert len(data_files) == 1
    warning_logs = [message for message, color in logs if color == "yellow"]
    assert any("report write failed" in message for message in warning_logs)


def test_save_dfs_still_skips_invalid_subject_without_raising(
    tmp_path: Path,
) -> None:
    saver = SAVE_EVERYTHING()
    saver.datadir = str(tmp_path)

    df = pd.DataFrame([{"session_number": 1, "correct": 1}])
    saver.save_dfs(categories=[(None, 1, df)], task="AF")

    assert not any(tmp_path.rglob("*.csv"))


def test_prime_session_allocator_collects_in_memory_and_disk_sessions(
    tmp_path: Path,
) -> None:
    saver = SAVE_EVERYTHING()
    saver.datadir = str(tmp_path)

    existing_dir = tmp_path / "9001" / "4" / "AF" / "data"
    existing_dir.mkdir(parents=True)

    categories = [
        ("9001", 1, pd.DataFrame([{"subject_id": "9001", "session_number": 2}])),
        ("9001", 2, pd.DataFrame([{"subject_id": "9001", "session_number": 3}])),
    ]

    saver.prime_session_allocator(categories, task="AF")

    assert saver._session_allocator_state[("9001", "AF")] == {2, 3, 4}


def test_resolve_session_for_save_allocates_from_empty_state_starting_at_one(
    tmp_path: Path,
) -> None:
    saver = SAVE_EVERYTHING()
    saver.datadir = str(tmp_path)

    resolution = saver.resolve_session_for_save(
        "9001",
        pd.DataFrame([{"subject_id": "9001", "correct": 1}]),
        task="AF",
    )

    assert resolution.session == "1"
    assert resolution.used_placeholder is True


def test_resolve_session_for_save_allocates_max_plus_one_after_priming(
    tmp_path: Path,
) -> None:
    saver = SAVE_EVERYTHING()
    saver.datadir = str(tmp_path)

    existing_dir = tmp_path / "9001" / "5" / "AF" / "data"
    existing_dir.mkdir(parents=True)
    categories = [
        ("9001", 1, pd.DataFrame([{"subject_id": "9001", "session_number": 2}])),
    ]
    saver.prime_session_allocator(categories, task="AF")

    resolution = saver.resolve_session_for_save(
        "9001",
        pd.DataFrame([{"subject_id": "9001", "correct": 1}]),
        task="AF",
    )

    assert resolution.session == "6"
    assert resolution.used_placeholder is True


def test_resolve_session_for_save_allocates_distinct_placeholders_within_run(
    tmp_path: Path,
) -> None:
    saver = SAVE_EVERYTHING()
    saver.datadir = str(tmp_path)

    categories = [
        ("9001", 1, pd.DataFrame([{"subject_id": "9001", "session_number": 2}])),
        ("9001", 2, pd.DataFrame([{"subject_id": "9001", "correct": 1}])),
        ("9001", 3, pd.DataFrame([{"subject_id": "9001", "correct": 1}])),
    ]
    saver.prime_session_allocator(categories, task="AF")

    first = saver.resolve_session_for_save(
        "9001",
        pd.DataFrame([{"subject_id": "9001", "correct": 1}]),
        task="AF",
    )
    second = saver.resolve_session_for_save(
        "9001",
        pd.DataFrame([{"subject_id": "9001", "correct": 1}]),
        task="AF",
    )

    assert first.session == "3"
    assert second.session == "4"
    assert first.used_placeholder is True
    assert second.used_placeholder is True
