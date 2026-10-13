#!/usr/bin/env python3
"""Bereitet die drei KI-Panels für die Demo auf (Ausschnitt und Maßstab je Panel) und schreibt scene.json.

    .venv/bin/python styles/comic-panels/scripts/build_panels.py

Panels (Seite 1280×720, Rand 16 px, Steg 14 px):
  A  Totale        822×582 bei (16, 16)   aus raw/bg.png      (1536×1024 → 873×582, x ab 26)
  B  Laterne       412×266 bei (852, 16)  aus raw/lantern.png (1536×1024 → 412×275, y ab 4)
  C  Nahaufnahme   412×302 bei (852, 296) aus raw/bust.png    (1536×1024 → 1,05 × 453×302 = 476×317 für die
                                                               Kamerafahrt; Sprite wird von 1/1,05 auf 1 skaliert)
  Dachs in C: Kostümfarben auf dieselben reinen Druckfarben wie die kleine Figur (BUST_PALETTE).
  Mundbild: raw/bust_talk.png wird nur im Mundbereich übernommen (Maske aus der Differenz zu bust.png > 30,
  um 6 px erweitert, 2 px weich), damit sich beim Sprechen sonst kein Pixel ändert.
Jedes Panel wird vor dem Verkleinern in Tusche und Farbflächen getrennt (inkcolor.py) und als zwei Dateien
abgelegt: panel_x.png (Farbe, wird gerastert) und panel_x_ink.png (schwarz, Alpha = Tuschedeckung).
Alle Verkleinerungen mit Lanczos (gpt-image liefert deckende RGB-Bilder ohne Alpha).
Koordinaten in scene.json sind Panel-Koordinaten (Pixel ab der linken oberen Panelecke), von Hand in den
Quellbildern abgelesen und hier umgerechnet.
"""
import json, pathlib

import numpy as np
from PIL import Image, ImageFilter

from inkcolor import separate, downscale_rgb, downscale_cov, save_rgb, save_ink

ROOT = pathlib.Path(__file__).resolve().parents[1]
RAW = ROOT / "assets/raw"
OUT = ROOT / "assets"
ZOOM_C = 1.05

PANELS = {
    "A": {"pos": [16, 16], "size": [822, 582]},
    "B": {"pos": [852, 16], "size": [412, 266]},
    "C": {"pos": [852, 296], "size": [412, 302]},
}


def load(name):
    return Image.open(RAW / name).convert("RGB")


def arr(im):
    return np.asarray(im).astype(np.float64) / 255.0


# Kolorierung des Dachses in der Nahaufnahme wie bei der kleinen Figur (build_badger.py → PALETTE): Pixel rechts von
# x = 480 (Quelle), deren nächster Anker eine Kostümfarbe ist, werden zur reinen Druckfarben-Mischung; Anker mit
# None (Himmel, Meer) bleiben, wie sie sind. Anker = k-means-Mittel der Farbflächen von raw/bust.png (gerundet).
BUST_PALETTE = [
    ((53, 53, 81), (0.0, 0.2, 0.6)),        # Fell: Blauschwarz
    ((247, 218, 168), (1.0, 1.0, 1.0)),     # Gesicht, Hemd: Papier
    ((70, 70, 42), (0.38, 0.68, 0.0)),      # Mütze, Weste
    ((206, 34, 24), (1.0, 0.0, 0.0)),       # Schal
    ((171, 28, 21), (1.0, 0.0, 0.0)),
    ((112, 77, 41), (0.72, 0.32, 0.0)),     # Tasche, Riemen
    ((208, 165, 110), (1.0, 0.72, 0.3)),    # Paket
    ((31, 70, 152), None), ((223, 128, 48), None), ((96, 64, 138), None), ((225, 79, 68), None),
    ((166, 72, 100), None), ((128, 18, 15), None), ((80, 23, 14), None),
]


def recolor_bust(col, x_min=480):
    ref = np.array([c for c, _ in BUST_PALETTE], float) / 255.0
    sub = col[:, x_min:]
    idx = ((sub[:, :, None, :] - ref[None, None]) ** 2).sum(axis=3).argmin(axis=2)
    out = sub.copy()
    for i, (_, tgt) in enumerate(BUST_PALETTE):
        if tgt is not None:
            out[idx == i] = tgt
    col = col.copy()
    col[:, x_min:] = out
    return col


def save_pair(rgb, name, size, crop, recolor=None):
    """Trennt, verkleinert auf size und schneidet crop (x0, y0, x1, y1) aus; schreibt <name>.png und <name>_ink.png."""
    col, ink = separate(rgb)
    if recolor:
        col = recolor(col)
    c = downscale_rgb(col, size)[crop[1]:crop[3], crop[0]:crop[2]]
    k = downscale_cov(ink, size)[crop[1]:crop[3], crop[0]:crop[2]]
    save_rgb(c, OUT / f"{name}.png")
    save_ink(k, OUT / f"{name}_ink.png")
    return c, k


