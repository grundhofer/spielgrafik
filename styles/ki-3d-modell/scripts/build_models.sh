#!/bin/bash
# Baut alle KI-3D-Modelle des Eintrags neu: TripoSR (lokal) -> Projektion anpassen -> Blender säubern/backen
# -> Dachs auf das Rig aus shared/3d übertragen -> glb nach demo/models/.
#
#   bash styles/ki-3d-modell/scripts/build_models.sh            (aus dem Projektordner)
#
# Voraussetzungen (nicht eingecheckt, siehe .gitignore): tsr/venv (Python 3.11, torch 2.7.1 …),
# tsr/TripoSR (github.com/VAST-AI-Research/TripoSR, MIT), tsr/hf (Gewichte stabilityai/TripoSR, MIT).
# Eingaben: assets/raw/*.png aus tools/genimg.py (nicht eingecheckt).
# Zwischenstände landen in work/ (nicht eingecheckt); Berichte in assets/models/*.json.
set -euo pipefail
E=styles/ki-3d-modell
W=$E/work
export HF_HOME=$E/tsr/hf HF_HUB_OFFLINE=1 HF_HUB_DISABLE_TELEMETRY=1
mkdir -p $W/tsr $E/assets/models $E/demo/models

for n in badger_front barrel lantern boat; do
    $E/tsr/venv/bin/python -I $E/scripts/tsr_run.py --image $E/assets/raw/$n.png --out $W/tsr/$n \
        --device mps --mc 256 --views 6 > /dev/null
done
$E/tsr/venv/bin/python -I $E/scripts/fit_projection.py $W/tsr/badger_front $W/tsr/barrel $W/tsr/lantern $W/tsr/boat

bake() { blender -b --factory-startup -P $E/blender/clean_bake.py -- "$@" 2>&1 | grep -E "^\[clean_bake|Error|Traceback" || true; }

bake --dir $W/tsr/barrel --name Barrel --height 0.9 --tris 4000 --tilt foot \
     --out $E/demo/models/barrel_tsr.glb --tex-out $E/assets/models/barrel_tex.png --report $E/assets/models/barrel.json
bake --dir $W/tsr/lantern --name LanternTSR --height 2.45 --tris 5000 --tilt foot --min-part 0.002 --sharp 35 \
     --bridge --out $E/demo/models/lantern_tsr.glb --tex-out $E/assets/models/lantern_tex.png \
     --report $E/assets/models/lantern.json
bake --dir $W/tsr/boat --name BoatTSR --length 4.0 --tris 6000 --tilt flat --yaw auto --sharp 45 \
     --out $E/demo/models/boat_tsr.glb --tex-out $E/assets/models/boat_tex.png --report $E/assets/models/boat.json
bake --dir $W/tsr/badger_front --name BadgerTSR --height 1.011 --tris 8000 --tilt foot --tilt-range 15 \
     --origin feet --squash-back=-0.2,0.42,0.3 --out $W/badger_static.glb --tex-out $E/assets/models/badger_tex.png \
     --report $E/assets/models/badger_static.json

# Rig-Quelle: gemeinsamer Dachs, neu gebaut in den eigenen Ordner (shared/ bleibt unberührt, bytegleich)
blender -b --factory-startup -P shared/3d/blender/build_badger.py -- --out $W/rigsrc --no-preview --no-notes \
    --save-blend $W/rigsrc/badger.blend > /dev/null
cmp $W/rigsrc/badger.glb shared/3d/badger.glb
blender -b --factory-startup $W/rigsrc/badger.blend -P $E/blender/rig_transfer.py -- \
    --mesh $W/badger_static.glb --out $E/demo/models/badger_tsr.glb --report $E/assets/models/badger_rig.json \
    2>&1 | grep -E "^\[rig_transfer|Error|Traceback" || true
godot --headless --path $E/demo --import > /dev/null 2>&1
echo "fertig: $E/demo/models"
