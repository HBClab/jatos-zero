# Feature -> Testing Suite

## Purpose
---
Define a baseline automated testing suite for the QA/QC pipeline that:
- validates current known-task behavior end-to-end,
- supports extension for domain-level algorithm tests,
- and enforces quality checks in CI.

This feature supports the main project goal of making the pipeline configurable while preserving baseline behavior for the current study.

## Goal Alignment (Project Constitution)
---
This spec is constrained by the project main goal in `features/MAIN-GOAL.md`:
- Preserve baseline full-QC behavior for known tasks.
- Ignore unknown/new tasks completely for now.
- Keep `meta/` generation behavior unchanged for known-task processing.
- Prioritize deterministic local behavior over external integration.

## Scope
---
In scope:
- Add a basic automated test architecture under `tests/`.
- Add one end-to-end (e2e) happy-path test for a known task.
- Add structure for domain-level algorithm tests (CC, MEM, PS, WL).
- Use small committed synthetic fixtures.
- Add CI requirements to run lint + tests on pull requests.

Out of scope:
- Expanding pipeline support to new/unknown tasks.
- Plot image-content validation.
- Performance benchmarking.
- Network-based integration tests against JATOS.
- Refactors to production QC logic unrelated to testability.

## Constraints from Main Goal
---
- Full QC behavior for known tasks must remain intact.
- Unknown/new tasks remain ignored by the pipeline.
- `meta/` outputs remain generated for known-task processing.
- Testing should prioritize deterministic, local, non-network execution.

## Assumptions
---
- Test execution uses `pytest`.
- Linting remains `flake8` per repo guidance.
- CI provider is intentionally unspecified; any provider is acceptable if it enforces required checks.

## Functional Requirements (FR)
---

### FR-001: Baseline test framework
The repository SHALL provide a runnable `pytest`-based test suite as the default test runner.

Acceptance criteria:
- `pytest` discovers and executes tests under `tests/`.
- Test layout supports both e2e and domain-level unit/integration tests.
- Tests can run from repository root without network dependency.
- Existing repository behavior remains unchanged outside test artifacts.

### FR-002: End-to-end known-task happy-path test (AF baseline)
The suite SHALL include at least one e2e test that executes a known-task processing flow using `AF` and validates expected artifacts.

Acceptance criteria:
- The e2e test runs pipeline orchestration for `AF` from the authoritative list in `code/main_handler.py`.
- The test asserts expected saved outputs for that run (data artifacts relevant to the task).
- The test asserts `meta/` aggregate outputs are produced/updated as expected for known-task processing.
- The test uses only local synthetic fixtures and does not require network access.
- The test isolates filesystem side effects using temporary output paths where practical.

### FR-003: Fixture strategy
The test suite SHALL use committed, minimal, synthetic fixtures for deterministic behavior.

Acceptance criteria:
- Fixtures are stored under `tests/fixtures/` (or a documented equivalent under `tests/`).
- Fixture payloads are small and representative of valid known-task inputs.
- Fixtures are stable across runs and do not depend on mutable repo data in `data/`.
- Fixture naming conventions indicate domain/task purpose.

### FR-004: Extensible domain test architecture
The suite SHALL include a domain-based structure enabling focused testing of feature-update algorithms and QC logic.

Acceptance criteria:
- Test modules are organized by domain (`cc`, `mem`, `ps`, `wl`) within `tests/data_processing/`.
- Shared helpers/factories are provided to reduce duplication across domain tests.
- New domain-level algorithm tests can be added without modifying existing e2e tests.
- Domain tests can compose fixtures/helpers without requiring changes to production module imports.

### FR-005: Regression coverage for core pipeline rules
Tests SHALL protect behavior required by the project main goals.

Acceptance criteria:
- Known-task processing behavior is covered by automated tests.
- Unknown/new task handling is covered by at least one test that verifies complete ignore/no-op behavior (no QC, no plots, no meta writes, no saved outputs).
- Meta output behavior for known-task runs is covered by automated assertions.

### FR-006: CI quality gate
Pull request validation SHALL run linting and the automated test suite, including e2e.