def main():
    scene = {"page": [1280, 720], "panels": PANELS}

    # Panel A: Totale
    bg = load("bg.png")
    sa = 582 / 1024
    a = bg.resize((round(1536 * sa), 582), Image.LANCZOS)
    ax = 26
    save_pair(arr(bg), "panel_a", (round(1536 * sa), 582), (ax, 0, ax + 822, 582))

    def pa(x, y):
        return [round(x * sa - ax, 1), round(y * sa, 1)]

    # Lagen in raw/bg.png (Quellpixel, von Hand abgelesen)
    scene["A"] = {
        "scale": sa, "crop_x": ax,
        "lamp": pa(1279, 149),               # Laternenraum des Leuchtturms
        "chimney": pa(136, 157),             # Oberkante Schornstein, Mitte
        "lantern": pa(609, 400),             # Laternenglas
        "window": pa(203, 490),              # erleuchtetes Fenster des Häuschens
        "horizon_y": round(420 * sa, 1),
        "quay_edge_y": round(770 * sa, 1),   # Vorderkante Kai (Beginn des Laufwegs)
    }

    # Wasser für Glitzerstriche: blaue, nicht dunkle Pixel zwischen Horizont und Kai, ohne Boote und Pfähle
    wa = np.asarray(a.crop((ax, 0, ax + 822, 582))).astype(int)
    r, g, b = wa[..., 0], wa[..., 1], wa[..., 2]
    water = (b > r + 40) & (b > 110) & (g > 60)
    ys = np.arange(582)[:, None]
    water &= (ys > 420 * sa + 6) & (ys < 750 * sa)
    # nur Pixel, deren 9×5-Umgebung ganz Wasser ist (Abstand zu Booten, Pfählen, Felsen)
    wm = Image.fromarray((water * 255).astype(np.uint8)).filter(ImageFilter.MinFilter(9))
    wm = np.asarray(wm) > 0
    rng = np.random.default_rng(20261012)
    cand = np.argwhere(wm)
    pick = cand[rng.choice(len(cand), size=min(60, len(cand)), replace=False)]
    scene["A"]["glints"] = [[int(x), int(y)] for y, x in pick]
    scene["A"]["water_px"] = int(water.sum())

    # Panel B: Laterne
    lan = load("lantern.png")
    sb = 412 / 1536
    by = 4
    save_pair(arr(lan), "panel_b", (412, round(1024 * sb)), (0, by, 412, by + 266))

    def pb(x, y):
        return [round(x * sb, 1), round(y * sb - by, 1)]

    scene["B"] = {
        "scale": sb, "crop_y": by,
        "flame": pb(1222, 560),              # Flamme
        "glass": pb(1243, 540),              # Mitte des Glases
        "glass_r": round(170 * sb, 1),
        "window": pb(230, 770),
    }

    # Panel C: Nahaufnahme (Grundbild und Mundbild)
    bust = load("bust.png")
    talk = load("bust_talk.png")
    ba = np.asarray(bust).astype(int)
    ta = np.asarray(talk).astype(int)
    d = np.abs(ba - ta).max(axis=2)
    m = np.zeros(d.shape, np.uint8)
    y0, y1, x0, x1 = 330, 470, 760, 1040          # Mundbereich (Quellpixel)
    m[y0:y1, x0:x1] = (d[y0:y1, x0:x1] > 30) * 255
    mi = Image.fromarray(m).filter(ImageFilter.MaxFilter(13)).filter(ImageFilter.GaussianBlur(2))
    mk = np.asarray(mi).astype(float)[..., None] / 255.0
    comp = (ba * (1 - mk) + ta * mk).round().clip(0, 255).astype(np.uint8)
    sc = 302 / 1024 * ZOOM_C
    size = (round(1536 * sc), round(1024 * sc))
    save_pair(arr(bust), "panel_c", size, (0, 0) + size, recolor_bust)
    save_pair(comp.astype(np.float64) / 255.0, "panel_c_talk", size, (0, 0) + size, recolor_bust)
    mask_share = float((mk > 0.5).mean())

    # Ausschnitt bei Zoom 1: 453×302, x ab 30 (links ein Stück Felsen, rechts die Tasche)
    s1 = 302 / 1024
    cx = 30

    def pc(x, y):
        return [round(x * s1 - cx, 1), round(y * s1, 1)]

    scene["C"] = {
        "tex_scale": sc, "zoom": ZOOM_C, "crop_x_at_zoom1": cx,
        "mouth": pc(905, 405),
        "eye": pc(955, 245),
        "nose": pc(815, 345),
        "lamp": pc(220, 318),                 # Leuchtturm im Hintergrund
        "zoom_center": pc(930, 330),          # Kamerafahrt auf das Gesicht
        "mouth_mask_share": round(mask_share, 4),
    }
    (OUT / "scene.json").write_text(json.dumps(scene, indent=1))
    print("ok", json.dumps({k: scene[k] for k in ("A", "B", "C")})[:600])


if __name__ == "__main__":
    main()
