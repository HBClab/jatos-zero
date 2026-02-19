from __future__ import annotations

from pathlib import Path

import pytest

from config.pipeline_config import (
    PipelineConfig,
    PipelineRuntimeConfig,
    TaskRouteConfig,
)
import main_handler
from main_handler import Handler


def test_all_runs_only_configured_subset(monkeypatch) -> None:
    subset_config = PipelineRuntimeConfig(
        schema_version=1,
        pipeline=PipelineConfig(
            tasks={
                "WL": TaskRouteConfig(domain="wl", task_ids=[958]),
                "AF": TaskRouteConfig(domain="cc", task_ids=[945]),
            },
        ),
        config_path=Path("/tmp/pipeline.toml"),
    )
    monkeypatch.setattr(
        main_handler,
        "load_pipeline_config",
        lambda **kwargs: subset_config,
    )

    handler = Handler()
    seen_tasks: list[str] = []
    monkeypatch.setattr(handler, "pull", lambda task: seen_tasks.append(task))

    handler.run("all")

    assert seen_tasks == ["AF", "WL"]


def test_omitted_known_task_is_explicit_error(monkeypatch) -> None:
    subset_config = PipelineRuntimeConfig(
        schema_version=1,
        pipeline=PipelineConfig(
            tasks={"AF": TaskRouteConfig(domain="cc", task_ids=[945])},
        ),
        config_path=Path("/tmp/pipeline.toml"),
    )
    monkeypatch.setattr(
        main_handler,
        "load_pipeline_config",
        lambda **kwargs: subset_config,
    )

    handler = Handler()
    with pytest.raises(ValueError, match="not enabled in config/pipeline.toml"):
        handler.pull("NF")
