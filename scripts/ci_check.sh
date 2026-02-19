#!/usr/bin/env bash
set -euo pipefail

python -m flake8 tests
pytest -q
