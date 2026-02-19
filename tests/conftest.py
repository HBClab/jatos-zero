from __future__ import annotations

import sys
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[1]
BEH_PATH = REPO_ROOT / "beh"
if str(BEH_PATH) not in sys.path:
    sys.path.insert(0, str(BEH_PATH))


@pytest.fixture(scope="session")
def repo_root() -> Path:
    return REPO_ROOT


@pytest.fixture(scope="session", autouse=True)
def add_code_to_path(repo_root: Path) -> None:
    code_path = repo_root / "beh"
    if str(code_path) not in sys.path:
        sys.path.insert(0, str(code_path))


@pytest.fixture
def temp_artifact_root(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> Path:
    artifact_root = tmp_path / "artifacts"
    artifact_root.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv(
        "BOOST_TEST_ARTIFACT_ROOT",
        str(artifact_root),
    )
    return artifact_root
