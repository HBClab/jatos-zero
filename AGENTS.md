# Repository Guidelines

## Project Structure & Module Organization
- Core orchestration lives in `code/`; `main_handler.py` coordinates task-level QC flows.
- Domain logic sits in `code/data_processing/` (CC, MEM, PS, WL modules plus utilities for plotting and persistence).
- Raw exports belong in `data/` (`data/int/` stores intermediates); aggregated CSVs auto-save to `meta/`.
- Visual artifacts render into `group/plots/`; keep derived notebooks or experiments outside tracked dirs unless reproducible.

## Build, Test, and Development Commands
- `python -m venv .venv && source .venv/bin/activate` (or `nix develop`) prepares the toolchain.
- `pip install -r requirements.txt` installs runtime dependencies; prefer dev-only extras in a separate file if needed.
- `python code/main_handler.py <TASK>` runs QC for a specific task (`AF`, `WL`, etc.); use `all` to replicate the scheduled GitHub Action.
- `python -m flake8 code` enforces lint rules; resolve warnings before committing.

## Coding Style & Naming Conventions
- Target Python 3.10+ features compatible with the flake environment; keep indentation at four spaces and follow PEP 8 layout.
- Modules and functions use snake_case (`save_utils.py`, `qc_cc_dfs`), while orchestration classes remain PascalCase (`Handler`, `CCqC`).
- Constants stay UPPER_SNAKE_CASE; include concise docstrings when adding new data loaders or plotters.

## Testing Guidelines
- Pytest is available in CI; place new tests under `tests/` mirroring the package tree (`tests/data_processing/test_wl_qc.py`).
- Name tests `test_<behavior>()` and rely on fixtures for representative CSV payloads; store them in `tests/fixtures/`.
- Run `pytest` locally before opening a PR; aim for coverage on threshold logic and file outputs, using temp dirs to assert artifact names.

## Commit & Pull Request Guidelines
- History favors short, imperative titles (e.g., `Add WL QC persistence`); keep subjects ≤72 chars and add context in the body when behavior shifts.
- PRs should summarize intent, list commands run (`pytest`, `flake8`, task processors), and call out any data schema or visualization changes with screenshots from `group/plots/`.
- Link related tickets or issues and flag breaking changes early so downstream analysts can adjust schedules.

## Security & Configuration Notes
- Never commit credentials or real tokens—parameterize secrets via environment variables and document expectations in `README.md`.
- Large or sensitive CSV exports stay in `meta/` (tracked aggregations) or ignored paths; update `.gitignore` when introducing new temp output folders.
- When adding config flags, reflect them in `run.py` usage examples and surface defaults in module-level constants.
