from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re
from typing import Dict, Iterable, List, Optional, Tuple

import pandas as pd

from .utils import QC_UTILS
from .wl_qc import WL_QC


@dataclass
class ParsedIdentifiers:
    subject_id: str
    session: Optional[object]


class META_RECREATE:
    """
    Rebuild domain-level meta aggregates by rescanning saved QC CSV exports.

    Usage
    -----
        META_RECREATE().recreate("cc")
        META_RECREATE().recreate("mem")
        META_RECREATE().recreate("ps")
        META_RECREATE().recreate("wl")

    Each invocation rewrites the corresponding meta CSV(s) under ``meta/``.
    """

    CC_TASKS = {"AF", "NF", "NTS", "ATS", "NNB", "VNB"}
    MEM_TASKS = {"FN", "SM"}
    PS_TASKS = {"PC", "LC", "DSST"}
    WL_TASKS = {"WL", "DWL"}

    FILENAME_PATTERN = re.compile(r"(?P<subject>\d+)_ses-(?P<session>[^_]+)_cat-")

    def __init__(
        self,
        data_root: Path | str | None = None,
        meta_root: Path | str | None = None,
    ) -> None:
        base_dir = Path(__file__).resolve().parents[2]
        self.data_root = Path(data_root) if data_root else base_dir / "data"
        self.meta_root = Path(meta_root) if meta_root else base_dir / "meta"
        self.meta_root.mkdir(parents=True, exist_ok=True)

        self._qc_utils = QC_UTILS()

    # ------------------------------------------------------------------ public
    def recreate(self, domain: str) -> Dict[str, Path]:
        """
        Rebuild the meta CSV(s) for ``domain`` and return the paths written.

        Args:
            domain: One of ``cc``, ``mem``, ``ps``, or ``wl`` (case-insensitive).

        Returns:
            Mapping of output filename to absolute Path.
        """
        domain_key = domain.lower()
        if domain_key == "cc":
            df = self._build_cc_master()
            target = self.meta_root / "cc_master.csv"
            self._write_atomic(df, target)
            return {"cc_master.csv": target}

        if domain_key == "mem":
            df = self._build_mem_master()
            target = self.meta_root / "mem_master.csv"
            self._write_atomic(df, target)
            return {"mem_master.csv": target}

        if domain_key == "ps":
            df = self._build_ps_master()
            target = self.meta_root / "ps_master.csv"
            self._write_atomic(df, target)
            return {"ps_master.csv": target}

        if domain_key == "wl":
            wide, flat = self._build_wl_master()
            wide_target = self.meta_root / "wl_master_wide.csv"
            flat_target = self.meta_root / "wl_master.csv"
            self._write_atomic(wide, wide_target)
            self._write_atomic(flat, flat_target)
            return {
                "wl_master_wide.csv": wide_target,
                "wl_master.csv": flat_target,
            }

        raise ValueError(
            "Domain must be one of {'cc', 'mem', 'ps', 'wl'}; "
            f"received '{domain}'."
        )

    # ----------------------------------------------------------------- helpers
    def _write_atomic(self, df: pd.DataFrame, path: Path) -> None:
        temp_path = path.with_suffix(path.suffix + ".tmp")
        df.to_csv(temp_path, index=False)
        temp_path.replace(path)

    def _iter_task_files(self, tasks: Iterable[str]) -> Iterable[Tuple[str, Path]]:
        for task in sorted(set(tasks)):
            pattern = f"**/{task}/data/*.csv"
            for path in sorted(self.data_root.glob(pattern)):
                yield task, path

    def _parse_identifiers(self, csv_path: Path, df: pd.DataFrame) -> ParsedIdentifiers:
        # Prefer dataframe values (they preserve floats when applicable)
        subject = self._extract_subject(df)
        session = self._extract_session(df)

        if subject is None or session is None:
            match = self.FILENAME_PATTERN.search(csv_path.name)
            if match:
                if subject is None:
                    subject = match.group("subject")
                if session is None:
                    session = self._coerce_session(match.group("session"))

        if subject is None:
            subject = csv_path.parent.parent.name  # fallback to folder name

        return ParsedIdentifiers(str(subject), session)

    @staticmethod
    def _extract_subject(df: pd.DataFrame) -> Optional[object]:
        if "subject_id" in df.columns:
            series = df["subject_id"].dropna()
            if not series.empty:
                return series.iloc[0]
        return None

    @staticmethod
    def _extract_session(df: pd.DataFrame) -> Optional[object]:
        for column in ("session_number", "session"):
            if column in df.columns:
                series = df[column].dropna()
                if not series.empty:
                    return series.iloc[0]
        return None

    @staticmethod
    def _coerce_session(value: str) -> object:
        try:
            if "." in value:
                return float(value)
            return int(value)
        except ValueError:
            return value

    @staticmethod
    def _normalize_correct_column(df: pd.DataFrame, column: str) -> pd.DataFrame:
        if column in df.columns:
            df[column] = pd.to_numeric(df[column], errors="coerce")
        return df

    # ----------------------------------------------------------- domain builds
    def _build_cc_master(self) -> pd.DataFrame:
        records: List[Dict[str, object]] = []
        tasks = self.CC_TASKS

        for task, csv_path in self._iter_task_files(tasks):
            df = pd.read_csv(csv_path)
            if df.empty:
                continue

            identifiers = self._parse_identifiers(csv_path, df)
            cond_col = "condition" if task in {"AF", "NF", "NNB", "VNB"} else "block_cond"
            if cond_col not in df.columns:
                continue

            df = self._normalize_correct_column(df, "correct")
            acc_by = self._qc_utils.get_acc_by_block_cond(
                df,
                block_cond_column_name=cond_col,
                acc_column_name="correct",
                correct_symbol=1,
                incorrect_symbol=0,
            )
            rt_by = self._qc_utils.get_avg_rt(
                df,
                rt_column_name="response_time",
                conditon_column_name=cond_col,
            )

            all_conditions = sorted(set(acc_by.keys()) | set(rt_by.keys()), key=str)
            for cond in all_conditions:
                records.append(
                    {
                        "task": task,
                        "subject_id": identifiers.subject_id,
                        "session": identifiers.session,
                        "condition": cond,
                        "accuracy": float(acc_by.get(cond, 0.0)),
                        "mean_rt": float(rt_by.get(cond, float("nan"))),
                    }
                )

        df = pd.DataFrame(
            records,
            columns=[
                "task",
                "subject_id",
                "session",
                "condition",
                "accuracy",
                "mean_rt",
            ],
        )
        if not df.empty:
            df = df.sort_values(["task", "subject_id", "session", "condition"]).reset_index(
                drop=True
            )
        return df

    def _build_mem_master(self) -> pd.DataFrame:
        records: List[Dict[str, object]] = []
        tasks = self.MEM_TASKS

        for task, csv_path in self._iter_task_files(tasks):
            df = pd.read_csv(csv_path)
            if df.empty:
                continue

            identifiers = self._parse_identifiers(csv_path, df)
            if "block_c" not in df.columns:
                continue

            df = self._normalize_correct_column(df, "correct")
            ct_by = self._qc_utils.get_count_correct(
                df,
                block_cond_column_name="block_c",
                acc_column_name="correct",
                correct_symbol=1,
            )
            acc_by = self._qc_utils.get_acc_by_block_cond(
                df,
                block_cond_column_name="block_c",
                acc_column_name="correct",
                correct_symbol=1,
                incorrect_symbol=0,
            )
            rt_by = self._qc_utils.get_avg_rt(
                df,
                rt_column_name="response_time",
                conditon_column_name="block_c",
            )

            all_conditions = sorted(
                set(ct_by.keys()) | set(acc_by.keys()) | set(rt_by.keys()), key=str
            )
            for cond in all_conditions:
                records.append(
                    {
                        "task": task,
                        "subject_id": identifiers.subject_id,
                        "session": identifiers.session,
                        "condition": cond,
                        "count_correct": int(ct_by.get(cond, 0)),
                        "mean_rt": float(rt_by.get(cond, float("nan"))),
                        "accuracy": float(acc_by.get(cond, 0.0)),
                    }
                )

        df = pd.DataFrame(
            records,
            columns=[
                "task",
                "subject_id",
                "session",
                "condition",
                "count_correct",
                "mean_rt",
                "accuracy",
            ],
        )
        if not df.empty:
            df = df.sort_values(["task", "subject_id", "session", "condition"]).reset_index(
                drop=True
            )
        return df

    def _build_ps_master(self) -> pd.DataFrame:
        records: List[Dict[str, object]] = []
        tasks = self.PS_TASKS

        for task, csv_path in self._iter_task_files(tasks):
            df = pd.read_csv(csv_path)
            if df.empty:
                continue

            identifiers = self._parse_identifiers(csv_path, df)
            if "block_c" not in df.columns:
                continue

            df = self._normalize_correct_column(df, "correct")
            ct_by = self._qc_utils.get_count_correct(
                df,
                block_cond_column_name="block_c",
                acc_column_name="correct",
                correct_symbol=1,
            )

            for cond, count in ct_by.items():
                records.append(
                    {
                        "task": task,
                        "subject_id": identifiers.subject_id,
                        "session": identifiers.session,
                        "condition": cond,
                        "count_correct": int(count),
                    }
                )

        df = pd.DataFrame(
            records,
            columns=[
                "task",
                "subject_id",
                "session",
                "condition",
                "count_correct",
            ],
        )
        if not df.empty:
            df = df.sort_values(["task", "subject_id", "session", "condition"]).reset_index(
                drop=True
            )
        return df

    def _build_wl_master(self) -> Tuple[pd.DataFrame, pd.DataFrame]:
        rows: Dict[Tuple[str, object], Dict[str, object]] = {}

        for task, csv_path in self._iter_task_files(self.WL_TASKS):
            df = pd.read_csv(csv_path)
            if df.empty:
                continue
            df = self._prepare_wl_dataframe(df)

            identifiers = self._parse_identifiers(csv_path, df)
            version = self._extract_version(df)

            wl_qc = WL_QC()
            if task == "WL":
                df_all, _ = wl_qc.wl_qc(df, version)
                counts = WL_QC.wl_count_correct(df_all).iloc[0].to_dict()
                upd = {
                    "block_1": counts.get("learn_1", 0),
                    "block_2": counts.get("learn_2", 0),
                    "block_3": counts.get("learn_3", 0),
                    "block_4": counts.get("learn_4", 0),
                    "block_5": counts.get("learn_5", 0),
                    "distraction": counts.get("distraction", 0),
                    "immediate": counts.get("immediate", 0),
                    "task": "WL",
                }
            else:
                df_all, _ = wl_qc.dwl_qc(df, version)
                counts = WL_QC.dwl_count_correct(df_all).iloc[0].to_dict()
                upd = {
                    "delay": counts.get("delay", 0),
                    "task": "DWL",
                }

            key = (identifiers.subject_id, identifiers.session)
            rows.setdefault(
                key,
                {
                    "subject_id": identifiers.subject_id,
                    "session": identifiers.session,
                    "task": None,
                    "block_1": 0,
                    "block_2": 0,
                    "block_3": 0,
                    "block_4": 0,
                    "block_5": 0,
                    "distraction": 0,
                    "immediate": 0,
                    "delay": 0,
                },
            )

            rows[key].update(upd)

        ordered_columns = [
            "task",
            "subject_id",
            "session",
            "block_1",
            "block_2",
            "block_3",
            "block_4",
            "block_5",
            "distraction",
            "immediate",
            "delay",
        ]

        if rows:
            wide = pd.DataFrame(rows.values())
            wide = wide[ordered_columns]
            wide = wide.sort_values(["subject_id", "session"]).reset_index(drop=True)
        else:
            wide = pd.DataFrame(columns=ordered_columns)

        flat = wide.copy()
        return wide, flat

    @staticmethod
    def _extract_version(df: pd.DataFrame) -> Optional[object]:
        for column in ("task_vers", "version"):
            if column in df.columns:
                series = df[column].dropna()
                if not series.empty:
                    return series.iloc[0]
        return None

    @staticmethod
    def _prepare_wl_dataframe(df: pd.DataFrame) -> pd.DataFrame:
        cleaned = df.copy()
        for column in ("response", "multichar_response"):
            if column in cleaned.columns:
                cleaned[column] = cleaned[column].fillna("").astype(str)
        return cleaned
