#!/bin/sh
# Einzelbild der Demo zum Zeitpunkt t (Sekunden) als PNG (320x200 und 3fach vergrößert).
#   sh styles/polygon-kino/scripts/still.sh <t> <ausgabe.png> [weitere Schalter, z. B. --probe-badger]
set -e
PY="$(cd "$(dirname "$0")/../../.." && pwd)/.venv/bin/python"
D="$(cd "$(dirname "$0")/../demo" && pwd)"
TT="$1"; OUT="$2"; shift 2
TMP="$(mktemp -d)"
godot --path "$D" --position 20000,20000 --write-movie "$TMP/f.png" --fixed-fps 30 --quit-after 1 -- --t0="$TT" "$@" >/dev/null 2>&1
F="$(ls "$TMP"/f*.png | head -1)"
"$PY" -c "
from PIL import Image; import sys
im=Image.open(sys.argv[1]).convert('RGB'); im.save(sys.argv[2])
im.resize((im.width*3, im.height*3), Image.NEAREST).save(sys.argv[2].replace('.png','_x3.png'))
" "$F" "$OUT"
rm -rf "$TMP"
