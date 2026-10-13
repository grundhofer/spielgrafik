#!/usr/bin/env python3
"""Tuschekonturen für die gerenderten Dachs-Bilder: Farbgrenzen + Tiefensprünge -> eine feste Linienstärke.

    .venv/bin/python styles/ligne-claire/scripts/ink_badger.py [--render DIR] [--out DIR] [--line 6] [--down 3]

Eingang: blender/render_badger.py (je Bild Farbpass *_col.png und Tiefenpass *_z.png, render.json).
Ablauf je Bild (in Renderauflösung, ohne Kantenglättung):
  1. Jedes Pixel der nächsten Palettenfarbe zuordnen (Materialnummer, -1 = leer).
  2. Kante, wo ein Nachbar (4er-Nachbarschaft) eine andere Materialnummer hat oder bei gleicher Nummer mehr als
     ZJUMP m weiter vorn/hinten liegt (Arm vor Bein, Bein vor Bein). Beide Seiten werden markiert, die Kante liegt
     also mittig auf der Grenze.
  3. Kante mit einer Kreisscheibe zur festen Linienbreite aufdicken (--line Pixel), schwarz über die flachen Farben
     legen; außen wird die Silhouette um die halbe Linienbreite deckend.
  4. Premultipliziert um den Faktor --down verkleinern (Lanczos): erst hier entsteht die Kantenglättung.
Alle Bilder werden mit demselben Rahmen beschnitten, der Fußpunkt der Figur liegt also in jedem Bild auf demselben
Pixel. Ausgabe: <out>/<prefix>_<reihe>.png (Bilder nebeneinander) und <out>/<prefix>.json.
"""
import argparse, json, pathlib

import numpy as np
from PIL import Image

HERE = pathlib.Path(__file__).resolve().parent.parent
ap = argparse.ArgumentParser()
ap.add_argument("--render", default=str(HERE / "assets/raw/render"))
ap.add_argument("--out", default=str(HERE / "assets"))
ap.add_argument("--line", type=float, default=6.0,
                help="Linienbreite in Renderpixeln (Kantenband 2 px + 2 x Scheibenradius); 6/3 = 2 px (Brustbild), "
                     "kleine Figur 5/3 = 1,7 px (build.sh): beide messen mit line_width.py Median 2 px wie der Hintergrund")
ap.add_argument("--down", type=int, default=3, help="Verkleinerungsfaktor Render -> Sprite")
ap.add_argument("--zjump", type=float, default=0.04, help="Tiefensprung in m, ab dem eine Linie entsteht")
ap.add_argument("--ink", default="141416")
ap.add_argument("--pad", type=int, default=12)
ap.add_argument("--prefix", default="badger", help="Dateinamen: <prefix>_<reihe>.png, <prefix>.json")
ap.add_argument("--full-frame", action="store_true",
                help="ganzes Renderbild behalten (Brustbild): kein Beschnitt, keine Kontur am Bildrand")
ap.add_argument("--face-simple", action="store_true",
                help="kleine Figur: im Kopfbereich keine Linien zwischen hellem und dunklem Fell und keine um Auge, "
                     "Nase und Mund; Auge und Nase als schwarze Punkte mit Mindestgröße")
ap.add_argument("--eye-grow", type=float, default=2.0,
                help="--face-simple: Auge um so viele Renderpixel aufdicken (Mindestgröße als Punkt)")
a = ap.parse_args()

rd, out = pathlib.Path(a.render), pathlib.Path(a.out)
info = json.loads((rd / "render.json").read_text())
names = list(info["palette"])
pal = np.array([[int(h[i:i + 2], 16) for i in (0, 2, 4)] for h in info["palette"].values()], np.int32)
# Füllfarbe je Materialnummer: gleich der Renderfarbe, außer für Hilfsnummern wie "Paw" (gefüllt wie FurDark)
fill_as = info.get("fill_as", {})
pal_fill = np.array([pal[names.index(fill_as.get(n, n))] for n in names], np.int32)
NUM = {n: i for i, n in enumerate(names)}
ink_rgb = np.array([int(a.ink[i:i + 2], 16) for i in (0, 2, 4)], np.float32)
znear, zrange = info["depth"]["near"], info["depth"]["range"]

