#!/bin/sh
# Alles neu rendern und einrasten (aus dem Projektordner spielgrafik/ aufrufen):
#   sh styles/vorgerenderte-sprites/scripts/build_all.sh <Temp-Ordner> [bg|sprites|ui|reduce …]
# Rohrender (4×) landen im Temp-Ordner (≈ 150 MB), verarbeitete Bilder in assets/ und demo/.
# Laufzeit auf Apple M-Serie (Cycles, Metal): Hintergrund ≈ 1 min, Sprites ≈ 12 min, Oberfläche ≈ 20 s.
set -e
OUT="$1"; shift
STEPS="${*:-bg sprites ui reduce}"
S=styles/vorgerenderte-sprites
B="blender -b --factory-startup -P"
for step in $STEPS; do
  case "$step" in
    bg)      $B $S/blender/render_bg.py -- "$OUT/bg" --samples 160 --water-frames 12 ;;
    sprites) for g in badger dirs boat lantern props beam; do
               $B $S/blender/render_sprites.py -- "$OUT" $g --samples 64
             done ;;
    ui)      $B $S/blender/render_ui.py -- "$OUT" --samples 64 ;;
    reduce)  .venv/bin/python $S/scripts/reduce_bg.py "$OUT/bg"
             .venv/bin/python $S/scripts/reduce_sprites.py "$OUT" badger dirs boat lantern props beam ui ;;
  esac
done
