#!/bin/sh
# Baut alle Assets des Eintrags kupferstich aus den Rohbildern neu (ruft kein Bildmodell auf) und importiert die Demo.
#   sh styles/kupferstich/scripts/build_all.sh            (aus dem Projektordner)
#   sh styles/kupferstich/scripts/build_all.sh --layouts  (zusätzlich die Blender-Layouts für die Bildaufträge)
set -e
ROOT="$(cd "$(dirname "$0")/../../.." && pwd)"
SD="$ROOT/styles/kupferstich"
PY="$ROOT/.venv/bin/python"
cd "$ROOT"
if [ "$1" = "--layouts" ]; then
  blender -b --factory-startup -P "$SD/blender/pose_layout.py" -- --glb shared/3d/badger.glb --set walk \
    --out "$SD/assets/ref/poses_walk" >/dev/null
  blender -b --factory-startup -P "$SD/blender/pose_layout.py" -- --glb shared/3d/badger.glb --set walk \
    --ortho 2.5 --out "$SD/assets/ref/poses_walk_small" >/dev/null
  "$PY" "$SD/scripts/make_layouts.py"
  "$PY" "$SD/scripts/make_style_ref.py"
fi
mkdir -p "$SD/demo/art"
cp "$SD/scripts/layout.json" "$SD/demo/art/layout.json"
"$PY" "$SD/scripts/build_scene.py"      # KI-Farbcode-Maske -> Effektmasken, Lichtpunkte
"$PY" "$SD/scripts/build_plate.py"      # KI-Stich -> Druckplatte (Tusche, Kammfeld, Spiegelungen)
"$PY" "$SD/scripts/make_paper.py"       # Papier mit Plattenrand
"$PY" "$SD/scripts/build_badger.py"     # KI-Laufbogen -> Spielbilder
"$PY" "$SD/scripts/choreo.py"           # Ablauf der Figur (Tabelle für Demo und Messung)
"$PY" "$SD/scripts/build_ornaments.py"  # Initialrahmen, Vignette, Zierlinie
"$PY" "$SD/scripts/make_fx.py"          # gestochener Schlagschatten
godot --headless --path "$SD/demo" --import >/dev/null 2>&1
echo "ok: Assets neu gebaut; prüfen: $PY $SD/scripts/probe_feet.py"
