#!/bin/zsh
# Einzelbild der Demo rendern (für Sichtprüfungen; Ausgabe in ein Temp-Verzeichnis).
#   scripts/snap.sh <ausgabe.png> <zeit_s> [Schalter für main.gd, z. B. --raw --static-cam]
# Spult per --t0 vor und nimmt dann 2 Bilder auf (das erste Bild nach dem Start ist noch unvollständig
# eingeschwungen); behalten wird das letzte.
set -e
out=$1; ts=$2; shift 2
demo=${0:A:h:h}/demo
tmp=$(mktemp -d)
godot --path $demo --position 20000,20000 --resolution 1280x720 --write-movie $tmp/f.png \
  --fixed-fps 30 --quit-after 2 -- --t0=$ts "$@" > $tmp/log.txt 2>&1 || { cat $tmp/log.txt; exit 1; }
grep -E "ERROR|SCRIPT ERROR|WARNING" $tmp/log.txt || true
last=$(ls $tmp/f*.png | tail -1)
cp $last $out
rm -rf $tmp
