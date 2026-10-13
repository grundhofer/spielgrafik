#!/bin/sh
# Baut alle Assets des Eintrags bilderbuch-gouache aus den Rohbildern und kopiert sie in die Demo.
#   sh styles/bilderbuch-gouache/scripts/build_all.sh   (aus dem Projektordner)
set -e
S=styles/bilderbuch-gouache
PY=.venv/bin/python
$PY $S/scripts/build_badger.py
$PY $S/scripts/build_scene.py
$PY $S/scripts/choreo.py
mkdir -p $S/demo/art/fx
cp $S/assets/bg.png $S/assets/paper.png $S/assets/boat_a.png $S/assets/boat_b.png \
   $S/assets/badger_walk.png $S/assets/badger_idle.png $S/assets/badger.json \
   $S/assets/scene.json $S/assets/timeline.json $S/demo/art/
cp $S/assets/fx/*.png $S/demo/art/fx/
echo "ok assets -> $S/demo/art"
