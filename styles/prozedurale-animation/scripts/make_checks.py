#!/usr/bin/env python3
"""Prüfbilder für den Eintrag.

    .venv/bin/python -I styles/prozedurale-animation/scripts/make_checks.py

assets/check/rig_rest.png    KI-Vorlage (links) neben der Ruhelage aus den Teilen mit Gelenken und Ankern (rechts)
assets/check/motion_strip.png  Godot-Ausgabe nur des Dachses mit Kontaktschatten: Gehen (jedes 3. Bild) und Anhalten
                               mit Nachschwingen (Halt ab 3,4 s, Schal am weitesten vorn bei etwa 4,07 s)
"""
import json, pathlib, subprocess, tempfile

import numpy as np
from PIL import Image, ImageDraw

SD = pathlib.Path(__file__).resolve().parents[1]
AS = SD / "assets"
OUT = AS / "check"
OUT.mkdir(parents=True, exist_ok=True)
R = json.loads((AS / "rig.json").read_text())
K = 2.0                      # Darstellung: Texturpixel x 2
BG = (118, 132, 150, 255)


def v(a):
    return np.array([float(a[0]), float(a[1])])


# ---------------------------------------------------------------- Ruhelage
W, H = 700, 620
can = Image.new("RGBA", (W, H), BG)
asm = Image.open(AS / "badger_assembled.png")
asm = asm.resize((int(asm.width * K), int(asm.height * K)), Image.LANCZOS)
ox, oy = 500, 590          # Ursprung (Boden unter der nahen Hüfte) der rechten Figur in Bildpixeln
lx = ox - 310              # linke Figur: KI-Vorlage im selben Maßstab, gleicher Boden


def paste(img_path, org, dark=None, origin=(ox, oy)):
    im = Image.open(AS / img_path)
    im = im.resize((int(im.width * K), int(im.height * K)), Image.LANCZOS)
    if dark is not None:
        a = np.asarray(im).astype(np.float32)
        a[..., :3] *= dark
        im = Image.fromarray(a.clip(0, 255).astype(np.uint8))
    can.alpha_composite(im, (int(origin[0] + org[0] * K), int(origin[1] + org[1] * K)))


paste("badger_assembled.png", v(R["assembled_origin"]), origin=(lx, oy))
far = v(R["leg_tex_origin"]) + v(R["far_leg_offset"])
paste("badger_leg.png", far, dark=0.62)
paste("badger_leg.png", v(R["leg_tex_origin"]))
paste("badger_body.png", v(R["body_tex_origin"]))
d = ImageDraw.Draw(can)


def P(p):
    return (ox + p[0] * K, oy + p[1] * K)


ll = R["leg_local"]
lo = v(R["leg_tex_origin"])
pts = [lo + v(ll[k]) for k in ("hip", "knee", "ankle")]
d.line([P(p) for p in pts], fill=(255, 150, 60), width=3)
for p in pts:
    x, y = P(p); d.ellipse([x - 5, y - 5, x + 5, y + 5], fill=(255, 150, 60))
cap = R["back_capsule"]
for c in (cap["a"], cap["b"]):
    x, y = P(v(c)); r = cap["r"] * K
    d.ellipse([x - r, y - r, x + r, y + r], outline=(110, 220, 255), width=2)
for key, col in (("scarf_anchor", (255, 100, 120)), ("strap_anchor", (110, 220, 255)), ("eye", (255, 230, 90))):
    x, y = P(v(R[key])); d.ellipse([x - 6, y - 6, x + 6, y + 6], outline=col, width=3)
x, y = P(v(R["body_pivot"])); d.line([x - 10, y, x + 10, y], fill=(255, 220, 80), width=3); d.line([x, y - 10, x, y + 10], fill=(255, 220, 80), width=3)
d.line([0, oy, W, oy], fill=(40, 40, 50), width=1)
d.text((10, 8), "KI-Vorlage (Gesamtfigur)", fill=(255, 255, 255))
d.text((380, 8), "Ruhelage aus Teilen + Gelenke/Anker", fill=(255, 255, 255))
can.convert("RGB").save(OUT / "rig_rest.png")

# ---------------------------------------------------------------- Bewegungsstreifen
with tempfile.TemporaryDirectory(prefix="pa-strip-") as tds:
    td = pathlib.Path(tds)
    subprocess.run(["godot", "--headless", "--path", str(SD / "demo"), "--import"], capture_output=True)
    subprocess.run(["godot", "--path", str(SD / "demo"), "--position", "20000,20000", "--resolution", "1280x720",
                    "--write-movie", str(td / "f.png"), "--fixed-fps", "30", "--quit-after", "150",
                    "--", "--only=near_leg,far_leg,body,scarf,strap,shadow", "--keycol=%.4f,%.4f,%.4f" % tuple(c / 255 for c in BG[:3])], capture_output=True)
    walk = list(range(40, 59, 3))
    stop = [100, 106, 110, 114, 118, 122, 128, 140]
    tiles = []
    for f in walk + stop:
        im = np.asarray(Image.open(td / f"f{f:08d}.png").convert("RGB")).astype(int)
        m = np.abs(im - np.array(BG[:3])).sum(-1) <= 6
        xs = np.nonzero((~m).any(0))[0]
        cx = int(xs.mean())
        tile = Image.fromarray(im.astype(np.uint8)).crop((cx - 85, 385, cx + 75, 600))
        dd = ImageDraw.Draw(tile)
        dd.line([0, 585 - 385, 160, 585 - 385], fill=(40, 40, 50))
        dd.text((4, 4), f"{f / 30:.2f} s", fill=(255, 255, 255))   # Bild f zeigt t = f / 30 (Bildzähler-Zeit in main.gd)
        tiles.append(tile)
    strip = Image.new("RGB", (160 * len(tiles), 215), BG[:3])
    for i, t in enumerate(tiles):
        strip.paste(t, (160 * i, 0))
    strip.save(OUT / "motion_strip.png")
print("ok", OUT)
