#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
py="${PYTHON:-${PY:-python3}}"
exec env -u PYTHONPATH "$py" -m dcbuild publish "$@"
