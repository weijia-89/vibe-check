#!/usr/bin/env bash
# Integration smoke test: exercise every CLI entry-point shape against a fixture.
# No `|| true`. Every step must succeed for the test to pass.

set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
DIFF="$ROOT/tests/fixtures/minimal.diff"
PY="${PYTHON:-python3}"

# 1. JSON output contract: required keys, valid JSON.
"$PY" "$ROOT/scripts/vibe_check.py" --diff "$DIFF" --format json | "$PY" -c "
import json, sys
d = json.load(sys.stdin)
required = ('overall_ai_probability', 'grade', 'signal_summary',
            'file_analyses', 'pattern_taxonomy', 'recommendations')
for k in required:
    assert k in d, f'missing JSON key: {k}'
print('vibe_check json smoke: ok')
"

# 2. Markdown output: must contain 'Grade' header text. NO `|| true` here.
out="$("$PY" "$ROOT/scripts/vibe_check.py" --diff "$DIFF" --format markdown)"
echo "$out" | grep -qE 'Grade|grade' \
    || { echo "vibe_check markdown smoke: FAIL — missing 'Grade'"; echo "$out"; exit 1; }
echo "vibe_check markdown smoke: ok"

# 3. --no-aggregate must suppress AI Probability headline.
out="$("$PY" "$ROOT/scripts/vibe_check.py" --diff "$DIFF" --no-aggregate --format markdown)"
echo "$out" | grep -q 'Aggregate score suppressed' \
    || { echo "vibe_check no-aggregate smoke: FAIL"; echo "$out"; exit 1; }
echo "$out" | grep -q '\*\*AI Probability:' \
    && { echo "vibe_check no-aggregate smoke: FAIL — AI Probability not suppressed"; echo "$out"; exit 1; }
echo "vibe_check --no-aggregate smoke: ok"

# 4. JSON --no-aggregate: aggregate fields must be null and aggregate_suppressed=true.
"$PY" "$ROOT/scripts/vibe_check.py" --diff "$DIFF" --no-aggregate --format json | "$PY" -c "
import json, sys
d = json.load(sys.stdin)
assert d.get('aggregate_suppressed') is True
assert d['overall_ai_probability'] is None
assert d['grade'] is None
print('vibe_check no-aggregate JSON smoke: ok')
"

# 5. Drift modes that require telemetry must report NO_TELEMETRY when env unset.
unset VIBE_CHECK_TELEMETRY_DIR
out="$("$PY" "$ROOT/scripts/vibe_check.py" --drift-status)"
echo "$out" | grep -q 'NO_TELEMETRY' \
    || { echo "vibe_check drift-status smoke: FAIL"; echo "$out"; exit 1; }
echo "vibe_check --drift-status smoke: ok"

# 6. --model-evolution defaults to EXPERIMENTAL_DISABLED.
out="$("$PY" "$ROOT/scripts/vibe_check.py" --model-evolution)"
echo "$out" | grep -q 'EXPERIMENTAL_DISABLED' \
    || { echo "vibe_check model-evolution smoke: FAIL"; echo "$out"; exit 1; }
echo "vibe_check --model-evolution fence: ok"

echo "All integration smoke checks passed."
