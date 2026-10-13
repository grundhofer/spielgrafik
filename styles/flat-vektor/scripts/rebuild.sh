#!/bin/sh
# SVG neu zeichnen und in Godot-Szenen umwandeln (aus dem Projektordner aufrufen)
set -e
S=styles/flat-vektor
.venv/bin/python $S/scripts/build_svg.py
.venv/bin/python $S/scripts/svg2godot.py $S/assets/harbor.svg $S/demo/art/harbor.tscn --stats $S/assets/harbor_stats.json
.venv/bin/python $S/scripts/svg2godot.py $S/assets/badger.svg $S/demo/art/badger.tscn --stats $S/assets/badger_stats.json
