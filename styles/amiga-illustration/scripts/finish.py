#!/usr/bin/env python3
"""Verarbeitet alles, was in assets/raw/ liegt, baut die Demo-Daten neu und prüft sie.

    .venv/bin/python styles/amiga-illustration/scripts/finish.py CHECKDIR [--capture]

1. Hafenbild: assets/raw/bg.png (Auftrag 1), sonst das Blender-Rendering assets/raw/bg3d (Rückfallweg; seit dem
   KI-Bild gelöscht, bei Bedarf mit blender/render_bg.py neu rendern)
   -> assets/ und demo/art/: picture_index.png, palette.json, badger.png/.json; Erkanntes in assets/picture_detect.json
2. Nahaufnahme: assets/raw/closeup.png (Auftrag 2) -> closeup_index.png, closeup_palette.json; fehlt das Bild,
   werden alte Nahaufnahme-Dateien aus demo/art/ entfernt (die Demo zeigt dann nur das Hafenbild)
3. godot --import, Probelauf (scripts/probe.py: Farben je Bild, 12-Bit-Raster, Fußzeilen des Dachses)
4. mit --capture: tools/capture.py --poster-at 0.85 (Poster bei 5,1 s in der Nahaufnahme: Dachs groß, Antwortzeile
   steht; PIPELINE.md → Figuren und Animation: Poster in die Nahaufnahme legen)
Prüfbilder landen in CHECKDIR (temporär, außerhalb des Projekts) und in assets/raw/ (*_x3.png).
"""
import argparse
import json
import pathlib
import subprocess
import sys

STYLE = pathlib.Path(__file__).resolve().parent.parent
ROOT = STYLE.parent.parent
PY = str(ROOT / ".venv/bin/python")


def run(cmd, **kw):
    print("$", " ".join(str(c) for c in cmd), flush=True)
    r = subprocess.run([str(c) for c in cmd], capture_output=True, text=True, **kw)
    out = (r.stdout + r.stderr).strip()
    if out:
        print("\n".join(out.splitlines()[-12:]))
    if r.returncode:
        sys.exit(f"Fehler ({r.returncode}) bei {cmd[1] if len(cmd) > 1 else cmd[0]}")
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("checkdir")
    ap.add_argument("--capture", action="store_true")
    ap.add_argument("--bg", help="nur zum Testen: anderes Hafenbild (absoluter Pfad) statt assets/raw/bg.png")
    ap.add_argument("--closeup", help="nur zum Testen: andere Nahaufnahme statt assets/raw/closeup.png")
    a = ap.parse_args()
    raw = STYLE / "assets/raw"
    run([PY, STYLE / "scripts/build_assets.py", "--preview"] + (["--source", "ai", "--ai-image", a.bg] if a.bg else []))
    art = STYLE / "demo/art"
    if a.closeup or (raw / "closeup.png").exists():
        run([PY, STYLE / "scripts/build_assets.py", "--picture", "closeup", "--preview"]
            + (["--ai-image", a.closeup] if a.closeup else []))
    else:
        for f in ("closeup_index.png", "closeup_index.png.import", "closeup_palette.json"):
            (art / f).unlink(missing_ok=True)
        for f in ("closeup_index.png", "closeup_palette.json", "closeup_preview.png", "closeup_detect.json"):
            (STYLE / "assets" / f).unlink(missing_ok=True)
        print("keine Nahaufnahme (assets/raw/closeup.png fehlt): Demo zeigt nur das Hafenbild")
    out = run(["godot", "--headless", "--path", STYLE / "demo", "--import"])
    errs = [l for l in out.splitlines() if "ERROR" in l]
    if errs:
        sys.exit("Godot-Import meldet Fehler:\n" + "\n".join(errs[:10]))
    run([PY, STYLE / "scripts/probe.py", a.checkdir, "--feet"])
    for name in ("picture_detect.json", "closeup_detect.json"):
        p = STYLE / "assets" / name
        if p.exists():
            print(name, json.dumps(json.loads(p.read_text()), ensure_ascii=False))
    print("Prüfbilder:", raw / "picture_preview_x3.png", raw / "picture_masks_x3.png",
          raw / "closeup_preview_x3.png", raw / "closeup_masks_x3.png", a.checkdir, sep="\n  ")
    if a.capture:
        run([PY, ROOT / "tools/capture.py", STYLE, "--poster-at", "0.85"], cwd=ROOT)


if __name__ == "__main__":
    main()
