from __future__ import annotations

from main_handler import Handler


def test_baseline_toml_preserves_all_known_tasks_execution_order(monkeypatch) -> None:
    handler = Handler()
    seen_tasks: list[str] = []
    monkeypatch.setattr(handler, "pull", lambda task: seen_tasks.append(task))

    handler.run("all")

    assert handler.configured_tasks() == handler.task_order
    assert seen_tasks == handler.task_order
