# Chore Spec -> Allow missing session values

## Context and objective
---
Some historical subject payloads have no session value and cannot be corrected at source retroactively. The pipeline currently skips these rows during artifact persistence, which causes data loss and downstream incompleteness.

This chore defines deterministic fallback behavior so rows with missing session can still be processed and saved, while clearly signaling manual follow-up is needed.

## Decisions captured from clarification
---
- Placeholder session uniqueness/max tracking is **per subject + task**.
- Current max session is computed from **current in-memory payload + existing saved artifacts**.
- If multiple missing-session records exist in one run, assign **incrementing placeholders** (`max+1`, `max+2`, ...).
- Missing-session handling uses **soft warning + report file** (processing continues).

## Scope
---
In scope:
- Detect missing session values for known-task records that otherwise qualify for saving.
- Assign deterministic placeholder sessions with no duplicates per subject+task.
- Persist outputs using assigned placeholders in canonical artifact paths.
- Emit warnings and produce a machine-readable missing-session report for human adjustment.
- Add/extend tests for fallback assignment, warning/report generation, and duplicate prevention.

Out of scope:
- Changing QC algorithms or thresholds.
- Changing known-task/unknown-task routing policy.
- Retroactively editing historical upstream JATOS source data.
- Introducing new task support or cross-task session harmonization.

## Functional requirements (FR)
---

### FR-01: Missing-session detection at save boundary
The pipeline SHALL detect records where session is unavailable after configured/session-column fallback resolution.

Acceptance criteria:
- Detection occurs before save path construction for CSV/plot artifacts.
- Existing subject/session column fallback behavior remains intact.
- Missing-session status is evaluated per record being persisted.

### FR-02: Placeholder session assignment policy
For missing-session records, the pipeline SHALL assign a placeholder session sequence per subject+task beginning at `current_max_session + 1`.

Acceptance criteria:
- `current_max_session` includes both:
	- sessions found in this run's in-memory payload for the same subject+task,
	- sessions already present in saved artifacts under the resolved data root for that subject+task.
- If no existing session is found, assignment starts at `1`.
- Placeholders are monotonic within run context for each subject+task.

### FR-03: Duplicate prevention
Placeholder assignment SHALL guarantee no duplicate session value collisions for a given subject+task path.

Acceptance criteria:
- Assignment checks both in-memory and on-disk observed sessions before finalizing placeholder values.
- Multiple missing-session records in one run receive distinct incrementing placeholders.
- Save path collisions caused solely by duplicate placeholder sessions are prevented.

### FR-04: Persistence compatibility
Assigned placeholder sessions SHALL be used consistently for data and plot output paths.

Acceptance criteria:
- Saved paths continue to follow canonical layout:
	- `<data_root>/<subject>/<session>/<task>/data/*.csv`
	- `<data_root>/<subject>/<session>/<task>/plot/*.png`
- Filename conventions continue to include `ses-<session>`.
- Existing dedup logic (`created`/`updated`/`skipped`) remains functional.

### FR-05: Soft warning behavior
The pipeline SHALL continue processing while clearly warning on each missing-session assignment.

Acceptance criteria:
- Warning includes at least task, subject, and assigned placeholder session.
- Processing does not hard-fail solely due to missing session.
- Warning text explicitly requests human adjustment/review.

### FR-06: Missing-session report artifact
The pipeline SHALL emit a machine-readable report of all placeholder assignments for human follow-up.

Acceptance criteria:
- A report is written per run when at least one placeholder assignment occurs.
- Report contains, at minimum: task, subject_id, assigned_session, reason, and timestamp/run-context field.
- Report writing is best-effort and does not cancel task processing if report write fails (warning emitted).

### FR-07: Meta rebuild compatibility
Meta recreation SHALL continue to include records saved under placeholder sessions.

Acceptance criteria:
- Meta rebuild runs unchanged in orchestration flow for known tasks.
- Records saved with placeholder sessions appear in corresponding `meta/` outputs.
- No regression in existing meta file naming/location.

### FR-08: Known-task behavior boundary
This feature SHALL not alter unknown-task no-op behavior.

Acceptance criteria:
- Unknown tasks still fail/skip as currently defined by pipeline policy.
- Missing-session assignment logic only applies within known-task processing paths.

## Non-functional requirements (NFR)
---
- Placeholder assignment must be deterministic for identical input + filesystem state.
- Additional filesystem scanning for session maxima should remain lightweight for typical run sizes.
- Warning/report output should be clear enough for analyst triage without inspecting raw code logs.

## Acceptance test matrix
---
- Known task with valid session values saves unchanged from baseline behavior.
- Known task with one missing-session record assigns exactly `max+1` and saves artifacts.
- Known task with multiple missing-session records for same subject+task assigns unique incrementing placeholders.
- Existing on-disk sessions are respected when computing next placeholder.
- Placeholder-assigned records appear in regenerated `meta/` aggregates.
- Warnings are emitted and include task/subject/assigned session.
- Missing-session report file is generated and contains required fields.
- Unknown task behavior remains unchanged.

## Open implementation notes
---
- Prefer centralizing placeholder/session allocation in one utility used by save paths.
- Reuse existing session extraction/normalization logic where possible to avoid path divergence.
- Keep logging and report schema stable to support analyst workflows.

## Definition of Done
---
This chore is complete when:
- FR-01 through FR-08 are implemented and verifiable.
- NFRs are satisfied for deterministic behavior and reporting clarity.
- New/updated tests pass locally with no regression to known-task baseline flows.

## Implementation plan
---

***Checkpoint 1: Session allocation utility foundation***
- [x] Add a centralized helper to resolve/assign session values for save-time records.
- [x] Implement missing-session detection and placeholder generation policy (`max+1`) per subject+task.
- [x] Include aggregation of observed sessions from in-memory payload and existing artifact paths.
- [x] A test: add focused unit tests for allocation behavior, including empty-state start at `1`.

***Checkpoint 2: Save pipeline integration***
- [x] Integrate allocator into CSV save flow in `beh/data_processing/save_utils.py`.
- [x] Ensure session tracking for plot saving uses assigned placeholders consistently.
- [x] Preserve canonical pathing and dedup behavior (`created`/`updated`/`skipped`).
- [x] A test: extend save-utils tests to verify persistence with missing sessions instead of skip.

***Checkpoint 3: Warning and report artifact***
- [x] Add structured warning output for every placeholder assignment.
- [x] Add a machine-readable report writer for missing-session events (run-scoped artifact).
- [x] Ensure report-write failure is non-fatal and logged.
- [x] A test: add coverage for warning content and report-file schema/rows.

***Checkpoint 4: Meta compatibility and regression coverage***
- [x] Validate meta recreation includes placeholder-session records without orchestration changes.
- [x] Add/extend e2e tests to cover mixed valid/missing session inputs and duplicate prevention.
- [x] Verify unknown-task no-op behavior remains unchanged.
- [x] A test: run targeted `pytest` modules for save/meta/e2e session fallback paths.

***Checkpoint 5: Quality gate and documentation polish***
- [x] Run lint/test quality gates (`flake8`, `pytest`) and resolve feature-related issues.
- [x] Update any adjacent docs/tests referencing "skip on missing session" to new behavior.
- [x] Confirm acceptance matrix coverage is complete.
- [x] A test: CI-equivalent local run passes for touched areas.
