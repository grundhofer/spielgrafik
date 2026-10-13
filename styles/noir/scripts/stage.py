#!/usr/bin/env python3
"""Kopiert die verarbeiteten Assets in das Godot-Projekt (demo/art) und schreibt art/ui_text.json aus data/motif.json.

    .venv/bin/python styles/noir/scripts/stage.py
"""
import json, pathlib, shutil

ROOT = pathlib.Path(__file__).resolve().parents[1]
ART = ROOT / "demo/art"
FILES = ["bg.png", "fx_mask.png", "aux_mask.png", "noise.png", "badger.png", "badger_n.png", "badger.json",
         "scene.json"]


def main():
    ART.mkdir(parents=True, exist_ok=True)
    for f in FILES:
        shutil.copy2(ROOT / "assets" / f, ART / f)
    motif = json.loads((ROOT.parents[1] / "data/motif.json").read_text())
    (ART / "ui_text.json").write_text(json.dumps(motif["ui_text"], ensure_ascii=False, indent=1) + "\n")
    print("ok", len(FILES), "Dateien nach", ART)


if __name__ == "__main__":
    main()
