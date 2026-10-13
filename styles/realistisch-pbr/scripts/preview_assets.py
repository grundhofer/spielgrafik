#!/usr/bin/env python3
"""Übersichtsbilder für den Katalog (assets/preview/):
  textures.jpg        je Material Grundfarbe | Normalen | ORM (AO, Rauheit, Metall) aus demo/textures
  sky.jpg             sichtbares Himmelsband (sky_band.hdr), wie in der Demo belichtet und getönt
  badger_closeup.jpg  Nahaufnahme des Dachses (Fellschalen, Stoffe), aus der Demo gerendert

    .venv/bin/python styles/realistisch-pbr/scripts/preview_assets.py
"""
import pathlib
import subprocess
import sys
import tempfile

import numpy as np
from PIL import Image, ImageDraw

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from rgbe_io import read_hdr  # noqa: E402

ENTRY = pathlib.Path(__file__).resolve().parent.parent
TEX = ENTRY / "demo" / "textures"
OUT = ENTRY / "assets" / "preview"


def textures():
    names = sorted({p.name.rsplit("_", 1)[0] for p in TEX.glob("*_a.*") if not p.name.endswith(".import")})
    cell = 120
    cols = 3  # Materialien je Zeile (je 3 Karten)
    rows = (len(names) + cols - 1) // cols
    im = Image.new("RGB", (cols * (3 * cell + 12), rows * (cell + 16)), (18, 18, 20))
    d = ImageDraw.Draw(im)
    for i, n in enumerate(names):
        x0 = (i % cols) * (3 * cell + 12)
        y0 = (i // cols) * (cell + 16)
        for j, suf in enumerate(("a", "n", "orm")):
            f = next(iter(sorted(TEX.glob(f"{n}_{suf}.*"), key=lambda p: p.suffix == ".import")), None)
            if f is None or f.suffix == ".import":
                continue
            t = Image.open(f).convert("RGB").resize((cell, cell), Image.LANCZOS)
            im.paste(t, (x0 + j * cell, y0 + 14))
        d.text((x0 + 2, y0 + 1), n, fill=(230, 230, 230))
    im.save(OUT / "textures.jpg", quality=85)


def sky():
    band = read_hdr(ENTRY / "demo" / "sky" / "sky_band.hdr")
    h = band.shape[0]
    # wie sky.gdshader: Belichtung 0,16, oben kühler, am Horizont wärmer (Höhe 40° … -8°)
    elev = np.linspace(40, -8, h)[:, None, None]
    e = np.clip(np.sin(np.radians(elev)), 0, 1) ** 0.45
    tint = np.array([1.25, 0.85, 0.6]) * (1 - e) + np.array([0.45, 0.55, 0.95]) * e
    c = band * 0.16 * tint
    c = c / (1 + c)        # einfache Abbildung, nur zur Ansicht
    c = np.clip(c, 0, 1) ** (1 / 2.2)
    Image.fromarray((c * 255).astype(np.uint8)).resize((1365, 410), Image.LANCZOS).save(OUT / "sky.jpg", quality=86)


def closeup():
    with tempfile.TemporaryDirectory() as td:
        out = pathlib.Path(td) / "c.png"
        subprocess.run([sys.executable, str(ENTRY / "scripts" / "snap.py"), str(out), "--frames", "30", "--",
                        "--cam=-1.15,0.85,2.9,-1.4,0.62,1.65,34", "--t0=5.0", "--no-ui", "--no-dof"],
                       check=True, capture_output=True)
        Image.open(out).convert("RGB").save(OUT / "badger_closeup.jpg", quality=88)


if __name__ == "__main__":
    OUT.mkdir(parents=True, exist_ok=True)
    textures()
    sky()
    closeup()
    print("ok", OUT)
