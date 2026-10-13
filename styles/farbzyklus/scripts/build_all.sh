#!/bin/sh
# Baut alle Assets des Eintrags farbzyklus neu (Reihenfolge wichtig: Szene vor Figur, beide schreiben palette.json).
# Aufruf aus dem Projektordner: sh styles/farbzyklus/scripts/build_all.sh
set -e
.venv/bin/python styles/farbzyklus/scripts/build_scene.py
.venv/bin/python styles/farbzyklus/scripts/build_badger.py
.venv/bin/python styles/farbzyklus/scripts/palette_sheet.py
godot --headless --path styles/farbzyklus/demo --import >/dev/null 2>&1
