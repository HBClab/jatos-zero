from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

try:
    import tomllib
except ModuleNotFoundError:  # pragma: no cover - Python < 3.11 fallback
    import tomli as tomllib


REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CONFIG_PATH = REPO_ROOT / "config" / "pipeline.toml"


@dataclass(frozen=True)
class TaskQCConfig:
    threshold: float | None = None
    max_rt: int | None = None
    subject_column: str | None = None
    session_column: str | None = None


@dataclass(frozen=True)
class TaskRouteConfig:
    domain: str
    qc: TaskQCConfig = field(default_factory=TaskQCConfig)


@dataclass(frozen=True)
class PipelineColumnsConfig:
    subject: str | None = None
    session: str | None = None


@dataclass(frozen=True)
class PipelineDefaultsConfig:
    columns: PipelineColumnsConfig = field(default_factory=PipelineColumnsConfig)


@dataclass(frozen=True)
class PipelineConfig:
    enable_plots: bool = False
    defaults: PipelineDefaultsConfig = field(default_factory=PipelineDefaultsConfig)
    tasks: dict[str, TaskRouteConfig] = field(default_factory=dict)


@dataclass(frozen=True)
class PipelineRuntimeConfig:
    schema_version: int
    pipeline: PipelineConfig
    config_path: Path


def _as_dict(value: Any, key_path: str) -> dict[str, Any]:
    if value is None:
        return {}
    if not isinstance(value, dict):
        raise TypeError(f"Expected '{key_path}' to be a table, found {type(value).__name__}")
    return value


def _load_task_routes(task_tables: dict[str, Any]) -> dict[str, TaskRouteConfig]:
    routes: dict[str, TaskRouteConfig] = {}
    for task_name, raw_task in task_tables.items():
        task_table = _as_dict(raw_task, f"pipeline.tasks.{task_name}")
        raw_qc = _as_dict(task_table.get("qc"), f"pipeline.tasks.{task_name}.qc")
        routes[task_name] = TaskRouteConfig(
            domain=str(task_table.get("domain", "")),
            qc=TaskQCConfig(
                threshold=raw_qc.get("threshold"),
                max_rt=raw_qc.get("max_rt"),
                subject_column=raw_qc.get("subject_column"),
                session_column=raw_qc.get("session_column"),
            ),
        )
    return routes


def load_pipeline_config(config_path: Path = DEFAULT_CONFIG_PATH) -> PipelineRuntimeConfig:
    resolved_path = config_path.resolve()
    if not resolved_path.exists():
        raise FileNotFoundError(
            f"Missing pipeline config at '{resolved_path}'. "
            "Create config/pipeline.toml before running the pipeline."
        )

    with resolved_path.open("rb") as config_file:
        raw_config = tomllib.load(config_file)

    pipeline_table = _as_dict(raw_config.get("pipeline"), "pipeline")
    defaults_table = _as_dict(pipeline_table.get("defaults"), "pipeline.defaults")
    columns_table = _as_dict(defaults_table.get("columns"), "pipeline.defaults.columns")
    tasks_table = _as_dict(pipeline_table.get("tasks"), "pipeline.tasks")

    return PipelineRuntimeConfig(
        schema_version=int(raw_config.get("schema_version", 1)),
        pipeline=PipelineConfig(
            enable_plots=bool(pipeline_table.get("enable_plots", False)),
            defaults=PipelineDefaultsConfig(
                columns=PipelineColumnsConfig(
                    subject=columns_table.get("subject"),
                    session=columns_table.get("session"),
                )
            ),
            tasks=_load_task_routes(tasks_table),
        ),
        config_path=resolved_path,
    )

