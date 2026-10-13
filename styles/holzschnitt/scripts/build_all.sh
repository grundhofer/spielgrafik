#!/bin/sh
# Baut alle verarbeiteten Assets des Eintrags "holzschnitt" aus den Rohbildern neu (aus dem Projektordner aufrufen).
# Rohbilder (assets/raw/*.png) kommen von tools/genimg.py; Prompts stehen in den .json daneben.
set -e
PY=.venv/bin/python
S=styles/holzschnitt
blender -b --factory-startup -P $S/blender/pose_layout.py -- --glb shared/3d/badger.glb --set walk --out $S/assets/ref/poses_walk >/dev/null
$PY $S/scripts/make_layout.py
$PY $S/scripts/make_style_ref.py
$PY $S/scripts/make_textures.py
$PY $S/scripts/make_fx.py
$PY $S/scripts/build_plates.py
$PY $S/scripts/build_badger.py
$PY $S/scripts/choreo.py
godot --headless --path $S/demo --import >/dev/null 2>&1
echo "fertig; Aufnahme: $PY tools/capture.py $S --poster-at 0.85"
