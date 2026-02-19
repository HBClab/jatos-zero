#!/usr/bin/env bash
set -euo pipefail

python -m flake8 tests
python -m flake8 beh
pytest -q
