#!/bin/bash
# Baut alle Assets des Eintrags gummischlauch ohne Bildmodell neu (aus assets/raw/) und importiert sie in Godot.
#   bash styles/gummischlauch/scripts/build_all.sh
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../../.." && pwd)"
cd "$ROOT"
PY=.venv/bin/python
$PY styles/gummischlauch/scripts/make_layout.py
$PY styles/gummischlauch/scripts/make_prompts.py
$PY styles/gummischlauch/scripts/build_assets.py
godot --headless --path styles/gummischlauch/demo --import >/dev/null 2>&1
echo "fertig; Prüfung: scripts/measure_badger.py, scripts/measure_ratio.py, scripts/measure_dance.py, scripts/compare_renderers.py"
