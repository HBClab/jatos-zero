import warnings
from data_processing.meta import META_RECREATE
from data_processing.pull_handler import Pull
from data_processing.cc_qc import CCqC
from data_processing.mem_qc import MEM_QC
from data_processing.ps_qc import PS_QC
from data_processing.utils import CONVERT_TO_CSV
from data_processing.wl_qc import WL_QC
from data_processing.plot_utils import CC_PLOTS, MEM_PLOTS, PS_PLOTS
from data_processing.save_utils import SAVE_EVERYTHING
from config.pipeline_config import load_runtime_pipeline_config as load_pipeline_config
import atexit
import os
from termcolor import cprint

warnings.filterwarnings("ignore")


class Handler:
    CODE_DEFAULT_SUBJECT_COLUMN = "subject_id"
    CODE_DEFAULT_SESSION_COLUMN = "session_number"
    CODE_DEFAULT_QC: dict[str, dict[str, float | int]] = {
        "AF": {"threshold": 0.5, "max_rt": 1800},
        "NF": {"threshold": 0.5, "max_rt": 1800},
        "NTS": {"threshold": 0.5, "max_rt": 1800},
        "ATS": {"threshold": 0.5, "max_rt": 1800},
        "NNB": {"threshold": 0.5, "max_rt": 1800},
        "VNB": {"threshold": 0.5, "max_rt": 1800},
        "FN": {"threshold": 0.5, "max_rt": 4000},
        "SM": {"threshold": 0.5, "max_rt": 2000},
        "PC": {"threshold": 0.6, "max_rt": 30000},
        "LC": {"threshold": 0.6, "max_rt": 30000},
        "DSST": {"threshold": 0.6, "max_rt": 125},
    }

    def __init__(self):
        self.task_order = [
            "AF",
            "NF",
            "NTS",
            "ATS",
            "NNB",
            "VNB",
            "WL",
            "DWL",
            "FN",
            "SM",
            "PC",
            "LC",
            "DSST",
        ]
        self.pipeline_config = load_pipeline_config(known_tasks=self.task_order)
        self.IDs = {
            task_name: task_config.task_ids
            for task_name, task_config in self.pipeline_config.pipeline.tasks.items()
        }
        self._log_startup_effective_config()

        self._meta_recreator = META_RECREATE()
        self._meta_rebuild_pending = False
        atexit.register(self._run_meta_if_needed)
        self._skipped_subjects: list[dict[str, object]] = []

    def configured_tasks(self) -> list[str]:
        configured = set(self.pipeline_config.pipeline.tasks.keys())
        return [task for task in self.task_order if task in configured]

    def _log_startup_effective_config(self) -> None:
        configured = self.configured_tasks()
        configured_repr = ",".join(configured) if configured else "<none>"
        cprint(
            "Pipeline startup config: "
            f"schema_version={self.pipeline_config.schema_version}, "
            f"config_path={self.pipeline_config.config_path}, "
            f"configured_tasks={configured_repr}, "
            f"enable_plots={self.pipeline_config.pipeline.enable_plots}",
            "cyan",
        )

    def _log_task_effective_config(self, task: str) -> None:
        route_config = self.pipeline_config.pipeline.tasks[task]
        qc = self.resolve_task_qc(task)
        subject_column, session_column = self.resolve_task_columns(task)
        cprint(
            f"Task {task} config: "
            f"domain={route_config.domain}, "
            f"task_ids={route_config.task_ids}, "
            f"qc.threshold={qc['threshold']}, "
            f"qc.max_rt={qc['max_rt']}, "
            f"subject_column={subject_column}, "
            f"session_column={session_column}",
            "cyan",
        )

    def _validate_runtime_task(self, task: str) -> None:
        if task not in self.task_order:
            known_tasks = ", ".join(sorted(self.task_order))
            raise ValueError(
                f"Unknown task '{task}'. Allowed known tasks: {known_tasks}"
            )
        if task not in self.IDs:
            raise ValueError(
                f"Task '{task}' is not enabled in config/pipeline.toml"
            )

    def run(self, task: str):
        if task == "all":
            return [self.pull(configured_task) for configured_task in self.configured_tasks()]
        return self.pull(task)

    def resolve_task_qc(self, task: str) -> dict[str, float | int | None]:
        self._validate_runtime_task(task)
        task_cfg = self.pipeline_config.pipeline.tasks[task].qc
        code_defaults = self.CODE_DEFAULT_QC.get(task, {})
        threshold = task_cfg.threshold
        if threshold is None:
            threshold = code_defaults.get("threshold")
        max_rt = task_cfg.max_rt
        if max_rt is None:
            max_rt = code_defaults.get("max_rt")
        return {"threshold": threshold, "max_rt": max_rt}

    def resolve_task_columns(self, task: str) -> tuple[str, str]:
        self._validate_runtime_task(task)
        task_cfg = self.pipeline_config.pipeline.tasks[task].qc
        default_columns = self.pipeline_config.pipeline.defaults.columns
        subject_column = (
            task_cfg.subject_column
            or default_columns.subject
            or self.CODE_DEFAULT_SUBJECT_COLUMN
        )
        session_column = (
            task_cfg.session_column
            or default_columns.session
            or self.CODE_DEFAULT_SESSION_COLUMN
        )
        return subject_column, session_column

    @staticmethod
    def _normalize_category_value(category):
        """Coerce QC categories to plain scalars so filenames remain clean."""
        if category is None:
            return None
        if hasattr(category, "item"):
            try:
                category = category.item()
            except Exception:
                pass
        try:
            return int(category)
        except (TypeError, ValueError):
            return category

    def _flush_skipped_subjects(self):
        """Log and clear any skipped-subject records accumulated during QC."""
        if self._skipped_subjects:
            formatted = ", ".join(
                f"{entry['subject_id']} (task={entry['task']}, session={entry['session'] if entry['session'] is not None else '<unknown>'}, reason={entry['reason']})"
                for entry in self._skipped_subjects
            )
            cprint(f"Skipped subjects: {formatted}", "red")
            self._skipped_subjects.clear()

    def _run_meta_if_needed(self, force: bool = False):
        """
        Rebuild aggregate CSVs from the saved per-participant artifacts.

        Args:
            force: when True, rebuild even if no dirty flag is set. This
                   is used for the explicit "final step" of the pipeline.
        """
        if not force and not self._meta_rebuild_pending:
            return

        self._flush_skipped_subjects()
        for domain in ("cc", "mem", "ps", "wl"):
            self._meta_recreator.recreate(domain)
        self._meta_rebuild_pending = False

    def _save_task_artifacts(self, task: str, categories, plots) -> None:
        save_instance = SAVE_EVERYTHING()
        save_instance.save_dfs(categories=categories, task=task)
        if self.pipeline_config.pipeline.enable_plots:
            save_instance.save_plots(plots=plots, task=task)

    @staticmethod
    def _get_value_with_fallback(
        df,
        preferred_column: str,
        fallback_columns: list[str],
        preferred_index: int = 0,
    ):
        columns = [preferred_column] + [
            column for column in fallback_columns if column != preferred_column
        ]
        for column in columns:
            if column not in df.columns:
                continue
            series = df[column]
            if series.empty:
                return None
            if len(series) > preferred_index:
                return series.iloc[preferred_index]
            return series.iloc[0]
        return None

    @classmethod
    def _apply_runtime_column_aliases(
        cls,
        df,
        subject_column: str,
        session_column: str,
    ):
        normalized = df
        if (
            subject_column in normalized.columns
            and cls.CODE_DEFAULT_SUBJECT_COLUMN not in normalized.columns
        ):
            normalized = normalized.copy()
            normalized[cls.CODE_DEFAULT_SUBJECT_COLUMN] = normalized[subject_column]
        if (
            session_column in normalized.columns
            and cls.CODE_DEFAULT_SESSION_COLUMN not in normalized.columns
        ):
            normalized = normalized.copy()
            normalized[cls.CODE_DEFAULT_SESSION_COLUMN] = normalized[session_column]
        return normalized

    def pull(self, task):
        self._validate_runtime_task(task)
        self._log_task_effective_config(task)
        pull_instance = Pull(
            self.IDs[task],
            tease="WEEEEEEEEEEEEEE",
            token=os.getenv("JATOS_TOKEN"),
            taskName=task,
            proxy=False
        )

        txt_dfs = pull_instance.load(days_ago=127)
        return self.convert_to_csv(txt_dfs, task)

    def convert_to_csv(self, txt_dfs, task):
        self._validate_runtime_task(task)
        csv_instance = CONVERT_TO_CSV(task)
        csv_dfs = csv_instance.convert_to_csv(txt_dfs)
        result = self.choose_construct(csv_dfs, task)
        self._meta_rebuild_pending = True
        self._run_meta_if_needed(force=True)
        return csv_dfs, result

    def choose_construct(self, csv_dfs, task):
        if task in ['NF', 'AF', 'NTS', 'ATS', 'NNB', 'VNB']:
            return self.qc_cc_dfs(csv_dfs, task)
        elif task in ['FN', 'SM']:
            return self.qc_mem_dfs(csv_dfs, task)
        elif task in ['WL', 'DWL']:
            return self.qc_wl_dfs(csv_dfs, task)
        elif task in ['PC', 'LC', 'DSST']:
            return self.qc_ps_dfs(csv_dfs, task)
        else:
            return None

    def qc_cc_dfs(self, dfs, task):
        categories, plots = [], []
        plot_instance = CC_PLOTS()
        qc_params = self.resolve_task_qc(task)
        subject_column, session_column = self.resolve_task_columns(task)
        # pick the grouping column for accuracy/RT
        cond_col = "condition" if task in ["AF", "NF", "NNB", "VNB"] else "block_cond"

        # Configure QC with task-specific column names/symbols
        qc_instance = CCqC(
            task,
            MAXRT=qc_params["max_rt"],
            RT_COLUMN_NAME="response_time",
            ACC_COLUMN_NAME="correct",
            CORRECT_SYMBOL=1,
            INCORRECT_SYMBOL=0,
            COND_COLUMN_NAME=cond_col,
        )

        for df in dfs:
            normalized_df = self._apply_runtime_column_aliases(
                df,
                subject_column=subject_column,
                session_column=session_column,
            )
            subject = self._get_value_with_fallback(
                normalized_df,
                preferred_column=subject_column,
                fallback_columns=[self.CODE_DEFAULT_SUBJECT_COLUMN],
                preferred_index=0,
            )
            session = self._get_value_with_fallback(
                normalized_df,
                preferred_column=session_column,
                fallback_columns=[self.CODE_DEFAULT_SESSION_COLUMN, "session"],
                preferred_index=0,
            )

            acc_by: dict = {}
            try:
                # --- Run QC + plots (kept as you had it) ---
                if task in ["AF", "NF"]:
                    category, acc_by = qc_instance.cc_qc(
                        normalized_df,
                        threshold=qc_params["threshold"],
                    )
                    plot = plot_instance.af_nf_plot(normalized_df)
                elif task in ["NNB", "VNB"]:
                    category, acc_by = qc_instance.cc_qc(
                        normalized_df,
                        threshold=qc_params["threshold"],
                    )
                    plot = plot_instance.nnb_vnb_plot(normalized_df)
                else:
                    category, acc_by = qc_instance.cc_qc(
                        normalized_df,
                        threshold=qc_params["threshold"],
                        TS=True,
                    )
                    plot = plot_instance.ats_nts_plot(normalized_df)
            except ValueError as err:
                message = str(err)
                if "No 'test' block rows available for plotting" in message:
                    cprint(
                        f"Skipping subject {subject} for task {task}: {message}",
                        "yellow",
                    )
                    self._skipped_subjects.append(
                        {
                            "task": task,
                            "subject_id": subject,
                            "session": session,
                            "reason": message,
                        }
                    )
                    continue
                raise

            normalized_category = self._normalize_category_value(category)
            categories.append([subject, normalized_category, normalized_df])
            plots.append([subject, plot])

        self._save_task_artifacts(task=task, categories=categories, plots=plots)

        return categories, plots

    def qc_ps_dfs(self, dfs, task):
        categories, plots = [], []
        plot_instance = PS_PLOTS()
        qc_params = self.resolve_task_qc(task)
        subject_column, session_column = self.resolve_task_columns(task)
        if task in ['PC', 'LC']:
            ps_instance = PS_QC('response_time', 'correct', 1, 0, 'block_c', qc_params["max_rt"])
            for df in dfs:
                normalized_df = self._apply_runtime_column_aliases(
                    df,
                    subject_column=subject_column,
                    session_column=session_column,
                )
                subject = self._get_value_with_fallback(
                    normalized_df,
                    preferred_column=subject_column,
                    fallback_columns=[self.CODE_DEFAULT_SUBJECT_COLUMN],
                    preferred_index=1,
                )
                category, _ = ps_instance.ps_qc(normalized_df, threshold=qc_params["threshold"])
                if task == 'PC':
                    plot = plot_instance.lc_plot(normalized_df)
                elif task == 'LC':
                    plot = plot_instance.lc_plot(normalized_df)
                normalized_category = self._normalize_category_value(category)
                categories.append([subject, normalized_category, normalized_df])
                plots.append([subject, plot])

        else:
            ps_instance = PS_QC('block_dur', 'correct', 1, 0, 'block_c', qc_params["max_rt"])
            for df in dfs:
                normalized_df = self._apply_runtime_column_aliases(
                    df,
                    subject_column=subject_column,
                    session_column=session_column,
                )
                subject = self._get_value_with_fallback(
                    normalized_df,
                    preferred_column=subject_column,
                    fallback_columns=[self.CODE_DEFAULT_SUBJECT_COLUMN],
                    preferred_index=1,
                )
                category, _ = ps_instance.ps_qc(
                    normalized_df,
                    threshold=qc_params["threshold"],
                    DSST=True,
                )
                plot = plot_instance.dsst_plot(normalized_df)
                normalized_category = self._normalize_category_value(category)
                categories.append([subject, normalized_category, normalized_df])
                plots.append([subject, plot])

        self._save_task_artifacts(task=task, categories=categories, plots=plots)

        return categories, plots

    def qc_mem_dfs(self, dfs, task):
        plot_instance = MEM_PLOTS()
        categories, plots = [], []
        qc_params = self.resolve_task_qc(task)
        subject_column, session_column = self.resolve_task_columns(task)
        if task in ['FN']:
            mem_instance = MEM_QC('response_time', 'correct', 1, 0, 'block_c', qc_params["max_rt"])
            for df in dfs:
                normalized_df = self._apply_runtime_column_aliases(
                    df,
                    subject_column=subject_column,
                    session_column=session_column,
                )
                subject = self._get_value_with_fallback(
                    normalized_df,
                    preferred_column=subject_column,
                    fallback_columns=[self.CODE_DEFAULT_SUBJECT_COLUMN],
                    preferred_index=1,
                )
                session = self._get_value_with_fallback(
                    normalized_df,
                    preferred_column=session_column,
                    fallback_columns=[self.CODE_DEFAULT_SESSION_COLUMN, "session"],
                    preferred_index=1,
                )

                try:
                    category, _ = mem_instance.fn_sm_qc(
                        normalized_df,
                        threshold=qc_params["threshold"],
                    )
                    plot = plot_instance.fn_plot(normalized_df)
                except ValueError as err:
                    message = str(err)
                    if "No 'test' block rows available for MEM plotting" in message:
                        cprint(
                            f"Skipping subject {subject} for task {task}: {message}",
                            "yellow",
                        )
                        self._skipped_subjects.append(
                            {
                                "task": task,
                                "subject_id": subject,
                                "session": session,
                                "reason": message,
                            }
                        )
                        continue
                    raise
                normalized_category = self._normalize_category_value(category)
                categories.append([subject, normalized_category, normalized_df])
                plots.append([subject, plot])
        elif task in ['SM']:
            mem_instance = MEM_QC('response_time', 'correct', 1, 0, 'block_c', qc_params["max_rt"])
            for df in dfs:
                normalized_df = self._apply_runtime_column_aliases(
                    df,
                    subject_column=subject_column,
                    session_column=session_column,
                )
                subject = self._get_value_with_fallback(
                    normalized_df,
                    preferred_column=subject_column,
                    fallback_columns=[self.CODE_DEFAULT_SUBJECT_COLUMN],
                    preferred_index=1,
                )
                session = self._get_value_with_fallback(
                    normalized_df,
                    preferred_column=session_column,
                    fallback_columns=[self.CODE_DEFAULT_SESSION_COLUMN, "session"],
                    preferred_index=1,
                )

                try:
                    category, _ = mem_instance.fn_sm_qc(
                        normalized_df,
                        threshold=qc_params["threshold"],
                    )
                    plot = plot_instance.sm_plot(normalized_df)
                except ValueError as err:
                    message = str(err)
                    if "No 'test' block rows available for MEM plotting" in message:
                        cprint(
                            f"Skipping subject {subject} for task {task}: {message}",
                            "yellow",
                        )
                        self._skipped_subjects.append(
                            {
                                "task": task,
                                "subject_id": subject,
                                "session": session,
                                "reason": message,
                            }
                        )
                        continue
                    raise
                normalized_category = self._normalize_category_value(category)
                categories.append([subject, normalized_category, normalized_df])
                plots.append([subject, plot])
        self._save_task_artifacts(task=task, categories=categories, plots=plots)

        return categories, plots

    def qc_wl_dfs(self, dfs, task):
        categories, plots = [], []
        plot_instance = MEM_PLOTS()
        subject_column, session_column = self.resolve_task_columns(task)

        if task == 'WL':
            for df in dfs:
                normalized_df = self._apply_runtime_column_aliases(
                    df,
                    subject_column=subject_column,
                    session_column=session_column,
                )
                subject = self._get_value_with_fallback(
                    normalized_df,
                    preferred_column=subject_column,
                    fallback_columns=[self.CODE_DEFAULT_SUBJECT_COLUMN],
                    preferred_index=1,
                )
                version = normalized_df['task_vers'].iloc[1]

                wl_instance = WL_QC()
                df_all, category = wl_instance.wl_qc(normalized_df, version)
                plot = plot_instance.wl_plot(df_all)

                normalized_category = self._normalize_category_value(category)
                categories.append([subject, normalized_category, normalized_df])
                plots.append([subject, plot])

        elif task == 'DWL':
            for df in dfs:
                normalized_df = self._apply_runtime_column_aliases(
                    df,
                    subject_column=subject_column,
                    session_column=session_column,
                )
                subject = self._get_value_with_fallback(
                    normalized_df,
                    preferred_column=subject_column,
                    fallback_columns=[self.CODE_DEFAULT_SUBJECT_COLUMN],
                    preferred_index=1,
                )
                version = normalized_df['task_vers'].iloc[1]

                dwl_instance = WL_QC()
                df_all, category = dwl_instance.dwl_qc(normalized_df, version)
                plot = plot_instance.dwl_plot(df_all)

                normalized_category = self._normalize_category_value(category)
                categories.append([subject, normalized_category, normalized_df])
                plots.append([subject, plot])

        # maybe: materialize wl_master back to columns if you prefer
        # wl_master_out = self.wl_master.reset_index()

        self._save_task_artifacts(task=task, categories=categories, plots=plots)

        return categories, plots


if __name__ == '__main__':
    import sys

    if len(sys.argv) < 2:
        raise SystemExit("Usage: python beh/main_handler.py <TASK|all>")

    instance = Handler()
    try:
        instance.run(sys.argv[1])
    except ValueError as err:
        cprint(str(err), "red")
        raise SystemExit(1)