r = max(0.0, (a.line - 2.0) / 2.0)          # das Kantenband ist schon 2 px breit (beide Seiten der Grenze)
R = int(np.ceil(r))
disk = [(dy, dx) for dy in range(-R, R + 1) for dx in range(-R, R + 1) if dx * dx + dy * dy <= r * r + 0.25]


def shift(m, dy, dx, fill=False, edge=False):
    """m um (dy, dx) verschieben; frei werdende Pixel mit fill füllen oder (edge) den Randwert wiederholen."""
    if edge:
        pad = np.pad(m, ((abs(dy), abs(dy)), (abs(dx), abs(dx))), mode="edge")
        h, w = m.shape
        return pad[abs(dy) - dy:abs(dy) - dy + h, abs(dx) - dx:abs(dx) - dx + w]
    o = np.full_like(m, fill)
    h, w = m.shape
    o[max(0, dy):h + min(0, dy), max(0, dx):w + min(0, dx)] = m[max(0, -dy):h + min(0, -dy), max(0, -dx):w + min(0, -dx)]
    return o


def disk_mask(m, rad):
    """m mit einer Kreisscheibe vom Radius rad aufdicken."""
    R_ = int(np.ceil(rad))
    o = np.zeros_like(m)
    for dy in range(-R_, R_ + 1):
        for dx in range(-R_, R_ + 1):
            if dx * dx + dy * dy <= rad * rad + 0.25:
                o |= shift(m, dy, dx, False)
    return o


def ink_frame(stem, head=None):
    """head: Kopfknochen im Render ([Halsansatz, Scheitel] in Pixeln), nur für --face-simple."""
    col = np.asarray(Image.open(rd / f"{stem}_col.png").convert("RGBA")).astype(np.int32)
    z = np.asarray(Image.open(rd / f"{stem}_z.png")).astype(np.float32) / 65535.0 * zrange + znear
    alpha = col[..., 3] > 127
    d = ((col[..., None, :3] - pal[None, None]) ** 2).sum(-1)
    idx = np.where(alpha, d.argmin(-1), -1)
    far = d.min(-1) > 3 * 12 ** 2
    if (far & alpha).mean() > 0.001:
        print(f"WARNUNG {stem}: {(far & alpha).mean():.2%} Pixel weit weg von der Palette")
    # Kleine Figur: Kopfbereich = alles oberhalb des Halsansatzes (+3 cm für Kinn und Wangen über dem Schal).
    face = np.zeros(idx.shape, bool)
    if a.face_simple and head is not None:
        face[:int(head[0][1] + 0.03 * info["ppm"])] = True
    fur = np.isin(idx, [NUM["FurDark"], NUM["FurLight"]])
    dots = np.isin(idx, [NUM["Eye"], NUM["Nose"]])
    edge = np.zeros(idx.shape, bool)
    for dy, dx in ((0, 1), (1, 0), (0, -1), (-1, 0)):
        ni = shift(idx, dy, dx, -1, edge=a.full_frame)
        nz = shift(z, dy, dx, 0.0, edge=a.full_frame)
        diff = (ni != idx) | ((idx >= 0) & (np.abs(nz - z) > a.zjump))
        if face.any():
            # Im Gesicht der kleinen Figur keine Linie zwischen hellem und dunklem Fell (der Farbwechsel reicht)
            # und keine Kontur um Auge, Nase und Mund (sie werden unten als schwarze Punkte gefüllt).
            nfur = np.isin(ni, [NUM["FurDark"], NUM["FurLight"]])
            ndots = np.isin(ni, [NUM["Eye"], NUM["Nose"]])
            quiet = face & (idx >= 0) & (ni >= 0) & ((fur & nfur) | dots | ndots)
            diff &= ~quiet
        edge |= diff & ((idx >= 0) | (ni >= 0))
    ink = np.zeros_like(edge)
    for dy, dx in disk:
        ink |= shift(edge, dy, dx, False)
    rgb = np.where(idx[..., None] >= 0, pal_fill[np.clip(idx, 0, None)], 0).astype(np.float32)
    rgb[ink] = ink_rgb
    if face.any():
        eye = face & (idx == NUM["Eye"])
        rgb[(disk_mask(eye, a.eye_grow) & (idx >= 0)) | (face & dots)] = ink_rgb
    a_ = (alpha | ink).astype(np.float32)
    return np.dstack([rgb, a_ * 255]).astype(np.uint8), idx, ink


