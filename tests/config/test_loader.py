from __future__ import annotations

from pathlib import Path

import pytest

from config.pipeline_config import load_pipeline_config


def test_loader_reads_default_pipeline_toml(repo_root: Path) -> None:
    config = load_pipeline_config()
    expected_path = (repo_root / "config" / "pipeline.toml").resolve()

    assert config.config_path == expected_path
    assert config.schema_version == 1
    assert "AF" in config.pipeline.tasks


def test_loader_fails_fast_when_config_missing(tmp_path: Path) -> None:
    missing_path = tmp_path / "config" / "pipeline.toml"

    with pytest.raises(FileNotFoundError, match="Missing pipeline config"):
        load_pipeline_config(missing_path)

