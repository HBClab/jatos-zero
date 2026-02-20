from __future__ import annotations

from pathlib import Path


def resolve_data_save_root(*, data_root_path: str, data_folder_name: str) -> Path:
    """
    Resolve effective persistent-data root as:
    <data_root_path>/<data_folder_name>
    """
    if not isinstance(data_root_path, str) or not data_root_path.strip():
        raise ValueError("data_root_path must be a non-empty string")
    if not isinstance(data_folder_name, str) or not data_folder_name.strip():
        raise ValueError("data_folder_name must be a non-empty string")
    return (Path(data_root_path).expanduser() / data_folder_name).resolve()
