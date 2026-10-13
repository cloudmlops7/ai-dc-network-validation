#!/usr/bin/env bash
set -uo pipefail

cd "$(dirname "$0")"
mkdir -p results

TIMESTAMP=$(date +%Y%m%d_%H%M%S)
REPORT="results/report_${TIMESTAMP}.html"
LOG="results/run_${TIMESTAMP}.log"

echo "HTML report: $REPORT"
echo "Console log: $LOG"

set +e
pytest -v --html="$REPORT" --self-contained-html "$@" 2>&1 | tee "$LOG"
STATUS=${PIPESTATUS[0]}
set -e

echo
echo "Pytest exit code: $STATUS"
echo "HTML report: $REPORT"
echo "Console log: $LOG"

exit "$STATUS"
