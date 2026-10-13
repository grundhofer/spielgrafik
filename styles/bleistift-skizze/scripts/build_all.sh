#!/bin/sh
# Baut alle Assets der Demo aus den Rohbildern neu (aus dem Projektordner aufrufen). Bitgleich reproduzierbar.
#   sh styles/bleistift-skizze/scripts/build_all.sh
# Vorher (nur einmal, schon geschehen): Blender-Posen (blender/pose_layout.py --set walk --ortho 2.5),
# scripts/make_layout.py, genimg.py für assets/raw/bg.png und assets/raw/walk.png (Prompts in assets/prompts/),
# scripts/split_sheet.py, Vorschub von Hand in assets/walk_advance.json (scripts/foot_match.py, overlay_pairs.py).
set -e
PY=.venv/bin/python
S=styles/bleistift-skizze/scripts
$PY $S/make_paper.py
$PY $S/build_drawing.py
$PY $S/build_badger.py
$PY $S/choreo.py
# Prüfen: $PY $S/probe_feet.py ; $PY $S/probe_feet.py --boil ; $PY $S/measure_fx.py
# Aufnehmen: $PY tools/capture.py styles/bleistift-skizze --poster-at 0.92
