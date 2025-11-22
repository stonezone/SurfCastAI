#!/bin/bash
# Generate a weekly SurfCastAI accuracy summary.

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")"/.. && pwd)"
cd "$ROOT_DIR"

LOG_DIR="logs"
mkdir -p "$LOG_DIR"

STAMP="$(date +%Y%m%d)"
LOG_FILE="$LOG_DIR/weekly-${STAMP}.log"

OUTPUT=$(python src/main.py accuracy-report --days 7)
echo "[$(date -Is)]" >> "$LOG_FILE"
echo "$OUTPUT" >> "$LOG_FILE"
echo "" >> "$LOG_FILE"

echo "Weekly accuracy report written to $LOG_FILE"
echo "Summary:" 
echo "$OUTPUT" | sed -n '1,10p'
