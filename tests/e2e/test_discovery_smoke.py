from pathlib import Path


def test_pytest_discovery_smoke(temp_artifact_root: Path) -> None:
    assert temp_artifact_root.exists()
    assert temp_artifact_root.is_dir()