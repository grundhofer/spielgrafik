#!/bin/sh
# Ausschnitte (x0 y0 x1 y1 im 320x200-Bild) zu mehreren Zeitpunkten nebeneinander, 3fach vergrößert.
#   sh styles/polygon-kino/scripts/crops.sh <ausgabe.png> "x0 y0 x1 y1" <t1> <t2> ... [-- Schalter]
set -e
PY="$(cd "$(dirname "$0")/../../.." && pwd)/.venv/bin/python"
D="$(cd "$(dirname "$0")" && pwd)"
OUT="$1"; BOX="$2"; shift 2
TMP="$(mktemp -d)"
TIMES=""
while [ $# -gt 0 ] && [ "$1" != "--" ]; do TIMES="$TIMES $1"; shift; done
[ "$1" = "--" ] && shift
for tt in $TIMES; do sh "$D/still.sh" "$tt" "$TMP/s_$tt.png" "$@"; done
"$PY" - "$OUT" "$TMP" "$BOX" $TIMES <<'PY'
import sys, pathlib
from PIL import Image
out, tmp, box, times = sys.argv[1], pathlib.Path(sys.argv[2]), [int(v) for v in sys.argv[3].split()], sys.argv[4:]
ims = [Image.open(tmp / f"s_{t}.png").crop(box) for t in times]
w, h = ims[0].size
sheet = Image.new("RGB", (w * len(ims), h))
for i, im in enumerate(ims):
    sheet.paste(im, (i * w, 0))
sheet.resize((sheet.width * 3, sheet.height * 3), Image.NEAREST).save(out)
PY
rm -rf "$TMP"
