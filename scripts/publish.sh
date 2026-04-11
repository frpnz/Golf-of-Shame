#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
python3 backend/export_stats.py --db data/golf_tracker.sqlite --docs docs
printf 'Export completato. Ora puoi fare git add/commit/push.\n'
