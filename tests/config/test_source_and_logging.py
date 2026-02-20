from __future__ import annotations

from pathlib import Path

from config.pipeline_config import (
    PipelineColumnsConfig,
    PipelineConfig,
    PipelineDefaultsConfig,
    PipelineOutputsConfig,
    PipelineRuntimeConfig,
    TaskQCConfig,
    TaskRouteConfig,
    load_pipeline_config,
)
from data_processing.save_utils import SAVE_EVERYTHING
import main_handler
from main_handler import Handler


def _write_config(tmp_path: Path, content: str) -> Path:
    config_path = tmp_path / "config" / "pipeline.toml"
    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text(content, encoding="utf-8")
    return config_path


def test_handler_uses_runtime_single_source_loader(monkeypatch) -> None:
    runtime_config = PipelineRuntimeConfig(
        schema_version=1,
        pipeline=PipelineConfig(
            tasks={"AF": TaskRouteConfig(domain="cc", task_ids=[945])},
        ),
        config_path=Path("/tmp/pipeline.toml"),
    )
    seen: dict[str, object] = {}

    def fake_runtime_loader(**kwargs):
        seen["kwargs"] = kwargs
        return runtime_config

    monkeypatch.setenv("PIPELINE_CONFIG_PATH", "/tmp/alternate.toml")
    monkeypatch.setattr(main_handler, "load_pipeline_config", fake_runtime_loader)

    handler = Handler()
    assert seen["kwargs"] == {"known_tasks": handler.task_order}


def test_new_config_keys_cannot_be_env_overridden(tmp_path: Path, monkeypatch) -> None:
    config_path = _write_config(
        tmp_path,
        """
schema_version = 1

[pipeline]
enable_plots = false

[pipeline.tasks.AF]
domain = "cc"
task_ids = [945]
""".strip(),
    )
    monkeypatch.setenv("PIPELINE_ENABLE_PLOTS", "true")
    monkeypatch.setenv("PIPELINE_TASK_AF_THRESHOLD", "0.9")

    loaded = load_pipeline_config(config_path=config_path, known_tasks={"AF"})
    assert loaded.pipeline.enable_plots is False
    assert loaded.pipeline.tasks["AF"].qc.threshold is None


def test_startup_logging_reports_effective_config(monkeypatch) -> None:
    runtime_config = PipelineRuntimeConfig(
        schema_version=1,
        pipeline=PipelineConfig(
            enable_plots=False,
            tasks={"AF": TaskRouteConfig(domain="cc", task_ids=[945])},
        ),
        config_path=Path("/tmp/pipeline.toml"),
    )
    logs: list[tuple[str, str]] = []
    monkeypatch.setattr(main_handler, "load_pipeline_config", lambda **kwargs: runtime_config)
    monkeypatch.setattr(
        main_handler,
        "cprint",
        lambda message, color: logs.append((message, color)),
    )

    Handler()

    assert logs
    startup_log, color = logs[0]
    assert "schema_version=1" in startup_log
    assert "config_path=/tmp/pipeline.toml" in startup_log
    assert "configured_tasks=AF" in startup_log
    assert "enable_plots=False" in startup_log
    assert "enable_saved_data=True" in startup_log
    assert "data_root_path=." in startup_log
    assert "data_folder_name=data" in startup_log
    assert "resolved_data_root=" in startup_log
    assert "save_dedup_csv=True" in startup_log
    assert "save_dedup_plots=True" in startup_log
    assert color == "cyan"


def test_task_logging_reports_route_qc_and_columns(monkeypatch) -> None:
    runtime_config = PipelineRuntimeConfig(
        schema_version=1,
        pipeline=PipelineConfig(
            enable_plots=False,
            defaults=PipelineDefaultsConfig(
                columns=PipelineColumnsConfig(
                    subject="subject_default",
                    session="session_default",
                )
            ),
            tasks={
                "AF": TaskRouteConfig(
                    domain="cc",
                    task_ids=[945, 960],
                    qc=TaskQCConfig(
                        threshold=0.75,
                        max_rt=1900,
                    ),
                )
            },
        ),
        config_path=Path("/tmp/pipeline.toml"),
    )
    logs: list[tuple[str, str]] = []
    monkeypatch.setattr(main_handler, "load_pipeline_config", lambda **kwargs: runtime_config)
    monkeypatch.setattr(
        main_handler,
        "cprint",
        lambda message, color: logs.append((message, color)),
    )

    handler = Handler()
    logs.clear()
    handler._log_task_effective_config("AF")

    assert logs
    task_log, color = logs[0]
    assert "Task AF config:" in task_log
    assert "domain=cc" in task_log
    assert "task_ids=[945, 960]" in task_log
    assert "qc.threshold=0.75" in task_log
    assert "qc.max_rt=1900" in task_log
    assert "subject_column=subject_default" in task_log
    assert "session_column=session_default" in task_log
    assert color == "cyan"


def test_task_output_logging_reports_resolved_root_and_dedup(monkeypatch) -> None:
    runtime_config = PipelineRuntimeConfig(
        schema_version=1,
        pipeline=PipelineConfig(
            enable_plots=True,
            outputs=PipelineOutputsConfig(
                enable_saved_data=True,
                data_root_path="/tmp",
                data_folder_name="unit-data",
            ),
            tasks={"AF": TaskRouteConfig(domain="cc", task_ids=[945])},
        ),
        config_path=Path("/tmp/pipeline.toml"),
    )
    logs: list[tuple[str, str]] = []
    monkeypatch.setattr(main_handler, "load_pipeline_config", lambda **kwargs: runtime_config)
    monkeypatch.setattr(
        main_handler,
        "cprint",
        lambda message, color: logs.append((message, color)),
    )
    monkeypatch.setattr(SAVE_EVERYTHING, "save_dfs", lambda self, categories, task: None)
    monkeypatch.setattr(SAVE_EVERYTHING, "save_plots", lambda self, plots, task: None)

    handler = Handler()
    logs.clear()
    handler._save_task_artifacts(task="AF", categories=[], plots=[])

    assert logs
    output_logs = [entry for entry, color in logs if color == "cyan"]
    assert output_logs
    assert any("Task AF output config:" in entry for entry in output_logs)
    assert any("resolved_data_root=" in entry for entry in output_logs)
    assert any("save_dedup_csv=True" in entry for entry in output_logs)
    assert any("save_dedup_plots=True" in entry for entry in output_logs)
