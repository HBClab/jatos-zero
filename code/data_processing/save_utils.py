import os
import re
import pandas as pd
import matplotlib.pyplot as plt
from termcolor import cprint
from pathlib import Path

class SAVE_EVERYTHING:
    def __init__(self):
        self.datadir = './data'
        self.sessions = {}  # Dictionary to track session numbers for each subjectID

    def _get_folder(self, subjID):
        try:
            subj_int = int(subjID)
        except (TypeError, ValueError):
            # Default to NE intervention for malformed IDs (logged upstream)
            return 'int', 'NE'
        if 7000 <= subj_int < 8000:
            return 'obs', 'UI'
        elif 8000 <= subj_int < 9000:
            return 'int', 'UI'
        else:
            return 'int', 'NE'

    def save_dfs(self, categories, task):
        cprint("saving task: " + task, "green")
        for subjectID, category, df in categories:
            folder1, folder2 = self._get_folder(subjectID)
            outdir = os.path.join(self.datadir, folder1, folder2, str(subjectID), task, 'data')
            session = df['session_number'][2]
            os.makedirs(outdir, exist_ok=True)
            csv_path = os.path.join(outdir, f"{subjectID}_ses-{session}_cat-{category}.csv")
            df.to_csv(csv_path, index=False)

            # Update the sessions dictionary
            if subjectID not in self.sessions:
                self.sessions[subjectID] = set()
            self.sessions[subjectID].add(session)

    def save_plots(self, plots, task):
        # Validate 'plots' for NoneType objects
        if plots is None or any(item is None for item in plots):
            raise ValueError("The 'plots' list contains NoneType objects, which are not allowed.")

        for subjectID, plot_obj in plots:
            # Ensure subjectID and plot_obj are valid
            if subjectID is None or plot_obj is None:
                raise ValueError(f"Invalid data in plots: subjectID={subjectID}, plot_obj={plot_obj}")

            if subjectID not in self.sessions:
                raise ValueError(f"No session information found for subjectID {subjectID}.")

            folder1, folder2 = self._get_folder(subjectID)
            outdir = os.path.join(self.datadir, folder1, folder2, str(subjectID), task, 'plot')
            os.makedirs(outdir, exist_ok=True)

            for session in self.sessions[subjectID]:
                if isinstance(plot_obj, tuple):  # Handle multiple plots
                    for i, individual_plot in enumerate(plot_obj):
                        plot_path = os.path.join(outdir, f"{subjectID}_ses-{session}_plot{i+1}.png")
                        individual_plot.figure.savefig(plot_path)
                        plt.close(individual_plot.figure)
                else:  # Handle a single plot
                    plot_path = os.path.join(outdir, f"{subjectID}_ses-{session}.png")
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

7000s- UI Observational
8000s- UI Intervention
9000s- NE Intervention

folder structure =
int -> UI/NE -> subID -> task -> data/plot
obs -> UI/NE -> subID -> task -> data/plot

"""
