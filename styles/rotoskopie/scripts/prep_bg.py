#!/usr/bin/env python3
"""KI-Hintergrund (assets/raw/bg.png, agy 1264×848) an der Blender-Vorlage messen, auf das Spielbild schneiden
und Masken/Lichtpunkte für die Demo ableiten.

    .venv/bin/python styles/rotoskopie/scripts/prep_bg.py

1. Auf 1536×1024 hochrechnen (Lanczos), Deckung mit assets/ref/harbor_layout.png messen: normierte
   Kreuzkorrelation der Kantenstärke (Sobel) über Maßstab 0,97–1,03 und Verschiebung ±24 px.
2. Den 16:9-Ausschnitt (Zeilen 160–1024 der Vorlage) mit dieser Lage abtasten -> demo/art/bg.png (1280×720).
3. Lichtpunkte (Leuchtfeuer, Laterne, Fenster) als helle, gelbe Flecken nahe der aus 3D projizierten Lage
   suchen, Wassermaske (R) über den Farbton zwischen Horizont und Kaikante -> demo/art/bg_mask.png (RGB, nicht
   im Alphakanal), Messwerte -> assets/bg.json; bg.png und bg_mask.png zusätzlich als Kopie in assets/.
"""
import json, shutil

import numpy as np
from PIL import Image

from rs_common import ENTRY

RAW = ENTRY / "assets/raw/bg.png"
LAYOUT = ENTRY / "assets/ref/harbor_layout.png"
lay_info = json.loads(LAYOUT.with_suffix(".json").read_text())
ART = ENTRY / "demo/art"
ART.mkdir(parents=True, exist_ok=True)

src = Image.open(RAW).convert("RGB")
big = src.resize((1536, 1024), Image.LANCZOS)
lay = Image.open(LAYOUT).convert("RGB")


