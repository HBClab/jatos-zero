from __future__ import annotations

from pathlib import Path

import pandas as pd

from data_processing.meta import META_RECREATE
from data_processing.save_utils import SAVE_EVERYTHING
from data_processing.utils import CONVERT_TO_CSV
from config.pipeline_config import (
    PipelineConfig,
    PipelineRuntimeConfig,
    TaskRouteConfig,
)
import main_handler
from main_handler import Handler
from tests.data_processing.helpers.fixture_factories import (
    load_dataframe_fixture,
)


def test_af_known_task_happy_path_generates_artifacts_and_meta(
    tmp_path: Path,
    monkeypatch,
) -> None:
    data_root = tmp_path / "data"
    meta_root = tmp_path / "meta"
    data_root.mkdir(parents=True, exist_ok=True)
    meta_root.mkdir(parents=True, exist_ok=True)

    af_df = load_dataframe_fixture("af_known_task", "af_minimal_trials.csv")
    af_df["session_number"] = pd.to_numeric(
        af_df.get("session", 1), errors="coerce"
    ).fillna(1)
    af_df["block"] = af_df["block"].astype(str).str.lower()

    def patched_convert_to_csv(self, txt_dfs):
        return [af_df.copy()]

    monkeypatch.setattr(
        CONVERT_TO_CSV,
        "convert_to_csv",
        patched_convert_to_csv,
    )

    plot_disabled_config = PipelineRuntimeConfig(
        schema_version=1,
        pipeline=PipelineConfig(
            enable_plots=False,
            tasks={"AF": TaskRouteConfig(domain="cc", task_ids=[945])},
        ),
        config_path=Path("/tmp/pipeline.toml"),
    )
    monkeypatch.setattr(
        main_handler,
        "load_pipeline_config",
        lambda **kwargs: plot_disabled_config,
    )

    original_save_init = SAVE_EVERYTHING.__init__

    def patched_save_init(self):
        original_save_init(self)
        self.datadir = str(data_root)

    monkeypatch.setattr(SAVE_EVERYTHING, "__init__", patched_save_init)

    handler = Handler()
    handler._meta_recreator = META_RECREATE(
        data_root=data_root,
        meta_root=meta_root,
    )

    dummy_txt_frames = [pd.DataFrame([{"file_content": "[]"}])]
    csv_dfs, result = handler.convert_to_csv(dummy_txt_frames, "AF")

    assert len(csv_dfs) == 1
    categories, plots = result
    assert len(categories) == 1
    assert len(plots) == 1

    subject_id = str(af_df["subject_id"].iloc[0])
    session = str(af_df["session_number"].iloc[0])
    subject_root = data_root / subject_id / session / "AF"

    data_files = sorted((subject_root / "data").glob("*.csv"))
    assert len(data_files) == 1
    assert f"{subject_id}_ses-1_cat-" in data_files[0].name

    plot_files = sorted((subject_root / "plot").glob("*.png"))
    assert len(plot_files) == 0

    expected_meta = [
        "cc_master.csv",
        "mem_master.csv",
        "ps_master.csv",
        "wl_master.csv",
        "wl_master_wide.csv",
    ]
    for file_name in expected_meta:
        assert (meta_root / file_name).exists()

    cc_master = pd.read_csv(meta_root / "cc_master.csv")
    assert not cc_master.empty
    assert "AF" in set(cc_master["task"].astype(str))
    assert subject_id in set(cc_master["subject_id"].astype(str))


def test_af_happy_path_generates_plots_when_enabled(
    tmp_path: Path,
    monkeypatch,
) -> None:
    data_root = tmp_path / "data"
    meta_root = tmp_path / "meta"
    data_root.mkdir(parents=True, exist_ok=True)
    meta_root.mkdir(parents=True, exist_ok=True)

    af_df = load_dataframe_fixture("af_known_task", "af_minimal_trials.csv")
    af_df["session_number"] = pd.to_numeric(
        af_df.get("session", 1), errors="coerce"
    ).fillna(1)
    af_df["block"] = af_df["block"].astype(str).str.lower()

    def patched_convert_to_csv(self, txt_dfs):
        return [af_df.copy()]

    monkeypatch.setattr(
        CONVERT_TO_CSV,
        "convert_to_csv",
        patched_convert_to_csv,
    )

    plot_enabled_config = PipelineRuntimeConfig(
        schema_version=1,
        pipeline=PipelineConfig(
            enable_plots=True,
            tasks={"AF": TaskRouteConfig(domain="cc", task_ids=[945])},
        ),
        config_path=Path("/tmp/pipeline.toml"),
    )
    monkeypatch.setattr(
        main_handler,
        "load_pipeline_config",
        lambda **kwargs: plot_enabled_config,
    )

    original_save_init = SAVE_EVERYTHING.__init__

    def patched_save_init(self):
        original_save_init(self)
        self.datadir = str(data_root)

    monkeypatch.setattr(SAVE_EVERYTHING, "__init__", patched_save_init)

    handler = Handler()
    handler._meta_recreator = META_RECREATE(
        data_root=data_root,
        meta_root=meta_root,
    )

    dummy_txt_frames = [pd.DataFrame([{"file_content": "[]"}])]
    handler.convert_to_csv(dummy_txt_frames, "AF")

    subject_id = str(af_df["subject_id"].iloc[0])
    session = str(af_df["session_number"].iloc[0])
    subject_root = data_root / subject_id / session / "AF"
    plot_files = sorted((subject_root / "plot").glob("*.png"))
    assert len(plot_files) == 2
    assert any(path.name.endswith("_plot1.png") for path in plot_files)
    assert any(path.name.endswith("_plot2.png") for path in plot_files)
