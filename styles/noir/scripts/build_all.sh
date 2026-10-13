#!/bin/sh
# Baut alle Assets der Noir-Demo aus den vorhandenen Rohbildern neu (ruft kein Bildmodell auf) und importiert in Godot.
#   sh styles/noir/scripts/build_all.sh        (aus dem Projektordner)
set -e
cd "$(dirname "$0")/../../.."
PY=.venv/bin/python
blender -b --factory-startup -P styles/noir/blender/pose_layout.py -- --glb shared/3d/badger.glb --set walk \
    --out styles/noir/assets/ref/poses_walk > /dev/null
$PY styles/noir/scripts/make_layouts.py
$PY styles/noir/scripts/build_bg.py
$PY styles/noir/scripts/build_fx.py
$PY styles/noir/scripts/build_badger.py
$PY styles/noir/scripts/stage.py
godot --headless --path styles/noir/demo --import > /dev/null 2>&1
echo "ok"