def downscale(rgba, k):
    im = Image.fromarray(rgba, "RGBA").convert("RGBa")
    im = im.resize((rgba.shape[1] // k, rgba.shape[0] // k), Image.LANCZOS)
    return np.asarray(im.convert("RGBA"))


rows = info["rows"]
frames = {}
for name, row in rows.items():
    frames[name] = [ink_frame(f"{name}_{i:02d}", row["feet"][i].get("head_px"))[0] for i in range(row["frames"])]
    print("getuscht:", name, row["frames"])

# Gemeinsamer Rahmen über alle Bilder (vielfaches von down, damit der Fußpunkt ganzzahlig bleibt)
allA = np.zeros(next(iter(frames.values()))[0].shape[:2], bool)
for fl in frames.values():
    for f in fl:
        allA |= f[..., 3] > 0
ys, xs = np.nonzero(allA)
k = a.down
pad = a.pad * k
ox, oy = info["origin_px"]
x0 = int((xs.min() - pad) // k * k); y0 = int((ys.min() - pad) // k * k)
x1 = int(-(-(xs.max() + pad) // k) * k); y1 = int(-(-(ys.max() + pad) // k) * k)
x0, y0 = max(0, x0), max(0, y0)
if a.full_frame:
    x0, y0, x1, y1 = 0, 0, allA.shape[1] // k * k, allA.shape[0] // k * k
fw, fh = (x1 - x0) // k, (y1 - y0) // k
anchor = [(ox - x0) / k, (oy - y0) / k]
ppm = info["ppm"] / k
meta = {"frame_size": [fw, fh], "anchor": anchor, "ppm": ppm, "line_px": a.line / k, "rows": {}}
for name, fl in frames.items():
    sheet = Image.new("RGBA", (fw * len(fl), fh), (0, 0, 0, 0))
    for i, f in enumerate(fl):
        sheet.paste(Image.fromarray(downscale(f[y0:y1, x0:x1], k)), (i * fw, 0))
    sheet.save(out / f"{a.prefix}_{name}.png", optimize=True)
    feet = []
    for fr in rows[name]["feet"]:
        feet.append({s: {"heel": [(fr[s]["heel_px"][0] - x0) / k, (fr[s]["heel_px"][1] - y0) / k],
                         "toe": [(fr[s]["toe_px"][0] - x0) / k, (fr[s]["toe_px"][1] - y0) / k],
                         "heel_x_m": fr[s]["heel_m"][0], "toe_x_m": fr[s]["toe_m"][0],
                         "heel_z_m": fr[s]["heel_m"][2], "toe_z_m": fr[s]["toe_m"][2]} for s in ("L", "R")})
    meta["rows"][name] = {"file": f"{a.prefix}_{name}.png", "frames": len(fl), "poses": rows[name]["poses"], "feet": feet}
    print("Blatt:", name, sheet.size)
(out / f"{a.prefix}.json").write_text(json.dumps(meta, indent=1))
print("Rahmen", fw, "x", fh, "Fußpunkt", anchor, "px/m", round(ppm, 2))
