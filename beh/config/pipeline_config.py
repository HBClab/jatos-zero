from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable

try:
    import tomllib
except ModuleNotFoundError:  # pragma: no cover - Python < 3.11 fallback
    import tomli as tomllib


REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CONFIG_PATH = REPO_ROOT / "config" / "pipeline.toml"
ALLOWED_DOMAINS = {"cc", "mem", "ps", "wl"}


class PipelineConfigValidationError(ValueError):
    """Raised when pipeline TOML fails schema validation."""


@dataclass(frozen=True)
class TaskQCConfig:
    threshold: float | None = None
    max_rt: int | None = None
    subject_column: str | None = None
    session_column: str | None = None


@dataclass(frozen=True)
class TaskRouteConfig:
    domain: str
    task_ids: list[int] = field(default_factory=list)
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
        raise PipelineConfigValidationError(
            f"Expected '{key_path}' to be a table, found {type(value).__name__}"
        )
    return value


def _is_int(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def _is_number(value: Any) -> bool:
    return (isinstance(value, (int, float)) and not isinstance(value, bool))


def _require_key(table: dict[str, Any], key: str, table_path: str) -> Any:
    if key not in table:
        raise PipelineConfigValidationError(f"Missing required key '{table_path}.{key}'")
    return table[key]


def _reject_unknown_keys(table: dict[str, Any], allowed_keys: set[str], table_path: str) -> None:
    unknown_keys = sorted(set(table.keys()) - allowed_keys)
    if unknown_keys:
        key_path = f"{table_path}.{unknown_keys[0]}"
        raise PipelineConfigValidationError(f"Unknown key '{key_path}'")


def _validate_string(value: Any, key_path: str) -> str:
    if not isinstance(value, str):
        raise PipelineConfigValidationError(
            f"Expected '{key_path}' to be a string, found {type(value).__name__}"
        )
    return value


def _validate_bool(value: Any, key_path: str) -> bool:
    if not isinstance(value, bool):
        raise PipelineConfigValidationError(
            f"Expected '{key_path}' to be a boolean, found {type(value).__name__}"
        )
    return value


def _validate_int(value: Any, key_path: str) -> int:
    if not _is_int(value):
        raise PipelineConfigValidationError(
            f"Expected '{key_path}' to be an integer, found {type(value).__name__}"
        )
    return value


def _validate_optional_string(value: Any, key_path: str) -> str | None:
    if value is None:
        return None
    return _validate_string(value, key_path)


def _load_task_routes(
    task_tables: dict[str, Any],
    known_tasks: set[str] | None,
) -> dict[str, TaskRouteConfig]:
    routes: dict[str, TaskRouteConfig] = {}
    for task_name, raw_task in task_tables.items():
        task_key_path = f"pipeline.tasks.{task_name}"
        if known_tasks is not None and task_name not in known_tasks:
            raise PipelineConfigValidationError(
                f"Unknown configured task '{task_key_path}'"
            )

        task_table = _as_dict(raw_task, f"pipeline.tasks.{task_name}")
        _reject_unknown_keys(task_table, {"domain", "task_ids", "qc"}, task_key_path)
        raw_domain = _require_key(task_table, "domain", task_key_path)
        domain = _validate_string(raw_domain, f"{task_key_path}.domain")
        if domain not in ALLOWED_DOMAINS:
            raise PipelineConfigValidationError(
                f"Invalid domain '{task_key_path}.domain': expected one of {sorted(ALLOWED_DOMAINS)}"
            )
        raw_task_ids = _require_key(task_table, "task_ids", task_key_path)
        if not isinstance(raw_task_ids, list):
            raise PipelineConfigValidationError(
                f"Expected '{task_key_path}.task_ids' to be a list, "
                f"found {type(raw_task_ids).__name__}"
            )
        if not raw_task_ids:
            raise PipelineConfigValidationError(
                f"Expected '{task_key_path}.task_ids' to be a non-empty list"
            )
        task_ids: list[int] = []
        for idx, task_id in enumerate(raw_task_ids):
            if not _is_int(task_id):
                raise PipelineConfigValidationError(
                    f"Expected '{task_key_path}.task_ids[{idx}]' to be an integer, "
                    f"found {type(task_id).__name__}"
                )
            task_ids.append(task_id)

        raw_qc = _as_dict(task_table.get("qc"), f"pipeline.tasks.{task_name}.qc")
        _reject_unknown_keys(
            raw_qc,
            {"threshold", "max_rt", "subject_column", "session_column"},
            f"{task_key_path}.qc",
        )

        threshold = raw_qc.get("threshold")
        if threshold is not None and not _is_number(threshold):
            raise PipelineConfigValidationError(
                f"Expected '{task_key_path}.qc.threshold' to be a number, "
                f"found {type(threshold).__name__}"
            )

        max_rt = raw_qc.get("max_rt")
        if max_rt is not None and not _is_int(max_rt):
            raise PipelineConfigValidationError(
                f"Expected '{task_key_path}.qc.max_rt' to be an integer, "
                f"found {type(max_rt).__name__}"
            )

        routes[task_name] = TaskRouteConfig(
            domain=domain,
            task_ids=task_ids,
            qc=TaskQCConfig(
                threshold=threshold,
                max_rt=max_rt,
                subject_column=_validate_optional_string(
                    raw_qc.get("subject_column"),
                    f"{task_key_path}.qc.subject_column",
                ),
                session_column=_validate_optional_string(
                    raw_qc.get("session_column"),
                    f"{task_key_path}.qc.session_column",
                ),
            ),
        )
    return routes


def load_pipeline_config(
    config_path: Path = DEFAULT_CONFIG_PATH,
    known_tasks: Iterable[str] | None = None,
) -> PipelineRuntimeConfig:
    resolved_path = config_path.resolve()
    if not resolved_path.exists():
        raise FileNotFoundError(
            f"Missing pipeline config at '{resolved_path}'. "
            "Create config/pipeline.toml before running the pipeline."
        )

    with resolved_path.open("rb") as config_file:
        raw_config = tomllib.load(config_file)

    _reject_unknown_keys(raw_config, {"schema_version", "pipeline"}, "root")

    schema_version = _validate_int(
        _require_key(raw_config, "schema_version", "root"),
        "schema_version",
    )
    pipeline_table = _as_dict(
        _require_key(raw_config, "pipeline", "root"),
        "pipeline",
    )
    _reject_unknown_keys(pipeline_table, {"enable_plots", "defaults", "tasks"}, "pipeline")

    raw_enable_plots = pipeline_table.get("enable_plots", False)
    enable_plots = _validate_bool(raw_enable_plots, "pipeline.enable_plots")

    defaults_table = _as_dict(pipeline_table.get("defaults"), "pipeline.defaults")
    _reject_unknown_keys(defaults_table, {"columns"}, "pipeline.defaults")

    columns_table = _as_dict(defaults_table.get("columns"), "pipeline.defaults.columns")
    _reject_unknown_keys(columns_table, {"subject", "session"}, "pipeline.defaults.columns")

    subject_column = _validate_optional_string(
        columns_table.get("subject"),
        "pipeline.defaults.columns.subject",
    )
    session_column = _validate_optional_string(
        columns_table.get("session"),
        "pipeline.defaults.columns.session",
    )

    tasks_table = _as_dict(
        _require_key(pipeline_table, "tasks", "pipeline"),
        "pipeline.tasks",
    )
    known_tasks_set = set(known_tasks) if known_tasks is not None else None

    return PipelineRuntimeConfig(
        schema_version=schema_version,
        pipeline=PipelineConfig(
            enable_plots=enable_plots,
            defaults=PipelineDefaultsConfig(
                columns=PipelineColumnsConfig(
                    subject=subject_column,
                    session=session_column,
                )
            ),
            tasks=_load_task_routes(tasks_table, known_tasks=known_tasks_set),
        ),
        config_path=resolved_path,
    )
