#!/bin/sh
# Baut alle verarbeiteten Assets der Jugendstil-Demo aus den KI-Rohbildern (assets/raw) und dem Blender-Layout neu.
# Aufruf aus dem Projektordner:  sh styles/jugendstil/scripts/build_all.sh
set -e
PY=.venv/bin/python
D=styles/jugendstil
blender -b --factory-startup -P $D/blender/pose_layout.py -- --glb shared/3d/badger.glb --set walk \
    --out $D/assets/ref/poses_walk > /dev/null
$PY $D/scripts/make_layout.py
$PY $D/scripts/make_frame_layout.py
$PY $D/scripts/build_frame.py
$PY $D/scripts/build_bg.py > /dev/null
$PY $D/scripts/layout.py > /dev/null
$PY $D/scripts/build_badger.py --heads > /dev/null
$PY $D/scripts/measure_stride.py > /dev/null
$PY $D/scripts/choreo.py > /dev/null
$PY $D/scripts/stage_ui.py
godot --headless --path $D/demo --import > /dev/null 2>&1
echo "fertig"