def grad(im, k=2):
    g = np.asarray(im.convert("L").resize((im.width // k, im.height // k), Image.BOX), np.float32)
    gx = np.zeros_like(g); gy = np.zeros_like(g)
    gx[:, 1:-1] = g[:, 2:] - g[:, :-2]
    gy[1:-1] = g[2:] - g[:-2]
    m = np.hypot(gx, gy)
    return m


def ncc(a, b):
    a = a - a.mean(); b = b - b.mean()
    return float((a * b).sum() / np.sqrt((a * a).sum() * (b * b).sum()))


# Deckung: Vorlage fest, KI-Bild um (cx, cy) skaliert und verschoben; gemessen nur im Bereich unterhalb des
# Himmels (Zeilen 300–1000), weil der Himmel der Vorlage leer ist
K = 2
gl = grad(lay, K)
roi = (slice(300 // K, 1000 // K), slice(40 // K, 1496 // K))
best = (-2, 1.0, 0, 0)
for s in np.arange(0.97, 1.0301, 0.01):
    w, h = round(1536 * s), round(1024 * s)
    im = big.resize((w, h), Image.BILINEAR)
    for dy in range(-24, 25, 4):
        for dx in range(-24, 25, 4):
            ox, oy = (1536 - w) / 2 + dx, (1024 - h) / 2 + dy
            canvas = Image.new("RGB", (1536, 1024))
            canvas.paste(im, (round(ox), round(oy)))
            v = ncc(grad(canvas, K)[roi], gl[roi])
            if v > best[0]:
                best = (v, float(s), dx, dy)
# Feinsuche um das beste Ergebnis
s0, dx0, dy0 = best[1], best[2], best[3]
for s in np.arange(s0 - 0.008, s0 + 0.0081, 0.004):
    w, h = round(1536 * s), round(1024 * s)
    im = big.resize((w, h), Image.BILINEAR)
    for dy in range(dy0 - 4, dy0 + 5):
        for dx in range(dx0 - 4, dx0 + 5):
            ox, oy = (1536 - w) / 2 + dx, (1024 - h) / 2 + dy
            canvas = Image.new("RGB", (1536, 1024))
            canvas.paste(im, (round(ox), round(oy)))
            v = ncc(grad(canvas, K)[roi], gl[roi])
            if v > best[0]:
                best = (v, float(s), dx, dy)
v0 = ncc(grad(big, K)[roi], gl[roi])
print(f"Deckung KI/Vorlage: NCC ohne Korrektur {v0:.3f}, beste {best[0]:.3f} bei Maßstab {best[1]:.3f}, "
      f"Versatz {best[2]:+d}/{best[3]:+d} px (1536er Maß)")

# 2. Ausschnitt: Vorlagenpixel p -> KI-Pixel q = (p - c - d) / s + c (c = Bildmitte), dann 1536->1264 Rohmaß
s, dx, dy = best[1], best[2], best[3]
top = lay_info["crop_rows"][0]
c = np.array([768.0, 512.0])


def lay_to_raw(px, py):
    qx = (px - c[0] - dx) / s + c[0]
    qy = (py - c[1] - dy) / s + c[1]
    return qx * src.width / 1536, qy * src.height / 1024


x0, y0 = lay_to_raw(0, top)
x1, y1 = lay_to_raw(1536, 1024)
PAD = 16                                                    # Rand wiederholen: der Ausschnitt ragt knapp hinaus
srcp = Image.fromarray(np.pad(np.asarray(src), ((PAD, PAD), (PAD, PAD), (0, 0)), mode="edge"))
bg = srcp.resize((1280, 720), Image.LANCZOS, box=(x0 + PAD, y0 + PAD, x1 + PAD, y1 + PAD))
bg.save(ART / "bg.png", optimize=True)
arr = np.asarray(bg).astype(np.float32)

# 3. Lichtpunkte: hell und gelb (R, G hoch, B deutlich kleiner) nahe der projizierten Lage
marks = lay_info["marks_game_px"]
r, g, b = arr[..., 0], arr[..., 1], arr[..., 2]
warm = (r > 200) & (g > 150) & (b < 0.75 * g)


def blob(cx, cy, rad):
    ys, xs = np.mgrid[0:720, 0:1280]
    sel = warm & ((xs - cx) ** 2 + (ys - cy) ** 2 < rad * rad)
    if sel.sum() < 4:
        return None
    w = (r + g)[sel]
    return [round(float((xs[sel] * w).sum() / w.sum()), 1), round(float((ys[sel] * w).sum() / w.sum()), 1),
            int(sel.sum())]


lights = {"lighthouse": blob(*marks["LighthouseLight"], 30), "lantern": blob(*marks["LanternLight"], 30),
          "side_window": blob(270, 430, 60)}
print("Lichtpunkte (KI-Bild) gegen 3D-Projektion:", lights, {k: marks[k] for k in ("LighthouseLight", "LanternLight")})

# Wassermaske über den Farbton: türkis/blau, zwischen Horizont und Kaikante
mx = arr.max(-1); mn = arr.min(-1)
sat = (mx - mn) / np.maximum(mx, 1)
hue_ok = (b > r + 25) & (g > r + 10)
ys = np.mgrid[0:720, 0:1280][0]
water = hue_ok & (sat > 0.3) & (ys > 343) & (ys < 540)
mask = np.zeros((720, 1280, 3), np.uint8)
mask[..., 0] = water * 255
Image.fromarray(mask, "RGB").save(ART / "bg_mask.png", optimize=True)
rows = np.nonzero(water.any(1))[0]
info = {"layout_ncc_raw": round(v0, 3), "layout_ncc_best": round(best[0], 3), "scale": round(s, 4),
        "shift_px_1536": [dx, dy], "crop_raw_box": [round(x0, 2), round(y0, 2), round(x1, 2), round(y1, 2)],
        "lights_ai": lights, "marks_3d": marks, "water_rows": [int(rows.min()), int(rows.max())],
        "water_px": int(water.sum())}
(ENTRY / "assets/bg.json").write_text(json.dumps(info, indent=1))
for n in ("bg.png", "bg_mask.png"):                         # verarbeitete Assets auch in assets/ (Kopie wie Vertrag)
    shutil.copyfile(ART / n, ENTRY / "assets" / n)
print(json.dumps(info, indent=1))
