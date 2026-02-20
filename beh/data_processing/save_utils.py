import re
import matplotlib.pyplot as plt
from termcolor import cprint
from pathlib import Path


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
            df.to_csv(csv_path, index=False)

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
                        individual_plot.figure.savefig(plot_path)
                        plt.close(individual_plot.figure)
                else:  # Handle a single plot
                    plot_path = outdir / f"{subject}_ses-{session}.png"
                    plot_obj.figure.savefig(plot_path)
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
