#!/usr/bin/env python3
"""Kopiert die verarbeiteten Assets in das Godot-Projekt (demo/art) und setzt Importparameter.

Puppenteile werden 2x gespeichert und mit 0,5 gezeichnet: dafür Mipmaps einschalten. Nach dem ersten Import
werden die .import-Dateien angepasst und neu importiert.

    .venv/bin/python styles/papier-collage/scripts/build_demo.py
"""
import pathlib, re, shutil, subprocess

HERE = pathlib.Path(__file__).resolve().parent.parent
ART = HERE / "demo" / "art"
for sub in ("scene", "puppet", "ui"):
    dst = ART / sub
    dst.mkdir(parents=True, exist_ok=True)
    for f in (HERE / "assets" / sub).iterdir():
        if f.suffix in (".png", ".json"):
            shutil.copy2(f, dst / f.name)
subprocess.run(["godot", "--headless", "--path", str(HERE / "demo"), "--import"], capture_output=True)
changed = 0
for imp in ART.glob("**/*.png.import"):
    s = imp.read_text()
    want_mip = imp.parent.name in ("puppet", "ui") or imp.name.startswith(("gull", "smoke"))
    s2 = re.sub(r"mipmaps/generate=\w+", f"mipmaps/generate={'true' if want_mip else 'false'}", s)
    if s2 != s:
        imp.write_text(s2); changed += 1
if changed:
    subprocess.run(["godot", "--headless", "--path", str(HERE / "demo"), "--import"], capture_output=True)
print("ok", changed, "Importdateien angepasst")
