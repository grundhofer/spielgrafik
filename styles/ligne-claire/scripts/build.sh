#!/bin/sh
# Baut alle Assets des Eintrags "ligne-claire" aus den Quellen neu und kopiert sie in die Demo.
# Aufruf aus dem Projektordner: sh styles/ligne-claire/scripts/build.sh
# Quellen: assets/raw/bg.png (agy), shared/3d/badger.glb. Kein Bildmodell-Aufruf.
set -e
E=styles/ligne-claire
PY=.venv/bin/python
# Figur im Hauptpanel: 109 px/m (Render 3-fach = 327 px/m), Lauf in 8 Bildern je Zyklus, Kamera 5° von oben.
# render_badger.py glättet das Modell (Subdivision Stufe 2, Smooth Shading) und setzt die Pfoten farblich ab.
blender -b --factory-startup -P $E/blender/render_badger.py -- --glb shared/3d/badger.glb \
    --out $E/assets/raw/render --ppm 327 --walk-frames 8 --tilt 5 | grep -E "Reihe|fertig|rror"
# Brustbild für den Einschub: 420 px/m (Render 1260 px/m), Kamera auf Augenhöhe
blender -b --factory-startup -P $E/blender/render_badger.py -- --glb shared/3d/badger.glb \
    --out $E/assets/raw/render_cu --ppm 1260 --preset cu --only wave,idle --tilt 0 | grep -E "Reihe|fertig|rror"
# Kleine Figur: im Gesicht keine Linien zwischen hellem und dunklem Fell, Auge und Nase als Punkte (sonst Linienknäuel).
# Linie 5 Renderpixel (1,7 px): Bei 110 px Figurhöhe liegen Linien dicht beieinander; mit 6 (2 px) maß line_width.py
# im Mittel 3,1 px gegen 2,1 px im Hintergrund, mit 5 sind es 2,7 px (Anteil 2-px-Läufe 52 % wie im Hintergrund 61 %).
$PY $E/scripts/ink_badger.py --render $E/assets/raw/render --out $E/assets --face-simple --eye-grow 4 --line 5
$PY $E/scripts/ink_badger.py --render $E/assets/raw/render_cu --out $E/assets --prefix closeup --full-frame
$PY $E/scripts/build_bg.py
mkdir -p $E/demo/art
cp $E/assets/bg.png $E/assets/badger.json $E/assets/closeup.json \
   $E/assets/badger_walk.png $E/assets/badger_turn.png $E/assets/badger_wave.png $E/assets/badger_idle.png \
   $E/assets/closeup_wave.png $E/assets/closeup_idle.png $E/demo/art/
echo "fertig: Assets in $E/assets und $E/demo/art"
