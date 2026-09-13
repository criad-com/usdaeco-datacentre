#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
exec env -u PYTHONPATH \
  "${PYTHON:-${PY:-python3}}" check.py "$@"
