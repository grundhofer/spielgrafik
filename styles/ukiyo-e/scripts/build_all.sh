#!/bin/sh
# Baut alle verarbeiteten Assets der Ukiyo-e-Demo aus den KI-Rohbildern (assets/raw) und dem Blender-Layout neu.
# Aufruf aus dem Projektordner:  sh styles/ukiyo-e/scripts/build_all.sh
set -e
PY=.venv/bin/python
D=styles/ukiyo-e
blender -b --factory-startup -P $D/blender/pose_layout.py -- --glb shared/3d/badger.glb --set walk \
    --out $D/assets/ref/poses_walk > /dev/null
$PY $D/scripts/make_layout.py
$PY $D/scripts/build_bg.py
$PY $D/scripts/build_lights.py
$PY $D/scripts/build_waves.py
$PY $D/scripts/build_badger.py
$PY $D/scripts/choreo.py
$PY $D/scripts/make_textures.py
godot --headless --path $D/demo --import > /dev/null 2>&1
echo "fertig"
