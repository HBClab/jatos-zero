import re
import json
import hashlib
import matplotlib.pyplot as plt
from termcolor import cprint
from pathlib import Path
import pandas as pd
import numpy as np

from data_processing.csv_compare import semantic_csv_equal


class SAVE_EVERYTHING:
    def __init__(self):
        self.datadir = './data'
        # Track observed sessions for subject/task so plot paths can align.
        self.sessions: dict[tuple[str, str], set[str]] = {}

    @staticmethod
    def _normalize_scalar(value):
        if value is None:
            return None
        if hasattr(value, "item"):
            try:
                value = value.item()
            except Exception:
                pass
        if isinstance(value, str):
            value = value.strip()
            if not value:
                return None
            return value
        return str(value)

    @classmethod
    def _extract_session_value(cls, df):
        for column_name in ("session_number", "session"):
            if column_name not in df.columns:
                continue
            series = df[column_name].dropna()
            if series.empty:
                continue
            session = cls._normalize_scalar(series.iloc[0])
            if session is not None:
                return session
        return None

    def _task_data_dir(self, subject_id: str, session: str, task: str) -> Path:
        return Path(self.datadir) / subject_id / session / task / "data"

    def _task_plot_dir(self, subject_id: str, session: str, task: str) -> Path:
        return Path(self.datadir) / subject_id / session / task / "plot"

    @staticmethod
    def _atomic_write_text(content: str, target_path: Path) -> None:
        tmp_path = target_path.with_suffix(target_path.suffix + ".tmp")
        tmp_path.write_text(content, encoding="utf-8")
        tmp_path.replace(target_path)

    @staticmethod
    def _atomic_write_csv(df, target_path: Path) -> None:
        tmp_path = target_path.with_suffix(target_path.suffix + ".tmp")
        df.to_csv(tmp_path, index=False)
        tmp_path.replace(target_path)

    @staticmethod
    def _atomic_write_figure(figure, target_path: Path) -> None:
        tmp_path = target_path.with_name(
            f"{target_path.stem}.tmp{target_path.suffix}"
        )
        figure.savefig(tmp_path)
        tmp_path.replace(target_path)

    @staticmethod
    def _round_float(value, precision: int = 8):
        return round(float(value), precision)

    @classmethod
    def _normalize_numeric_sequence(cls, values):
        normalized = []
        for value in values:
            if pd.isna(value):
                normalized.append(None)
            elif isinstance(value, (int, float, np.integer, np.floating)):
                normalized.append(cls._round_float(value))
            else:
                normalized.append(str(value))
        return normalized

    @classmethod
    def _axis_metadata(cls, axis) -> dict:
        legend = axis.get_legend()
        legend_labels = []
        if legend is not None:
            legend_labels = [text.get_text() for text in legend.get_texts()]

        line_payload = []
        for line in axis.lines:
            line_payload.append(
                {
                    "x": cls._normalize_numeric_sequence(line.get_xdata(orig=False)),
                    "y": cls._normalize_numeric_sequence(line.get_ydata(orig=False)),
                    "label": line.get_label(),
                }
            )

        patch_payload = []
        for patch in axis.patches:
            if all(
                hasattr(patch, attr)
                for attr in ("get_x", "get_y", "get_width", "get_height")
            ):
                patch_payload.append(
                    {
                        "x": cls._round_float(patch.get_x()),
                        "y": cls._round_float(patch.get_y()),
                        "width": cls._round_float(patch.get_width()),
                        "height": cls._round_float(patch.get_height()),
                    }
                )
                continue

            path = patch.get_path()
            vertices = path.vertices if path is not None else []
            patch_payload.append(
                {
                    "vertices_hash": cls._hash_payload(
                        [
                            (
                                cls._round_float(vertex[0]),
                                cls._round_float(vertex[1]),
                            )
                            for vertex in vertices
                        ]
                    )
                }
            )

        collection_payload = []
        for collection in axis.collections:
            if not hasattr(collection, "get_offsets"):
                continue
            offsets = collection.get_offsets()
            points = []
            if offsets is not None and len(offsets) > 0:
                points = [
                    (
                        int(round(float(point[0]))),
                        cls._round_float(point[1]),
                    )
                    for point in offsets
                ]
                points = sorted(points)
            collection_payload.append(points)

        return {
            "title": axis.get_title(),
            "xlabel": axis.get_xlabel(),
            "ylabel": axis.get_ylabel(),
            "xticks": [tick.get_text() for tick in axis.get_xticklabels()],
            "yticks": [tick.get_text() for tick in axis.get_yticklabels()],
            "legend_labels": legend_labels,
            "line_hash": cls._hash_payload(line_payload),
            "patch_hash": cls._hash_payload(patch_payload),
            "collection_hash": cls._hash_payload(collection_payload),
        }

    @staticmethod
    def _hash_payload(payload) -> str:
        as_json = json.dumps(payload, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(as_json.encode("utf-8")).hexdigest()

    @classmethod
    def _build_plot_signature(
        cls,
        *,
        task: str,
        subject: str,
        session: str,
        plot_slot: str,
        axis,
    ) -> dict:
        figure = axis.figure
        figure.set_dpi(figure.get_dpi())
        figure.canvas.draw()
        return {
            "task": task,
            "subject": subject,
            "session": session,
            "plot_slot": plot_slot,
            "figure_size": [
                cls._round_float(figure.get_figwidth()),
                cls._round_float(figure.get_figheight()),
            ],
            "axis_metadata": cls._axis_metadata(axis),
        }

    @staticmethod
    def _plot_signature_path(plot_path: Path) -> Path:
        return plot_path.with_suffix(plot_path.suffix + ".sig.json")

    @classmethod
    def _write_plot_if_changed(cls, axis, plot_path: Path, signature: dict) -> str:
        signature_path = cls._plot_signature_path(plot_path)
        signature_hash = cls._hash_payload(signature)

        if plot_path.exists() and signature_path.exists():
            try:
                existing_signature = json.loads(
                    signature_path.read_text(encoding="utf-8")
                )
                existing_hash = existing_signature.get("signature_hash")
                if existing_hash == signature_hash:
                    return "skipped"
            except (json.JSONDecodeError, OSError):
                pass

        outcome = "created" if not plot_path.exists() else "updated"
        cls._atomic_write_figure(axis.figure, plot_path)
        payload = {
            "signature_hash": signature_hash,
            "signature": signature,
        }
        cls._atomic_write_text(
            json.dumps(payload, sort_keys=True, indent=2),
            signature_path,
        )
        return outcome

    def _write_csv_if_changed(self, df, csv_path: Path) -> str:
        if not csv_path.exists():
            self._atomic_write_csv(df, csv_path)
            return "created"

        existing_df = pd.read_csv(csv_path)
        if semantic_csv_equal(existing_df, df):
            return "skipped"

        self._atomic_write_csv(df, csv_path)
        return "updated"

    def save_dfs(self, categories, task):
        cprint("saving task: " + task, "green")
        for subjectID, category, df in categories:
            subject = self._normalize_scalar(subjectID)
            session = self._extract_session_value(df)
            if subject is None or session is None:
                cprint(
                    f"Skipping save for task {task}: invalid subject/session "
                    f"(subject={subjectID}, session={session})",
                    "yellow",
                )
                continue

            outdir = self._task_data_dir(subject, session, task)
            outdir.mkdir(parents=True, exist_ok=True)
            csv_path = outdir / f"{subject}_ses-{session}_cat-{category}.csv"
            outcome = self._write_csv_if_changed(df, csv_path)
            outcome_color = {
                "created": "green",
                "updated": "yellow",
                "skipped": "cyan",
            }.get(outcome, "green")
            cprint(f"[{outcome}] csv artifact: {csv_path}", outcome_color)

            session_key = (subject, task)
            if session_key not in self.sessions:
                self.sessions[session_key] = set()
            self.sessions[session_key].add(session)

    def save_plots(self, plots, task):
        # Validate 'plots' for NoneType objects
        if plots is None or any(item is None for item in plots):
            raise ValueError("The 'plots' list contains NoneType objects, which are not allowed.")

        for subjectID, plot_obj in plots:
            # Ensure subjectID and plot_obj are valid
            if subjectID is None or plot_obj is None:
                raise ValueError(f"Invalid data in plots: subjectID={subjectID}, plot_obj={plot_obj}")

            subject = self._normalize_scalar(subjectID)
            session_key = (subject, task)
            if subject is None or session_key not in self.sessions:
                cprint(
                    f"Skipping plot save for task {task}: no session information for "
                    f"subject={subjectID}",
                    "yellow",
                )
                continue

            for session in sorted(self.sessions[session_key], key=str):
                outdir = self._task_plot_dir(subject, session, task)
                outdir.mkdir(parents=True, exist_ok=True)
                if isinstance(plot_obj, tuple):  # Handle multiple plots
                    for i, individual_plot in enumerate(plot_obj):
                        plot_path = outdir / f"{subject}_ses-{session}_plot{i+1}.png"
                        signature = self._build_plot_signature(
                            task=task,
                            subject=subject,
                            session=session,
                            plot_slot=f"plot{i+1}",
                            axis=individual_plot,
                        )
                        outcome = self._write_plot_if_changed(
                            individual_plot,
                            plot_path,
                            signature,
                        )
                        outcome_color = {
                            "created": "green",
                            "updated": "yellow",
                            "skipped": "cyan",
                        }.get(outcome, "green")
                        cprint(f"[{outcome}] plot artifact: {plot_path}", outcome_color)
                        plt.close(individual_plot.figure)
                else:  # Handle a single plot
                    plot_path = outdir / f"{subject}_ses-{session}.png"
                    signature = self._build_plot_signature(
                        task=task,
                        subject=subject,
                        session=session,
                        plot_slot="plot",
                        axis=plot_obj,
                    )
                    outcome = self._write_plot_if_changed(plot_obj, plot_path, signature)
                    outcome_color = {
                        "created": "green",
                        "updated": "yellow",
                        "skipped": "cyan",
                    }.get(outcome, "green")
                    cprint(f"[{outcome}] plot artifact: {plot_path}", outcome_color)
                    plt.close(plot_obj.figure)


def normalize_category_exports(
    base_dir: str | Path = "data",
    dry_run: bool = False,
) -> dict[str, list]:
    """
    Rename tuple-suffixed QC CSV exports so filenames carry only the scalar category.

    For each file like ``*_cat-(1, {...}).csv`` we either:
      * rename it to ``*_cat-1.csv`` when no normalized file already exists, or
      * delete the tuple version if the normalized file is already present.

    Args:
        base_dir: Root directory to scan (defaults to project ``data`` folder).
        dry_run: When True, report planned actions without renaming/deleting.

    Returns:
        dict with keys ``renamed`` (list of (old, new) Paths), ``deleted`` (list of Paths),
        and ``skipped`` (Paths that matched the pattern but could not be normalized).
    """
    base_path = Path(base_dir).expanduser()
    if not base_path.exists():
        return {"renamed": [], "deleted": [], "skipped": []}

    matches = sorted(base_path.rglob("*.csv"))
    renamed: list[tuple[Path, Path]] = []
    deleted: list[Path] = []
    skipped: list[Path] = []

    for csv_path in matches:
        name = csv_path.name
        if "cat-" not in name:
            continue
        prefix_part, suffix_part = name.split("cat-", 1)
        if not suffix_part:
            continue

        first_char = suffix_part[0]
        if first_char == "(":
            cat_match = re.match(r"\((\d+)", suffix_part)
        elif first_char == "[":
            cat_match = re.match(r"\[(\d+)", suffix_part)
        else:
            continue

        if not cat_match:
            skipped.append(csv_path)
            continue

        category = cat_match.group(1)
        new_name = f"{prefix_part}cat-{category}{csv_path.suffix}"
        target_path = csv_path.with_name(new_name)

        if target_path.exists():
            deleted.append(csv_path)
            if not dry_run:
                try:
                    csv_path.unlink()
                except FileNotFoundError:
                    continue
            continue

        renamed.append((csv_path, target_path))
        if not dry_run:
            try:
                csv_path.rename(target_path)
            except FileNotFoundError:
                continue

    if renamed or deleted:
        msg = (
            f"Normalized QC exports: {len(renamed)} renamed, "
            f"{len(deleted)} duplicates removed."
        )
        cprint(msg, "yellow")

    if skipped:
        cprint(f"Skipped {len(skipped)} files; inspect patterns.", "red")

    return {"renamed": renamed, "deleted": deleted, "skipped": skipped}


"""

canonical folder structure =
<data_root>/<subject>/<session>/<task>/data|plot

"""
