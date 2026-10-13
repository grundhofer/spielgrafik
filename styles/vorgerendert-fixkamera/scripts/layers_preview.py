#!/usr/bin/env python3
"""Übersichtsbild der Ebenen je Einstellung (für die Katalogseite und zum Prüfen).

    .venv/bin/python styles/vorgerendert-fixkamera/scripts/layers_preview.py

Schreibt assets/preview/layers_<shot>.png: ruhendes Bild | Tiefenbild | Lichtebene Laterne (×4 aufgehellt) |
Bewegungsmaske des Overlays (weiß = ändert sich in der Schleife), je 320×240, ×2 vergrößert.
"""
import json
import pathlib

import numpy as np
from PIL import Image, ImageDraw

STYLE = pathlib.Path(__file__).resolve().parent.parent


def main():
    out = STYLE / "assets" / "preview"
    out.mkdir(parents=True, exist_ok=True)
    for shot in ("totale", "nah"):
        d = STYLE / "assets" / "bg" / shot
        meta = json.loads((d / "meta.json").read_text())
        base = Image.open(d / "base.png").convert("RGB")
        depth = Image.open(d / "depth_preview.png").convert("RGB")
        lan = np.asarray(Image.open(d / "lantern.png").convert("RGB"), dtype=np.float32)
        lan = Image.fromarray(np.clip(lan * 4.0, 0, 255).astype(np.uint8))
        atlas = Image.open(d / "anim.png")
        x, y, w, h = meta["anim"]["rect"]
        a = np.asarray(atlas)[:h, :w, 3]
        mask = np.zeros((240, 320), np.uint8)
        mask[y:y + h, x:x + w] = a
        mask = Image.fromarray(mask).convert("RGB")
        tiles = [("Renderbild (Median der Schleife)", base), ("Tiefenbild", depth),
                 ("Lichtebene Laterne x4", lan), ("bewegte Pixel (Overlay-Maske)", mask)]
        sheet = Image.new("RGB", (640 * 4 + 30, 480 + 26), (16, 16, 18))
        dr = ImageDraw.Draw(sheet)
        for i, (label, im) in enumerate(tiles):
            sheet.paste(im.resize((640, 480), Image.NEAREST), (i * 650, 26))
            dr.text((i * 650 + 4, 6), label, fill=(230, 230, 230))
        sheet.save(out / f"layers_{shot}.png")
        print(out / f"layers_{shot}.png")


if __name__ == "__main__":
    main()
