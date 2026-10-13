#!/bin/sh
# Einzelbilder der Demo rendern (Movie Maker, 30 fps), z. B. für Sichtprüfung und Messskripte.
#   scripts/render_frames.sh <Zielordner> [Bildanzahl] [-- Prüfschalter]
set -e
HERE="$(cd "$(dirname "$0")/.." && pwd)"
OUT="$1"; N="${2:-180}"; shift; shift 2>/dev/null || true
mkdir -p "$OUT"
rm -f "$OUT"/f*.png
godot --headless --path "$HERE/demo" --import >/dev/null 2>&1 || true
godot --path "$HERE/demo" --position 20000,20000 --resolution 1280x720 \
  --write-movie "$OUT/f.png" --fixed-fps 30 --quit-after "$N" "$@" 2>&1 | grep -E "ERROR|WARNING" || true
ls "$OUT" | grep -c png
