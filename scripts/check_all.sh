#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
exec env -u PYTHONPATH PYTHONPATH="${AECO_VALIDATION_CORE_ROOT:-../usdaeco-core}:$PWD" \
  "${PYTHON:-${PY:-python3}}" check.py "$@"
