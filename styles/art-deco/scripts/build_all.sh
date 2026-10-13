#!/bin/sh
# Baut alle verarbeiteten Assets der Art-déco-Demo aus den KI-Rohbildern (assets/raw) und dem Blender-Layout neu.
# Aufruf aus dem Projektordner:  sh styles/art-deco/scripts/build_all.sh
set -e
PY=.venv/bin/python
D=styles/art-deco
blender -b --factory-startup -P $D/blender/pose_layout.py -- --glb shared/3d/badger.glb --set walk \
    --out $D/assets/ref/poses_walk > /dev/null
$PY $D/scripts/make_layout.py
$PY $D/scripts/build_bg.py
$PY $D/scripts/build_badger.py --heads
$PY $D/scripts/measure_stride.py > /dev/null
$PY $D/scripts/choreo.py
$PY $D/scripts/stage_ui.py
godot --headless --path $D/demo --import > /dev/null 2>&1
echo "fertig"
