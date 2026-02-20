# Feature Spec -> Configurable local artifact saving under data/

## Context and objective
---
The current pipeline still contains hardcoded save path assumptions (including legacy obs/int and UI/NE routing). This feature defines how artifact saving becomes configurable while preserving baseline behavior for known tasks.

This spec is scoped to **known tasks only** and must stay compatible with the project main goal:
- full QC behavior remains intact for known tasks,
- unknown tasks remain ignored,
- `meta/` outputs still generate for known tasks.

## Decisions captured from clarification
---
- Canonical saved-data layout is:
  - `<data_root>/<subject>/<session>/<task>/data/*.csv`
- Plot artifact handling is included in this feature for de-dup behavior.
- Re-save policy is content-aware:
  - overwrite only when content changed,
  - do not rewrite identical files.
- For now, runtime behavior stays equivalent to full QC + meta for known tasks.
- Output toggles should be designed for future expansion (eventual toggleability of data/meta/qc outputs).

## Final ambiguity resolutions
---
- `data_root_path` and `data_folder_name` combine as:
  - `<data_root_path>/<data_folder_name>`
- CSV equality for de-dup is semantic row/column equality with minor float tolerance (not strict byte equality).
- Plot equality for de-dup is based on normalized plot metadata signatures (not rendered image bytes).
- Any temporary on-disk intermediates needed for meta reconstruction are cleaned in best-effort `finally` cleanup.

## In scope
---
- Replace hardcoded save path branches with configurable output root/folder behavior.
- Persist cleaned task-level CSV artifacts under the canonical path layout.
- Avoid unnecessary rewrites of unchanged data and plots.
- Preserve `meta/` generation behavior for known tasks.

## Out of scope
---
- Supporting new/unknown tasks.
- Changing QC domain logic or task membership rules.
- Redesigning plot content/format; only save/no-resave behavior is in scope.

## Functional requirements (FR)
---

### FR-01: Configurable data save destination
- The pipeline must support configuring:
  - whether persistent data saving is enabled,
  - the data folder name,
  - the data root path.
- Effective data save root must resolve to:
  - `<data_root_path>/<data_folder_name>`
- Configuration must not rely on environment-variable overrides for new keys unless explicitly introduced in a future feature.
- Defaults must preserve existing baseline behavior for current study execution.

### FR-02: Canonical artifact path structure
- For each known-task output rowset, the save path must resolve to:
  - `<data_root>/<subject>/<session>/<task>/data/<artifact_name>.csv`
- The implementation must remove hardcoded obs/int and UI/NE branching from persistence logic.
- Subject and session values must come from configured/default column mappings already used by the pipeline.

### FR-03: Known-task-only persistence
- Artifacts may be saved only for tasks in the authoritative known-task set.
- Unknown tasks must continue to produce no QC, no saved artifacts, no plots, and no meta outputs.

### FR-04: Data file de-dup save behavior
- Before writing a CSV output, the pipeline must detect whether the target file content would change.
- CSV comparison must use semantic data equality on normalized DataFrames:
  - stable column order,
  - stable row ordering rule,
  - numeric comparison with minor float tolerance.
- If semantic content is unchanged, it must skip rewriting the file.
- If content differs, it must overwrite the file atomically/safely.
- This behavior must reduce commit noise caused by deterministic re-runs.

### FR-05: Plot file de-dup save behavior
- Plot save logic must follow the same no-op-on-identical-content principle as CSV artifacts.
- Plot equality must be determined from normalized metadata signatures rather than raw image bytes.
- If a target plot file exists and the metadata signature is identical, do not rewrite.
- If changed, overwrite with updated content.

### FR-06: Meta output compatibility
- For known tasks, `meta/` outputs must continue to be generated as they are today.
- This feature must not regress current meta output naming/location semantics.
- If implementation requires temporary intermediates for meta assembly, those intermediates must be internal and must not alter user-facing output contracts.
- Temporary intermediates must be cleaned at end-of-task via best-effort cleanup in a `finally` path.

### FR-07: Forward-compatible output toggles
- The design must leave a clean extension point to separately toggle:
  - QC execution,
  - persistent saved data,
  - meta output generation,
  - plot generation.
