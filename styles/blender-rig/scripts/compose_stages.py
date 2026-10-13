#!/usr/bin/env python3
"""Setzt die Blender-Renders aus blender/stages.py zu beschrifteten Tafeln zusammen.

    blender -b --factory-startup -P styles/blender-rig/blender/stages.py -- --tmp <Temp>
    .venv/bin/python styles/blender-rig/scripts/compose_stages.py --tmp <Temp>

Schreibt nach styles/blender-rig/assets/stages/:
  1_grundformen.png  2_rig.png  3_gewichte.png  4_walk.png  und die Übersicht blender_stages.png
"""
import argparse
import json
import pathlib

from PIL import Image, ImageDraw, ImageFont

HERE = pathlib.Path(__file__).resolve().parent
ENTRY = HERE.parent
FONTS = ENTRY / "demo" / "fonts"
ap = argparse.ArgumentParser()
ap.add_argument("--tmp", required=True)
ap.add_argument("--out", default=str(ENTRY / "assets" / "stages"))
a = ap.parse_args()
tmp, out = pathlib.Path(a.tmp), pathlib.Path(a.out)
out.mkdir(parents=True, exist_ok=True)
stats = json.loads((tmp / "stages.json").read_text())
curves = json.loads((tmp / "walk_curves.json").read_text())

BG = (34, 38, 48, 255)
TEXT = (236, 240, 246)
DIM = (160, 170, 188)
COL_L = (77, 209, 255)
COL_R = (255, 107, 184)


def font(size, bold=True):
    f = ImageFont.truetype(str(FONTS / "Nunito.ttf"), size)
    try:
        f.set_variation_by_axes([800 if bold else 600])
    except Exception:      # ohne Variationsunterstützung: Standardschnitt
        pass
    return f


MONO = ImageFont.truetype(str(FONTS / "IBMPlexMono-Regular.ttf"), 17)
MONO_S = ImageFont.truetype(str(FONTS / "IBMPlexMono-Regular.ttf"), 15)


def layer(name, alpha=1.0):
    im = Image.open(tmp / name).convert("RGBA")
    if alpha < 1.0:
        r, g, b, al = im.split()
        im = Image.merge("RGBA", (r, g, b, al.point(lambda v: int(v * alpha))))
    return im


def panel(size, layers, num, title, lines):
    w, h = size
    head = 118
    im = Image.new("RGBA", (w, h + head), BG)
    for l in layers:
        im.alpha_composite(l, ((w - l.width) // 2, head))
    d = ImageDraw.Draw(im)
    d.ellipse([24, 26, 62, 64], fill=(92, 200, 255))
    d.text((43, 45), str(num), font=font(24), fill=(20, 24, 32), anchor="mm")
    d.text((76, 28), title, font=font(30), fill=TEXT)
    y = 70
    for ln in lines:
        d.text((76, y), ln, font=MONO, fill=DIM)
        y += 22
    return im


p1 = panel((720, 900), [layer("parts.png")], 1, "Grundformen per Skript",
           [f"{stats['loose_parts']} geschlossene Teile, keine Vorlage",
            "Ring-Lofts, Ellipsoide, Röhren, Quader"])
p2 = panel((720, 900), [layer("body.png"), layer("bones.png", 0.92)], 2, "Eigenes Deform-Rig",
           [f"{stats['bones']} Knochen statt Rigify, Ruhepose",
            "Mitte · links (.L) · rechts (.R) · Schal/Schwanz"])
p3 = panel((720, 900), [layer("weights.png"), layer("bones.png", 0.35)], 3, "Gewichte je Körperteil",
           ["Bone Heat nur mit den passenden Knochen,",
            "Kopf, Paket, Krallen starr; Farbe = Knochen"])
p1.save(out / "1_grundformen.png")
p2.save(out / "2_rig.png")
p3.save(out / "3_gewichte.png")

# Walk: 6 Schlüssel nebeneinander + Kurve der Knöchelhöhe über alle 31 Schlüssel
walk = Image.new("RGBA", (1800, 560), (0, 0, 0, 0))
walk.alpha_composite(layer("walk.png"))
walk.alpha_composite(layer("walk_bones.png", 0.72))
chart_h = 250
p4 = Image.new("RGBA", (2160, 118 + 560 + 34 + chart_h + 40), BG)
p4.alpha_composite(walk, (180, 118))
d = ImageDraw.Draw(p4)
d.ellipse([24, 26, 62, 64], fill=(92, 200, 255))
d.text((43, 45), "4", font=font(24), fill=(20, 24, 32), anchor="mm")
d.text((76, 28), "Keyframes per Skript: Walk", font=font(30), fill=TEXT)
d.text((76, 70), "Pose je Bild aus Formeln (Becken, Gegendrehung, Zwei-Gelenk-IK der Beine), jedes der 31 Bilder"
                 " ein Schlüssel; Export gesampelt mit Idle (61) und Wave (46) in einer glb", font=MONO, fill=DIM)
for i, f in enumerate(stats["walk_keys"]):
    cx = 180 + int((i + 0.5) * 1800 / len(stats["walk_keys"]))
    d.text((cx, 118 + 560 + 22), f"Bild {f}", font=MONO_S, fill=TEXT, anchor="ms")
# Kurve
x0, x1 = 240, 2100
y0 = 118 + 560 + 34 + 30
yb = y0 + chart_h - 50
lift = max(max(curves["L_ankle"]), max(curves["R_ankle"])) - min(curves["L_ankle"])
base = min(curves["L_ankle"] + curves["R_ankle"])


def px(i, v):
    return x0 + i * (x1 - x0) / 30, yb - (v - base) / max(lift, 1e-6) * (chart_h - 80)


d.line([(x0, yb), (x1, yb)], fill=(90, 98, 115), width=2)
d.text((x0 - 14, yb), "Boden", font=MONO_S, fill=DIM, anchor="rm")
d.text((x0 - 14, px(0, base + lift)[1]), f"+{lift * 100:.1f} cm", font=MONO_S, fill=DIM, anchor="rm")
for key, col in (("L_ankle", COL_L), ("R_ankle", COL_R)):
    pts = [px(i, v) for i, v in enumerate(curves[key])]
    d.line(pts, fill=col, width=3)
    for p in pts:
        d.ellipse([p[0] - 5, p[1] - 5, p[0] + 5, p[1] + 5], fill=col, outline=(20, 24, 32))
for i in range(0, 31, 5):
    d.text((px(i, base)[0], yb + 26), str(i), font=MONO_S, fill=DIM, anchor="ms")
d.text((x1, y0 - 4), "Knöchelhöhe in den 31 Schlüsseln (Punkte): links cyan, rechts rosa", font=MONO_S,
       fill=DIM, anchor="rs")
p4.save(out / "4_walk.png")

# Übersicht: oben 1–3, unten 4
top = Image.new("RGBA", (2160, p1.height), BG)
for i, p in enumerate((p1, p2, p3)):
    top.alpha_composite(p, (i * 720, 0))
sheet = Image.new("RGBA", (2160, top.height + p4.height), BG)
sheet.alpha_composite(top, (0, 0))
sheet.alpha_composite(p4, (0, top.height))
d = ImageDraw.Draw(sheet)
d.line([(24, top.height), (2136, top.height)], fill=(70, 78, 95), width=2)
sheet = sheet.convert("RGB")
sheet.save(out / "blender_stages.png")
sheet.resize((sheet.width // 2, sheet.height // 2), Image.LANCZOS).save(out / "blender_stages_small.jpg", quality=88)
print("geschrieben:", *sorted(p.name for p in out.iterdir()))
