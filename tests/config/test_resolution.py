from __future__ import annotations

from pathlib import Path

from config.pipeline_config import (
    PipelineColumnsConfig,
    PipelineConfig,
    PipelineDefaultsConfig,
    PipelineRuntimeConfig,
    TaskQCConfig,
    TaskRouteConfig,
)
import main_handler
from main_handler import Handler


def test_resolve_task_qc_applies_override_and_code_default_fallback(monkeypatch) -> None:
    runtime_config = PipelineRuntimeConfig(
        schema_version=1,
        pipeline=PipelineConfig(
            tasks={
                "AF": TaskRouteConfig(
                    domain="cc",
                    task_ids=[945],
                    qc=TaskQCConfig(threshold=0.75),
                ),
                "SM": TaskRouteConfig(
                    domain="mem",
                    task_ids=[955],
                ),
            },
        ),
        config_path=Path("/tmp/pipeline.toml"),
    )
    monkeypatch.setattr(
        main_handler,
        "load_pipeline_config",
        lambda **kwargs: runtime_config,
    )

    handler = Handler()

    af_qc = handler.resolve_task_qc("AF")
    sm_qc = handler.resolve_task_qc("SM")

    assert af_qc["threshold"] == 0.75
    assert af_qc["max_rt"] == 1800
    assert sm_qc["threshold"] == 0.5
    assert sm_qc["max_rt"] == 2000


def test_resolve_task_columns_fallback_order(monkeypatch) -> None:
    runtime_config = PipelineRuntimeConfig(
        schema_version=1,
        pipeline=PipelineConfig(
            defaults=PipelineDefaultsConfig(
                columns=PipelineColumnsConfig(
                    subject="subject_default",
                    session="session_default",
                )
            ),
            tasks={
                "AF": TaskRouteConfig(
                    domain="cc",
                    task_ids=[945],
                    qc=TaskQCConfig(subject_column="subject_override"),
                ),
            },
        ),
        config_path=Path("/tmp/pipeline.toml"),
    )
    monkeypatch.setattr(
        main_handler,
        "load_pipeline_config",
        lambda **kwargs: runtime_config,
    )

    handler = Handler()
    af_subject, af_session = handler.resolve_task_columns("AF")

    assert af_subject == "subject_override"
    assert af_session == "session_default"


def test_resolve_task_columns_uses_code_defaults_when_config_missing(monkeypatch) -> None:
    runtime_config = PipelineRuntimeConfig(
        schema_version=1,
        pipeline=PipelineConfig(
            tasks={
                "AF": TaskRouteConfig(
                    domain="cc",
                    task_ids=[945],
                ),
            },
        ),
        config_path=Path("/tmp/pipeline.toml"),
    )
    monkeypatch.setattr(
        main_handler,
        "load_pipeline_config",
        lambda **kwargs: runtime_config,
    )

    handler = Handler()
    subject_column, session_column = handler.resolve_task_columns("AF")

    assert subject_column == "subject_id"
    assert session_column == "session_number"
