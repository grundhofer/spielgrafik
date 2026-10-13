#!/bin/sh
# Kontaktbogen mehrerer Zeitpunkte (je 320x200, 2fach) für die Sichtprüfung.
#   sh styles/polygon-kino/scripts/sheet.sh <ausgabe.png> <t1> <t2> ... [-- Schalter]
set -e
PY="$(cd "$(dirname "$0")/../../.." && pwd)/.venv/bin/python"
D="$(cd "$(dirname "$0")" && pwd)"
OUT="$1"; shift
TMP="$(mktemp -d)"
TIMES=""
while [ $# -gt 0 ] && [ "$1" != "--" ]; do TIMES="$TIMES $1"; shift; done
[ "$1" = "--" ] && shift
for tt in $TIMES; do sh "$D/still.sh" "$tt" "$TMP/s_$tt.png" "$@"; done
"$PY" - "$OUT" "$TMP" $TIMES <<'PY'
import sys, pathlib
from PIL import Image, ImageDraw
out, tmp, times = sys.argv[1], pathlib.Path(sys.argv[2]), sys.argv[3:]
ims = [Image.open(tmp / f"s_{t}.png").resize((640, 400), Image.NEAREST) for t in times]
cols = 2
rows = (len(ims) + cols - 1) // cols
sheet = Image.new("RGB", (640 * cols, 400 * rows))
d = ImageDraw.Draw(sheet)
for i, (im, t) in enumerate(zip(ims, times)):
    x, y = (i % cols) * 640, (i // cols) * 400
    sheet.paste(im, (x, y)); d.text((x + 4, y + 4), f"t={t}", fill="white")
sheet.save(out)
PY
rm -rf "$TMP"
