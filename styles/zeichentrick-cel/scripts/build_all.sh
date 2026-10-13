#!/bin/sh
# Baut alle Assets des Eintrags zeichentrick-cel aus den Rohbildern und kopiert sie in die Demo.
#   sh styles/zeichentrick-cel/scripts/build_all.sh   (aus dem Projektordner)
set -e
S=styles/zeichentrick-cel
PY=.venv/bin/python
$PY $S/scripts/build_bg.py
$PY $S/scripts/build_water_mask.py
$PY $S/scripts/ink_paint.py
$PY $S/scripts/build_sprites.py
$PY $S/scripts/measure_walk.py
$PY $S/scripts/build_fx.py
mkdir -p $S/demo/art
cp $S/assets/bg.png $S/assets/badger_cels.png $S/assets/boat_a.png $S/assets/boat_b.png $S/assets/shadow.png \
   $S/assets/sprites.json $S/assets/walk.json $S/assets/fx/gull.png $S/assets/fx/twinkle.png $S/assets/fx/glow.png \
   $S/assets/water_mask.png $S/demo/art/
echo "ok assets -> $S/demo/art"
