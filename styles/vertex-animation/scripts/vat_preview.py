#!/usr/bin/env python3
"""Vorschaubilder für den Katalog: die vier VAT-Texturen als Bild und vier Bilder der Stoffsimulation.

    .venv/bin/python styles/vertex-animation/scripts/vat_preview.py [--flag-frames DIR]

1. assets/vat_textures.png: flag_pos, flag_nrm, gull_pos, gull_nrm (demo/vat/*.exr, Half Float, unkomprimiert)
   nebeneinander, Werte auf Farben abgebildet (Versatz: 0,5 + v · Verstärkung; Normale: 0,5 + 0,5 · n),
   ohne Glättung vergrößert. Spalte = Punkt, Zeile = Bild (oben Bild 0).
2. assets/flag_sim.png (nur mit --flag-frames): vier Workbench-Bilder der Stoffsimulation aus
   blender/build_vat.py --preview DIR, im Abstand von 0,5 s.
"""
import argparse
import pathlib
import struct

import numpy as np
from PIL import Image, ImageDraw, ImageFont

ROOT = pathlib.Path(__file__).resolve().parents[3]
BASE = ROOT / "styles" / "vertex-animation"
ap = argparse.ArgumentParser()
ap.add_argument("--flag-frames", default="")
a = ap.parse_args()


def read_exr(path):
    """Unkomprimiertes Scanline-EXR (Half) -> (Zeilen, Spalten, 3) float32, Kanäle R, G, B."""
    data = path.read_bytes()
    pos, attrs = 8, {}
    while data[pos] != 0:
        end = data.index(b"\0", pos)
        name = data[pos:end].decode()
        end2 = data.index(b"\0", end + 1)
        size = struct.unpack("<i", data[end2 + 1:end2 + 5])[0]
        attrs[name] = data[end2 + 5:end2 + 5 + size]
        pos = end2 + 5 + size
    pos += 1
    assert attrs["compression"][0] == 0
    ch, names, p = attrs["channels"], [], 0
    while ch[p] != 0:
        end = ch.index(b"\0", p)
        names.append(ch[p:end].decode())
        p = end + 17
    x0, y0, x1, y1 = struct.unpack("<4i", attrs["dataWindow"])
    w, h = x1 - x0 + 1, y1 - y0 + 1
    offs = struct.unpack(f"<{h}Q", data[pos:pos + 8 * h])
    out = np.zeros((h, len(names), w), np.float32)
    for off in offs:
        y = struct.unpack("<i", data[off:off + 4])[0] - y0
        out[y] = np.frombuffer(data, np.float16, count=w * len(names), offset=off + 8).reshape(len(names), w)
    return np.stack([out[:, names.index(c), :] for c in "RGB"], axis=-1)


font = ImageFont.load_default(size=13)
panels = []
for name, kind, gain, scale in (("flag_pos", "Versatz", 0.6, 1), ("flag_nrm", "Normale", 0.5, 1),
                                ("gull_pos", "Versatz", 1.3, 3), ("gull_nrm", "Normale", 0.5, 3)):
    v = read_exr(BASE / "demo" / "vat" / f"{name}.exr")
    rgb = np.clip(v * gain + 0.5, 0, 1)
    im = Image.fromarray((rgb * 255 + 0.5).astype(np.uint8)).resize((v.shape[1] * scale, v.shape[0] * scale), Image.NEAREST)
    panels.append((f"{name}.exr · {kind} · {v.shape[1]} Punkte x {v.shape[0]} Bilder", im))
W = max(im.width for _, im in panels) + 32
H = sum(im.height + 34 for _, im in panels) + 16
sheet = Image.new("RGB", (W, H), (22, 26, 33))
d = ImageDraw.Draw(sheet)
y = 12
for label, im in panels:
    d.text((16, y), label, fill=(225, 220, 210), font=font)
    sheet.paste(im, (16, y + 20))
    y += im.height + 34
sheet.save(BASE / "assets" / "vat_textures.png", optimize=True)
print("vat_textures.png", sheet.size)

if a.flag_frames:
    fs = sorted(pathlib.Path(a.flag_frames).glob("flag_*.png"))
    ims = [Image.open(f).convert("RGB") for f in fs]
    w, h = ims[0].size
    strip = Image.new("RGB", (w * len(ims), h + 22), (22, 26, 33))
    d = ImageDraw.Draw(strip)
    for i, im in enumerate(ims):
        strip.paste(im, (i * w, 22))
        d.text((i * w + 8, 4), f"Schleifenbild {40 + 15 * i} (t = {(40 + 15 * i) / 30:.1f} s)", fill=(225, 220, 210), font=font)
    strip.save(BASE / "assets" / "flag_sim.png", optimize=True)
    print("flag_sim.png", strip.size)