- This feature does not need to expose all final toggles yet, but must avoid architecture that blocks that direction.

### FR-08: Logging and traceability
- Startup/runtime logs should clearly report effective artifact output configuration:
  - resolved data root,
  - resolved data folder name,
  - whether save de-dup is active.
- Per-artifact save logs should distinguish:
  - created,
  - updated (content changed),
  - skipped (identical content).

## Non-functional requirements (NFR)
---
- File comparisons should be efficient enough for routine CI/local runs.
- Save operations should remain deterministic across repeated runs with identical inputs.
- The feature must not materially increase memory/CPU usage outside expected file comparison overhead.

## Acceptance criteria
---
- Running a known task with unchanged input twice must not rewrite identical CSV outputs.
- Running a known task with unchanged input twice must not rewrite identical plot files.
- Modifying input that changes task outputs must rewrite only changed artifacts.
- Known-task runs must still generate the same `meta/` outputs as baseline behavior.
- Unknown-task input must still produce no artifacts and no meta outputs.
- Saved artifact paths must follow `<data_root>/<subject>/<session>/<task>/data/`.
- Effective data root path must resolve from `<data_root_path>/<data_folder_name>`.
- CSV files with only tolerated float jitter must be treated as unchanged.
- Plot saves must skip when metadata signature is unchanged, even if rendered byte output would differ.

## Open implementation notes
---
- Prefer centralizing save path resolution in one utility to avoid path drift across modules.
- Prefer content hashing or equivalent deterministic comparison for de-dup checks.
- Keep migration minimally invasive so existing tests and CI behavior remain stable.

## Implementation plan
---

***Checkpoint 1: Output config + path resolver foundation***
- [x] Extend config schema to add output save settings for data root/path naming (without breaking existing defaults).
- [x] Implement a single resolver utility that computes effective save root as `<data_root_path>/<data_folder_name>`.
- [x] Route `SAVE_EVERYTHING` and dependent callers to consume resolved paths instead of hardcoded obs/int + UI/NE branches.
- [x] A test: add config + resolver tests under `tests/config/` to validate defaults, path composition, and rejection of invalid values.

***Checkpoint 2: Canonical data layout migration***
- [x] Replace legacy path routing in `beh/data_processing/save_utils.py` with canonical `<root>/<subject>/<session>/<task>/data/` writes.
- [x] Ensure subject/session extraction uses pipeline defaults/task overrides and fails safely for malformed inputs.
- [x] Keep known-task-only behavior unchanged in orchestration (`beh/main_handler.py`).
- [x] A test: update/add e2e assertions in `tests/e2e/test_known_task_happy_path.py` and `tests/e2e/test_unknown_task_noop.py` for new directory structure and unknown-task no-op.

***Checkpoint 3: CSV de-dup with tolerance-aware compare***
- [x] Add a reusable CSV comparator utility that normalizes order and applies minor float tolerance.
- [x] Integrate comparator into save path so unchanged semantic CSV content is skipped and changed content is atomically rewritten.
- [x] Emit save outcome state (`created`/`updated`/`skipped`) for each artifact.
- [x] A test: add focused tests under `tests/data_processing/` proving skip-on-equivalent, rewrite-on-change, and tolerance behavior.

***Checkpoint 4: Plot metadata-signature de-dup***
- [x] Define normalized metadata signature extraction for plot outputs (task, subject, session, plot slot, and deterministic plot metadata fields).
- [x] Persist and compare signatures to skip unchanged plot writes; rewrite when signature changes.
- [x] Keep plot generation toggle semantics unchanged.
- [x] A test: extend e2e plot-enabled coverage in `tests/e2e/test_known_task_happy_path.py` to validate skip vs rewrite behavior via signatures.

***Checkpoint 5: Meta compatibility + temporary cleanup***
- [x] Ensure meta rebuild remains identical for known tasks with new save layout and de-dup flows.
- [x] Add best-effort `finally` cleanup for temporary artifacts used only for internal meta assembly.
- [x] Add startup/runtime logging for resolved output config and per-artifact save outcomes.
- [x] A test: add/extend integration tests ensuring meta files are produced unchanged and temporary files are cleaned after both success and failure paths.