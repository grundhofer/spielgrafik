#!/usr/bin/env python3
"""Kontrollbild: Clean Plate, Ebenen vor Magenta und vor Schwarz, Parallax-Verschiebung (Kamera 110 px)."""
import pathlib, sys
from PIL import Image
S = pathlib.Path(__file__).resolve().parent.parent
L = S / "assets" / "layers"
out = pathlib.Path(sys.argv[1])
plate = Image.open(L / "plate.png").convert("RGBA")
tiles = [plate]
for name in ("harbour", "headland"):
    im = Image.open(L / f"{name}.png")
    for col in ((255, 0, 255, 255), (10, 10, 10, 255)):
        bg = Image.new("RGBA", im.size, col); bg.alpha_composite(im); tiles.append(bg)
# Parallax-Probe: Ebenen mit Kamera 110 px verschoben
cam = 110
comp = Image.new("RGBA", plate.size, (0, 0, 0, 255))
comp.alpha_composite(plate, (-int(cam * 0.06), 0))
comp.alpha_composite(Image.open(L / "headland.png"), (-int(cam * 0.3), 0))
comp.alpha_composite(Image.open(L / "harbour.png"), (-cam, 0))
tiles.append(comp)
tw, th = plate.width // 2, plate.height // 2
sheet = Image.new("RGB", (tw * 2, th * 4))
for i, t in enumerate(tiles):
    sheet.paste(t.convert("RGB").resize((tw, th), Image.LANCZOS), ((i % 2) * tw, (i // 2) * th))
sheet.save(out)
