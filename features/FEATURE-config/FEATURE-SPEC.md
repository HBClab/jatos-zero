# Feature -> Configurable Pipeline

## Purpose
---
Define the first configuration feature for the QA/QC pipeline so behavior is configurable while preserving the current study's baseline processing behavior.

This feature formalizes:
- where config is read from,
- how config is validated and applied,
- and what must remain unchanged for known tasks.

## Goal Alignment (Project Constitution)
---
This feature is constrained by `features/MAIN-GOAL.md`:
- Preserve baseline full-QC behavior for known tasks.
- Reject unknown/new tasks for execution.
- Keep `meta/` generation behavior unchanged for known-task processing.
- Do not expand the pipeline to support new tasks.
- Plot generation behavior is controlled only as enable/disable (not algorithm/content changes).

## Scope
---
In scope:
- Add a typed pipeline config model and loader.
- Define a single on-disk config file location and schema.
- Allow configuration of existing known-task processing controls.
- Allow configuration of QC parameters and subject/session column-name fallbacks.
- Enforce validation and deterministic fallback/default behavior.
- Add clear startup/runtime logging of effective config.
- Add plot enable/disable control (default disabled).

Out of scope:
- Adding support for unknown/new tasks.
- Refactoring domain QC algorithms.
- Plot algorithm/content changes.
- Non-local config providers (remote URLs, services, DB-backed config).

## Assumptions
---
- Runtime remains Python 3.10+.
- Config format is TOML.
- Feature behavior is implemented in/around `beh/main_handler.py` orchestration paths.

## Functional Requirements (FR)
---

### FR-001: Single config source of truth
The pipeline SHALL load configuration from one TOML file by default at `config/pipeline.toml`.

Acceptance criteria:
- The loader reads only `config/pipeline.toml`.
- The file is parsed once per process startup and reused as immutable runtime config.
- A startup log line reports the resolved config path.

### FR-002: Explicit config schema and versioning
The configuration SHALL declare `schema_version` and conform to a documented TOML schema.

Acceptance criteria:
- The root object includes `schema_version` (integer) and `pipeline` (object).
- Missing required keys fail validation before any task processing begins.
- Unknown keys at any nesting level are rejected with a clear validation error.
- Validation errors include the failing key path.

### FR-003: Known-task allowlist enforcement
Task execution SHALL be restricted to the authoritative known-task list in `beh/main_handler.py` and configured task subset in `config/pipeline.toml`.

Acceptance criteria:
- A task not in the authoritative list raises an explicit error and exits non-zero.
- Unknown task input produces no QC, no plots, no save outputs, and no meta rebuild trigger before exit.
- Known-task processing behavior remains unchanged when using baseline config values.

### FR-004: Domain/task routing configuration
The config SHALL support explicit domain routing and task-id mapping for a configurable subset of known tasks only.

Acceptance criteria:
- Config may include any subset of known tasks.
- Omitted known tasks are not run.
- Config maps each configured task to one of `cc`, `mem`, `ps`, `wl`.
- Config declares `task_ids` (list of integers) for each configured task.
- Runtime pull IDs are sourced from `pipeline.tasks.<TASK>.task_ids` rather than hardcoded IDs in `beh/main_handler.py`.
- The mapping must match implemented handlers in `beh/main_handler.py`.
- Config cannot define mappings for unknown tasks.

### FR-005: Runtime parameter overrides for existing QC paths
The config SHALL allow overrides for existing per-task QC parameters and subject/session column-name keys without changing algorithm structure.

Acceptance criteria:
- Configurable fields include currently hardcoded thresholds and RT limits used by existing QC entry points.
- Configurable fields include subject-id and session column-name keys used during orchestration.
- If any configurable field is omitted, the current hardcoded baseline value is used as fallback.
- Type mismatches or invalid ranges fail validation at startup.
- Effective values used for each task are logged at task start.

### FR-006: Output behavior constraints
The configuration SHALL not permit disabling required baseline outputs for known-task runs, while plot generation is opt-in.

Acceptance criteria:
- `meta/` generation remains enabled for known-task runs and cannot be disabled by config.
- Saved cleaned data outputs remain enabled for known-task runs and cannot be disabled by config.
- Plot generation is disabled by default.
- Plot generation can be enabled explicitly via config.

### FR-007: Config precedence and override rules
Runtime config resolution SHALL be deterministic and documented.

Acceptance criteria:
- Config is loaded exclusively from `config/pipeline.toml`; alternate config paths are not supported.
- If `config/pipeline.toml` does not exist, execution fails fast with actionable error text.
- Environment variable usage is allowed only for values already environment-backed in current code.
- New config keys introduced in this feature cannot be provided or overridden via environment variables.

### FR-008: Backward-compatible baseline mode
Running with baseline-equivalent config SHALL reproduce current behavior for known tasks.

Acceptance criteria:
- Existing known-task flow (`all` and single-task execution) remains behaviorally equivalent under baseline config.
- Existing file naming patterns for saved known-task outputs remain unchanged.
- Existing meta rebuild flow remains triggered for known-task runs as today.

### FR-009: Observability for effective config
The pipeline SHALL report effective configuration at startup and per-task boundary.

Acceptance criteria:
- Startup logs include schema version, config path, configured task set, and plot-enabled state.
- Per-task logs include domain route, resolved QC parameters, and resolved subject/session column keys.
- Logs redact sensitive values if any secret-like fields appear in config.

### FR-010: Validation test coverage
Automated tests SHALL cover config loading, validation, unknown-task errors, and subset task execution.