Acceptance criteria:
- CI configuration (provider-agnostic) runs lint (`flake8`) and tests (`pytest`) for PRs.
- CI fails the PR status when lint or tests fail.
- e2e test(s) are included in the default CI test run.
- CI setup and local equivalents are documented.

### FR-007: Developer execution and maintainability
The testing suite SHALL provide clear local commands and predictable structure for future contributors.

Acceptance criteria:
- A documented local workflow exists for running lint, all tests, and e2e-only tests.
- Naming conventions for test files and fixtures are documented in the feature output.
- New domain tests can be added by following a small documented pattern.

## Proposed Test Structure
---
Target structure:

```
tests/
	e2e/
		test_known_task_happy_path.py
	data_processing/
		cc/
			test_cc_*.py
		mem/
			test_mem_*.py
		ps/
			test_ps_*.py
		wl/
			test_wl_*.py
		helpers/
			fixture_factories.py
			assertions.py
	fixtures/
		af_known_task/
			... synthetic payloads ...
		shared/
			... cross-domain fixture pieces ...
```

Notes:
- Exact filenames may vary, but directory responsibilities should remain the same.
- Keep test helpers generic and reusable across domains.
- Keep imports compatible with the current package layout under `code/`.

## Acceptance Test Matrix
---
- `AF` e2e happy-path test validates known-task pipeline behavior and expected artifacts.
- Unknown-task no-op test validates complete ignore behavior.
- At least one domain-level sample test validates helper/factory extensibility.
- CI pipeline executes lint and tests on pull requests.

## Non-Functional Requirements
---
- Tests should be deterministic and runnable offline.
- Test runtime should remain practical for PR validation (favor small fixtures).
- Tests should isolate filesystem side effects via temporary directories when possible.

## Definition of Done
---
This feature is complete when:
- FR-001 through FR-007 are implemented and verifiable.
- The suite is documented with clear local run commands.
- CI enforces lint + test execution for pull requests.

## Implementation Plan
---

***Checkpoint 1: Test Harness Bootstrap***
- [x] Add base `pytest` structure under `tests/` (`e2e/`, `data_processing/`, `fixtures/`).
- [x] Add shared test config (`conftest.py`) for path setup and temporary artifact directories.
- [x] Add baseline lint/test local command documentation in project docs section for testing.
- [x] A test: `pytest` discovery smoke test confirms suite collection works from repo root.

***Checkpoint 2: Fixture and Helper Foundation***
- [x] Add committed synthetic fixtures for `AF` known-task flow under `tests/fixtures/af_known_task/`.
- [x] Add shared factories/assertion helpers in `tests/data_processing/helpers/`.
- [x] Ensure helper APIs are domain-agnostic and reusable by CC/MEM/PS/WL tests.
- [x] A test: helper/factory unit test validates fixture loading and normalized assertions.

***Checkpoint 3: AF End-to-End Path***
- [x] Implement `tests/e2e/test_known_task_happy_path.py` for `AF` orchestration path.
- [x] Assert expected saved artifacts for the `AF` run in isolated temp output paths.
- [x] Assert expected `meta/` artifact generation behavior for known-task processing.
- [x] A test: `AF` e2e passes fully offline with synthetic fixtures.

***Checkpoint 4: Unknown-Task No-Op Guardrail***
- [x] Add test coverage for unknown/new task input handling.
- [x] Assert complete ignore/no-op behavior (no QC, no plots, no meta writes, no saved outputs).
- [x] Ensure no exceptions are raised for ignored task paths unless explicitly intended by production behavior.
- [x] A test: unknown-task regression test verifies zero output mutation.

***Checkpoint 5: Domain Extensibility Skeleton + CI Gate***
- [x] Add starter domain test modules for `cc`, `mem`, `ps`, and `wl` that use shared helpers.
- [x] Add provider-agnostic CI workflow requirement implementation to run `flake8` + `pytest` on PR.
- [x] Document local equivalents (`flake8 tests`, `pytest`, and e2e-targeted invocation).
- [x] A test: CI-equivalent local run succeeds with lint + full test suite including e2e.