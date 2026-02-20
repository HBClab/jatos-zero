from __future__ import annotations

from pathlib import Path

import pytest

from config.output_paths import resolve_data_save_root
from config.pipeline_config import PipelineConfigValidationError, load_pipeline_config


def _write_config(tmp_path: Path, content: str) -> Path:
    config_path = tmp_path / "config" / "pipeline.toml"
    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text(content, encoding="utf-8")
    return config_path


def test_resolver_composes_root_and_folder() -> None:
    resolved = resolve_data_save_root(
        data_root_path="/tmp/runtime-root",
        data_folder_name="saved-data",
    )
    assert resolved == Path("/tmp/runtime-root/saved-data").resolve()


def test_resolver_rejects_empty_values() -> None:
    with pytest.raises(ValueError, match="data_root_path"):
        resolve_data_save_root(
            data_root_path="",
            data_folder_name="saved-data",
        )
    with pytest.raises(ValueError, match="data_folder_name"):
        resolve_data_save_root(
            data_root_path=".",
            data_folder_name=" ",
        )


def test_config_validation_rejects_blank_output_folder_name(tmp_path: Path) -> None:
    config_path = _write_config(
        tmp_path,
        """
schema_version = 1

[pipeline]
enable_plots = false

[pipeline.outputs]
data_folder_name = "   "

[pipeline.tasks.AF]
domain = "cc"
task_ids = [945]
""".strip(),
    )

    with pytest.raises(
        PipelineConfigValidationError,
        match=r"pipeline\.outputs\.data_folder_name",
    ):
        load_pipeline_config(config_path, known_tasks={"AF"})
