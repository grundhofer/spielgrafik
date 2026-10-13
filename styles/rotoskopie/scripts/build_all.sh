#!/bin/sh
# Ganzer Bau des Eintrags "rotoskopie" in Reihenfolge (aus dem Projektordner aufrufen).
# Die KI-Bilder (assets/raw/sheet.png, sheet_b.png, bg.png) entstehen nicht hier, sondern einmalig mit
# tools/genimg.py --jobs styles/rotoskopie/assets/jobs_1.json bzw. jobs_2.json (Prompts in assets/prompts/).
# TMP: Ordner für Zwischenstände (Datenpässe, Prüfaufnahmen), danach löschbar.
set -e
TMP=${TMP:-/tmp/rotoskopie}
E=styles/rotoskopie
PY=.venv/bin/python

# 1. Vorlagen aus 3D: Datenpässe je Pose (Material, Tiefe, Licht) und Layout des Hintergrunds
blender -b --factory-startup -P $E/blender/rotoscope.py -- --glb shared/3d/badger.glb --out $TMP/passes --ppm 540
blender -b --factory-startup -P $E/blender/harbor_layout.py -- --glb shared/3d/harbor.glb \
    --out $E/assets/ref/harbor_layout.png --cam=-2.2,2.0,10.2 --pitch=-1
# 2. Posen-Vorlage für das Bildmodell und klassischer Weg ohne KI
$PY $E/scripts/build_templates.py --passes $TMP/passes
# 3. KI-Blätter messen (beide Läufe) und den eingebauten Lauf (sheet_b) zu Sprites machen
$PY $E/scripts/build_ai_sprites.py --sheet assets/raw/sheet.png --tag a
$PY $E/scripts/build_ai_sprites.py --sheet assets/raw/sheet_b.png --tag b
$PY $E/scripts/build_ai_sprites.py
$PY $E/scripts/compare_kss.py
# 4. Hintergrund an der Vorlage messen und schneiden, Daten für die Demo
$PY $E/scripts/prep_bg.py
$PY $E/scripts/make_anim.py
# 5. Prüfen: Füße und Kopf in der Godot-Ausgabe (drei Fassungen), dann Aufnahme
$PY $E/scripts/measure_feet.py --tmp $TMP/m
$PY tools/capture.py $E --poster-at 0.72
