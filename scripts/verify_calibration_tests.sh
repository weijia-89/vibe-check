#!/usr/bin/env bash
# Mirrors CI test-pytest job: pytest + combined coverage floor on drift/calibration surface.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
PY=python3
if [[ -x "$ROOT/.venv/bin/python" ]]; then
  PY="$ROOT/.venv/bin/python"
fi
"$PY" -m pytest tests/test_drift.py tests/test_calibration.py tests/test_gh_integration.py -q --maxfail=5
if ! "$PY" -c "import coverage" 2>/dev/null; then
  "$PY" -m pip install coverage
fi
"$PY" -m coverage run --source=scripts -m pytest tests/test_drift.py tests/test_calibration.py tests/test_gh_integration.py -q
"$PY" -m coverage report \
  --include="scripts/eval_drift.py,scripts/calibration_pipeline.py,scripts/vibe_calibration.py,scripts/vibe_check.py" \
  --fail-under=38
