from __future__ import annotations

from pathlib import Path

import pytest

from config.pipeline_config import (
    PipelineConfig,
    PipelineOutputsConfig,
    PipelineRuntimeConfig,
    TaskRouteConfig,
)
from data_processing.meta import META_RECREATE
import main_handler
from main_handler import Handler


def _build_handler_with_roots(
    tmp_path: Path,
    monkeypatch,
) -> tuple[Handler, Path, Path]:
    data_root_path = tmp_path / "root"
    data_folder_name = "data"
    resolved_data_root = data_root_path / data_folder_name
    meta_root = tmp_path / "meta"

    runtime_config = PipelineRuntimeConfig(
        schema_version=1,
        pipeline=PipelineConfig(
            outputs=PipelineOutputsConfig(
                enable_saved_data=True,
                data_root_path=str(data_root_path),
                data_folder_name=data_folder_name,
            ),
            tasks={"AF": TaskRouteConfig(domain="cc", task_ids=[945])},
        ),
        config_path=Path("/tmp/pipeline.toml"),
    )
    monkeypatch.setattr(
        main_handler,
        "load_pipeline_config",
        lambda **kwargs: runtime_config,
    )

    handler = Handler()
    handler._meta_recreator = META_RECREATE(
        data_root=resolved_data_root,
        meta_root=meta_root,
    )
    return handler, resolved_data_root, meta_root


def test_meta_temp_artifacts_cleaned_after_success(tmp_path: Path, monkeypatch) -> None:
    handler, data_root, meta_root = _build_handler_with_roots(tmp_path, monkeypatch)

    data_tmp = data_root / "9001" / "1" / "AF" / "data" / "artifact.csv.tmp"
    data_tmp.parent.mkdir(parents=True, exist_ok=True)
    data_tmp.write_text("tmp", encoding="utf-8")

    meta_tmp = meta_root / "cc_master.csv.tmp"
    meta_tmp.parent.mkdir(parents=True, exist_ok=True)
    meta_tmp.write_text("tmp", encoding="utf-8")

    monkeypatch.setattr(handler._meta_recreator, "recreate", lambda domain: {})

    handler._meta_rebuild_pending = True
    handler._run_meta_if_needed(force=True)

    assert not data_tmp.exists()
    assert not meta_tmp.exists()


def test_meta_temp_artifacts_cleaned_after_failure(tmp_path: Path, monkeypatch) -> None:
    handler, data_root, meta_root = _build_handler_with_roots(tmp_path, monkeypatch)

    data_tmp = data_root / "9001" / "1" / "AF" / "data" / "artifact.csv.tmp"
    data_tmp.parent.mkdir(parents=True, exist_ok=True)
    data_tmp.write_text("tmp", encoding="utf-8")

    meta_tmp = meta_root / "cc_master.csv.tmp"
    meta_tmp.parent.mkdir(parents=True, exist_ok=True)
    meta_tmp.write_text("tmp", encoding="utf-8")

    def failing_recreate(domain: str):
        raise RuntimeError("meta rebuild failed")

    monkeypatch.setattr(handler._meta_recreator, "recreate", failing_recreate)

    handler._meta_rebuild_pending = True
    with pytest.raises(RuntimeError, match="meta rebuild failed"):
        handler._run_meta_if_needed(force=True)

    assert not data_tmp.exists()
    assert not meta_tmp.exists()
