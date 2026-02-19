from __future__ import annotations

from pathlib import Path

import pytest

from config.pipeline_config import (
    PipelineConfigValidationError,
    load_pipeline_config,
)


def _write_config(tmp_path: Path, content: str) -> Path:
    config_path = tmp_path / "config" / "pipeline.toml"
    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text(content, encoding="utf-8")
    return config_path


def test_validation_fails_when_schema_version_missing(tmp_path: Path) -> None:
    config_path = _write_config(
        tmp_path,
        """
[pipeline]
enable_plots = false

[pipeline.tasks.AF]
domain = "cc"
task_ids = [945]
""".strip(),
    )

    with pytest.raises(
        PipelineConfigValidationError,
        match=r"root\.schema_version",
    ):
        load_pipeline_config(config_path, known_tasks={"AF"})


def test_validation_fails_for_bad_schema_version_type(tmp_path: Path) -> None:
    config_path = _write_config(
        tmp_path,
        """
schema_version = "1"

[pipeline]
enable_plots = false

[pipeline.tasks.AF]
domain = "cc"
task_ids = [945]
""".strip(),
    )

    with pytest.raises(
        PipelineConfigValidationError,
        match=r"schema_version.*integer",
    ):
        load_pipeline_config(config_path, known_tasks={"AF"})


def test_validation_fails_for_unknown_nested_key(tmp_path: Path) -> None:
    config_path = _write_config(
        tmp_path,
        """
schema_version = 1

[pipeline]
enable_plots = false

[pipeline.defaults.columns]
subject = "subject_id"
session = "session_number"
mystery = "unexpected"

[pipeline.tasks.AF]
domain = "cc"
task_ids = [945]
""".strip(),
    )

    with pytest.raises(
        PipelineConfigValidationError,
        match=r"pipeline\.defaults\.columns\.mystery",
    ):
        load_pipeline_config(config_path, known_tasks={"AF"})


def test_validation_rejects_invalid_domain(tmp_path: Path) -> None:
    config_path = _write_config(
        tmp_path,
        """
schema_version = 1

[pipeline]
enable_plots = false

[pipeline.tasks.AF]
domain = "cognitive"
task_ids = [945]
""".strip(),
    )

    with pytest.raises(
        PipelineConfigValidationError,
        match=r"pipeline\.tasks\.AF\.domain",
    ):
        load_pipeline_config(config_path, known_tasks={"AF"})


def test_validation_rejects_missing_task_domain_key(tmp_path: Path) -> None:
    config_path = _write_config(
        tmp_path,
        """
schema_version = 1

[pipeline]
enable_plots = false

[pipeline.tasks.AF]
task_ids = [945]
[pipeline.tasks.AF.qc]
threshold = 0.5
""".strip(),
    )

    with pytest.raises(
        PipelineConfigValidationError,
        match=r"pipeline\.tasks\.AF\.domain",
    ):
        load_pipeline_config(config_path, known_tasks={"AF"})


def test_validation_rejects_missing_task_ids_key(tmp_path: Path) -> None:
    config_path = _write_config(
        tmp_path,
        """
schema_version = 1

[pipeline]
enable_plots = false

[pipeline.tasks.AF]
domain = "cc"
""".strip(),
    )

    with pytest.raises(
        PipelineConfigValidationError,
        match=r"pipeline\.tasks\.AF\.task_ids",
    ):
        load_pipeline_config(config_path, known_tasks={"AF"})


def test_validation_rejects_unknown_configured_task(tmp_path: Path) -> None:
    config_path = _write_config(
        tmp_path,
        """
schema_version = 1

[pipeline]
enable_plots = false

[pipeline.tasks.AF]
domain = "cc"
task_ids = [945]

[pipeline.tasks.UNKNOWN_TASK]
domain = "cc"
task_ids = [123]
""".strip(),
    )

    with pytest.raises(
        PipelineConfigValidationError,
        match=r"pipeline\.tasks\.UNKNOWN_TASK",
    ):
        load_pipeline_config(config_path, known_tasks={"AF"})


def test_validation_rejects_more_than_six_task_ids(tmp_path: Path) -> None:
    config_path = _write_config(
        tmp_path,
        """
schema_version = 1

[pipeline]
enable_plots = false

[pipeline.tasks.AF]
domain = "cc"
task_ids = [1, 2, 3, 4, 5, 6, 7]
""".strip(),
    )

    with pytest.raises(
        PipelineConfigValidationError,
        match=r"pipeline\.tasks\.AF\.task_ids.*at most 6",
    ):
        load_pipeline_config(config_path, known_tasks={"AF"})


def test_validation_rejects_attempt_to_configure_output_disables(tmp_path: Path) -> None:
    config_path = _write_config(
        tmp_path,
        """
schema_version = 1

[pipeline]
enable_plots = false

[pipeline.outputs]
enable_meta = false
enable_saved_data = false

[pipeline.tasks.AF]
domain = "cc"
task_ids = [945]
""".strip(),
    )

    with pytest.raises(
        PipelineConfigValidationError,
        match=r"pipeline\.outputs",
    ):
        load_pipeline_config(config_path, known_tasks={"AF"})
