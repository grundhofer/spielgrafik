#!/usr/bin/env python3
"""Vergleichsbilder für den Katalog (assets/preview/).

    .venv/bin/python styles/gemaltes-3d/scripts/make_previews.py

stages.png   Endeinstellung bei 5,0 s ohne Oberfläche: ungemaltes 3D-Bild | Steuerkarte | gemaltes Bild
presets.png  Voreinstellung "gouache" (Aufnahme) | Voreinstellung "aquarell", mit Oberfläche
"""
import pathlib, subprocess, tempfile
from PIL import Image

HERE = pathlib.Path(__file__).resolve().parent
OUT = HERE.parent / "assets" / "preview"


def snap(t, *args):
    with tempfile.TemporaryDirectory() as td:
        p = pathlib.Path(td) / "s.png"
        subprocess.run([str(HERE / "snap.sh"), str(p), f"{t}", *args], check=True, capture_output=True, text=True)
        return Image.open(p).convert("RGB")


def row(ims, w=640, h=360):
    sheet = Image.new("RGB", (w * len(ims), h))
    for i, im in enumerate(ims):
        sheet.paste(im.resize((w, h), Image.LANCZOS), (i * w, 0))
    return sheet


OUT.mkdir(parents=True, exist_ok=True)
row([snap(5.0, "--raw", "--no-ui"), snap(5.0, "--show-ctrl", "--no-ui"), snap(5.0, "--no-ui")]).save(OUT / "stages.png")
row([snap(5.0), snap(5.0, "--preset=aquarell")]).save(OUT / "presets.png")
print("geschrieben:", OUT / "stages.png", OUT / "presets.png")
