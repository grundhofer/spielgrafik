#!/bin/sh
# Einzelbild(er) ab Zeitpunkt t0 rendern: scripts/still.sh <ausgabeordner> <t0> [bilder] [weitere Benutzerargumente]
set -e
OUT=$1; T0=$2; N=${3:-1}; shift 3 || shift $#
mkdir -p "$OUT"
D=styles/flat-vektor/demo
godot --headless --path $D --import >/dev/null 2>&1
godot --path $D --position 20000,20000 --resolution 1280x720 --write-movie "$OUT/f.png" --fixed-fps 30 --quit-after "$N" -- --t0="$T0" "$@" 2>&1 | grep -E "ERROR|WARNING" || true
