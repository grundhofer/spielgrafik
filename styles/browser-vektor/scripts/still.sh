#!/bin/sh
# Einzelbild der Demo bei Zeit t0 rendern: scripts/still.sh <t0> <out.png> [weitere Prüfschalter]
# Rendert 2 Bilder ab t0 in ein Temp-Verzeichnis und kopiert das erste nach <out.png>.
set -e
HERE="$(cd "$(dirname "$0")/.." && pwd)"
T0="$1"; OUT="$2"; shift 2
TMP="$(mktemp -d)"
godot --path "$HERE/demo" --position 20000,20000 --resolution 1280x720 --write-movie "$TMP/f.png" \
  --fixed-fps 30 --quit-after 2 -- --t0="$T0" "$@" > "$TMP/log.txt" 2>&1 || true
grep -E "ERROR|SCRIPT ERROR|WARNING|STATS" "$TMP/log.txt" | head -20 || true
cp "$TMP/f00000000.png" "$OUT"
rm -rf "$TMP"
