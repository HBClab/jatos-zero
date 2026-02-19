from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Iterable, Mapping

import pandas as pd


FIXTURES_DIR = Path(__file__).resolve().parents[2] / "fixtures"


def fixtures_root() -> Path:
    return FIXTURES_DIR


def fixture_path(*relative_parts: str) -> Path:
    return fixtures_root().joinpath(*relative_parts)


def load_records_fixture(*relative_parts: str) -> list[dict[str, Any]]:
    path = fixture_path(*relative_parts)
    suffix = path.suffix.lower()

    if suffix == ".json":
        payload = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(payload, list):
            return [dict(item) for item in payload]
        if isinstance(payload, dict):
            return [dict(payload)]
        raise ValueError(
            f"Unsupported JSON payload type in {path}: {type(payload)!r}"
        )

    if suffix == ".csv":
        return pd.read_csv(path).to_dict(orient="records")

    raise ValueError(f"Unsupported fixture type for {path}. Use .json or .csv")


def load_dataframe_fixture(*relative_parts: str) -> pd.DataFrame:
    records = load_records_fixture(*relative_parts)
    return pd.DataFrame(records)


def build_trial_frame(
    rows: Iterable[Mapping[str, Any]],
    *,
    task: str,
    subject_id: str = "9001",
    session: int = 1,
) -> pd.DataFrame:
    normalized_rows: list[dict[str, Any]] = []

    for row in rows:
        normalized = dict(row)
        normalized.setdefault("task", task)
        normalized.setdefault("subject_id", subject_id)
        normalized.setdefault("session", session)
        normalized_rows.append(normalized)

    return pd.DataFrame(normalized_rows)
