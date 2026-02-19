from __future__ import annotations

import main_handler


def test_main_defaults_to_all_when_no_task_argument(monkeypatch) -> None:
    seen: list[str] = []

    class FakeHandler:
        def run(self, task: str):
            seen.append(task)

    monkeypatch.setattr(main_handler, "Handler", FakeHandler)

    exit_code = main_handler.main(["beh/main_handler.py"])

    assert exit_code == 0
    assert seen == ["all"]


def test_main_uses_explicit_task_argument(monkeypatch) -> None:
    seen: list[str] = []

    class FakeHandler:
        def run(self, task: str):
            seen.append(task)

    monkeypatch.setattr(main_handler, "Handler", FakeHandler)

    exit_code = main_handler.main(["beh/main_handler.py", "AF"])

    assert exit_code == 0
    assert seen == ["AF"]
