#!/bin/sh
# Baut alle Assets der Buchmalerei-Demo aus den KI-Rohbildern neu und kopiert sie nach demo/art.
# Aufruf aus dem Projektordner: sh styles/buchmalerei/scripts/build_all.sh
set -e
D=styles/buchmalerei
PY=.venv/bin/python
$PY $D/scripts/build_miniature.py
$PY $D/scripts/build_badger.py
$PY $D/scripts/build_page.py
$PY $D/scripts/build_drollery.py
for f in page.png page_gold.png page.json miniature.png mini_mask.png mini_nocrest.png miniature.json \
         badger_body.png badger_arm.png badger.json drollery.png drollery_gold.png drollery.json; do
  cp $D/assets/$f $D/demo/art/$f
done
godot --headless --path $D/demo --import >/dev/null 2>&1 || true
echo "ok: Assets in $D/demo/art"
