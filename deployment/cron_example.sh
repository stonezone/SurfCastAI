#!/bin/bash
# SurfCastAI scheduled run (sample cron helper)

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")"/.. && pwd)"
cd "$ROOT_DIR"

LOG_DIR="logs"
mkdir -p "$LOG_DIR"

STAMP="$(date +%Y%m%d)"
LOG_FILE="$LOG_DIR/cron-${STAMP}.log"

echo "[$(date -Is)] Starting SurfCastAI cron run" >> "$LOG_FILE"

python src/main.py run --mode full >> "$LOG_FILE" 2>&1

# Simple rotation: keep 7 most recent cron logs
cd "$LOG_DIR"
ls -1 cron-*.log 2>/dev/null | sort | head -n -7 | xargs -r rm -f