Acceptance criteria:
- Tests assert fail-fast behavior for malformed config and schema violations.
- Tests assert unknown keys fail with validation errors.
- Tests assert baseline defaults are applied when optional fields are omitted.
- Tests assert unknown-task inputs fail explicitly and produce no output side effects.
- Tests assert omitted known tasks are not run.
- Tests assert plot generation is off by default and only active when explicitly enabled.
- Tests assert known-task execution uses configured override values.

## Proposed Config Shape (Baseline)
---
```toml
schema_version = 1

[pipeline]
enable_plots = false

[pipeline.defaults.columns]
subject = "subject_id"
session = "session_number"

[pipeline.tasks.AF]
domain = "cc"
task_ids = [945, 960, 990, 898, 919, 932]

[pipeline.tasks.AF.qc]
threshold = 0.5
max_rt = 1800

[pipeline.tasks.FN]
domain = "mem"
task_ids = [950, 964, 987, 902, 923, 936]

[pipeline.tasks.FN.qc]
threshold = 0.5
max_rt = 4000
subject_column = "subject_id"
session_column = "session_number"

[pipeline.tasks.WL]
domain = "wl"
task_ids = [958, 972, 995, 910, 927, 944]
```

Notes:
- The tasks table is subset-based; omitted known tasks are intentionally not run.
- `task_ids` are required per configured task and are the runtime source of pull IDs.
- Task-level `subject_column`/`session_column` fallback order is: task override -> pipeline defaults -> in-code defaults.

## Definition of Done
---
This feature is complete when:
- FR-001 through FR-010 are implemented and verifiable.
- The config schema is documented with a baseline example.
- Validation failures are actionable and tested.
- Known-task baseline behavior remains preserved.

## Implementation Plan
---

***Checkpoint 1: Config Module Skeleton + TOML Loader***
- [x] Add a config module under `beh/config/` (for example: `beh/config/pipeline_config.py`) with typed models/dicts for schema version, pipeline defaults, tasks, and QC fields.
- [x] Implement TOML loading from `config/pipeline.toml` as the only supported config source.
- [x] Wire loader entry into `beh/main_handler.py` startup path without changing task execution behavior yet.
- [x] A test: add `tests/config/test_loader.py` to verify successful default-path load and fail-fast behavior when `config/pipeline.toml` is missing.

***Checkpoint 2: Strict Schema Validation***
- [x] Implement fail-fast validation for required keys and types (`schema_version`, `pipeline`, task/domain blocks).
- [x] Enforce hard errors on unknown keys at any nesting level with key-path details in error messages.
- [x] Enforce domain mapping validity (`cc`, `mem`, `ps`, `wl`) and reject unknown task definitions in config.
- [x] Enforce `task_ids` presence and type validation (non-empty integer list per configured task).
- [x] A test: add `tests/config/test_validation.py` cases for missing keys, bad types, and unknown-key failures.

***Checkpoint 3: Task Selection and Unknown-Task Runtime Errors***
- [x] Update orchestration in `beh/main_handler.py` so only configured known-task subset is runnable.
- [x] Make omitted known tasks not run when executing `all`.
- [x] Make unknown runtime task requests fail explicitly (non-zero/error path) before any side effects.
- [x] Remove hardcoded task ID values from `beh/main_handler.py` and source pull IDs from TOML `task_ids`.
- [x] A test: add/extend `tests/e2e/` coverage asserting omitted tasks are skipped and unknown tasks raise with no outputs written.

***Checkpoint 4: QC Param + Column Fallback Resolution***
- [x] Add resolver logic for per-task QC overrides (threshold/max_rt) with fallback to in-code defaults when missing.
- [x] Add resolver logic for `subject_column` and `session_column` with fallback order: task override -> pipeline defaults -> code defaults.
- [x] Thread resolved values into existing QC entry points in `beh/main_handler.py` while preserving baseline behavior when config is sparse.
- [x] A test: add `tests/config/test_resolution.py` asserting override behavior and fallback behavior for QC params and column names.

***Checkpoint 5: Plot Toggle and Output Constraints***
- [x] Add `pipeline.enable_plots` handling with default `false` and explicit `true` opt-in.
- [x] Gate plot generation calls in `beh/main_handler.py` by config flag while keeping saved data + meta behavior mandatory.
- [x] Validate that config cannot disable required outputs (data saves/meta rebuild).
- [x] A test: add/extend `tests/e2e/` coverage verifying no plot artifacts by default and plot artifacts only when enabled.

***Checkpoint 6: Precedence Rules, Logging, and Docs***
- [ ] Finalize config-source behavior so `config/pipeline.toml` is the only supported config path and missing file fails fast.
- [ ] Enforce env-var policy: only already-existing env-backed values remain env-backed; new config keys cannot be env overrides.
- [ ] Add startup/per-task logging for effective config (schema version, config path, configured tasks, resolved routing/params/columns, plot state).
- [ ] A test: add `tests/config/test_source_and_logging.py` for single-source config behavior and key log assertions.

***Checkpoint 7: Regression + CI Alignment***
- [ ] Add/adjust e2e regression tests to confirm baseline-known-task behavior remains intact under baseline TOML.
- [ ] Ensure all new tests fit repo structure under `tests/` and use deterministic fixtures.
- [ ] Run local quality gate (`python -m flake8 code`, `pytest`) and fix issues.
- [ ] A test: CI-equivalent local run passes lint + full test suite with config feature enabled.
