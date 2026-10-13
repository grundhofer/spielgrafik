#!/bin/sh
# Baut alle Assets des Eintrags ohne Bildmodell neu (aus assets/raw/*.png) und kopiert sie in die Demo.
#   sh styles/comic-panels/scripts/build_all.sh        (aus dem Projektordner)
set -e
cd "$(dirname "$0")/../../.."
S=styles/comic-panels
blender -b --factory-startup -P $S/blender/pose_layout.py -- --glb shared/3d/badger.glb --set walk \
  --out $S/assets/ref/poses_walk > /dev/null
.venv/bin/python $S/scripts/make_layout.py
.venv/bin/python $S/scripts/make_prompts.py > /dev/null
.venv/bin/python $S/scripts/build_badger.py
.venv/bin/python $S/scripts/build_panels.py > /dev/null
mkdir -p $S/demo/art
for f in panel_a.png panel_a_ink.png panel_b.png panel_b_ink.png panel_c.png panel_c_ink.png \
         panel_c_talk.png panel_c_talk_ink.png badger.png badger_ink.png badger.json scene.json; do
  cp $S/assets/$f $S/demo/art/$f
done
godot --headless --path $S/demo --import > /dev/null 2>&1
echo "ok: $S/demo/art"
