#!/usr/bin/env python3
"""Druckbild des Hintergrunds und Wassermaske für die Ukiyo-e-Demo.

    .venv/bin/python styles/ukiyo-e/scripts/build_bg.py

Eingang: assets/raw/bg2.png (gpt-image, 1536x1024)
Ausgang (assets/ und demo/art/):
  bg.png      1264x704: Zeilen 64..920 der KI-Vorlage (856 Zeilen, oberes dunkles Band und Teil der Meeresfläche
              abgeschnitten), Lanczos x0,8229. Liegt in der Demo bei (8, 8) innerhalb des 8-px-Papierrands.
              Vor dem Verkleinern werden Kaimauer, Pflaster, Hausmauer und Felsen in KI-Auflösung flach gedruckt
              (scripts/flatten_cells.py: jede von der Schlüsselkontur umschlossene Zelle mit 1 Ton, große Zellen mit
              Licht/Schatten-Teilung 2 Töne, Felsen zusätzlich eine Bokashi-Kante unten).
  bg_close.png  1264x704: die Nahaufnahme (scene.json "closeup": Druckausschnitt ab view, 1,6-fach) direkt aus der
              geglätteten KI-Vorlage gerechnet (Lanczos x1,317), damit sie nicht aus bg.png hochskaliert wird.
  water_close.png  Wassermaske der Nahaufnahme, gleiche Regel in deren Koordinaten.
  water.png   1264x704 RGB, nearest gelesen: R = Hafenwasser, das verschoben werden darf (Zielpixel, um 1 px
              geschrumpft), G = Hafenwasser, aus dem gelesen werden darf (um 3 px geschrumpft), B = 0.
              Wasser = blaue Pixel (B > R + 55, B > 80) zwischen Horizont und Kaikante, nur zusammenhängende
              Flächen ab 1500 px (Steg und Laternenpfahl teilen das Wasser; Bootskonturen, Felsen und
              einzelne blaue Pixel in Booten bleiben draußen).
  scene.json  Lage von Leuchtfeuer, Laterne, Fenster, Schornstein, Horizont und Kaikante in Druckkoordinaten
              (von Hand an 6-fach vergrößerten Ausschnitten abgelesen, siehe Kommentare)
"""
import json, pathlib, sys
import numpy as np
from PIL import Image

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import flatten_cells  # noqa: E402

ROOT = pathlib.Path(__file__).resolve().parents[1]
OUTS = [ROOT / "assets", ROOT / "demo/art"]
CROP = (0, 64, 1536, 920)
SIZE = (1264, 704)
HORIZON_Y = 256          # erste Wasserzeile unter dem Horizont (Druckkoordinaten)
QUAY_Y = 436             # Kante Wasser/Kai
SCENE = {
    "print_origin": [8, 8],
    "lamp": [955, 66, 13, 8],          # Lampenraum des Leuchtturms: Mitte und Halbachsen (Glas 943-967 x 59-74)
    "lantern": [1012, 346, 14, 14],    # Laternenglas 999-1026 x 332-360
    "window": [38, 361, 10, 15],       # Fenster des Häuschens 28-47 x 346-376
    "chimney": [131, 183],             # Mitte der Schornsteinkrone (113-148 x 183)
    "horizon_y": HORIZON_Y,
    "quay_top": [437, 507],            # Pflaster des Kais (Gehfläche), darunter Kaimauer bis 655, dann Meer
    "sea_y": 655,
    # Nahaufnahme ab Takt 90 (3,0 s): Druckausschnitt ab view (Druckkoordinaten), zoom-fach, wieder bei (8, 8)
    "closeup": {"from_tick": 90, "view": [0, 230], "zoom": 1.6},
}
# Bearbeitungsbereiche für das flache Drucken (Druckkoordinaten x0, y0, x1, y1)
FLAT_BOXES = [(0, 503, 1264, 660),      # Kaimauer mit Deckplatten
              (0, 437, 1264, 507),      # Pflaster
              (0, 280, 196, 440),       # Hausmauer
              (185, 370, 290, 440),     # Felsen am Haus
              (700, 202, 1264, 362), (1000, 185, 1264, 202), (640, 270, 1000, 340)]   # Felsnase, Klippen, Steine
ROCK_BOXES = [(185, 370, 290, 440), (700, 202, 1264, 362), (1000, 185, 1264, 202), (640, 270, 1000, 340)]
KEEP_BOXES = [(960, 285, 1035, 505),    # Laternenpfahl
              (1060, 380, 1264, 520),   # Fässer, Kisten, Tau
              (20, 325, 70, 385), (100, 320, 160, 440),   # Fenster, Tür
              (920, 20, 1000, 216), (975, 140, 1062, 214)]  # Leuchtturm, Wärterhaus


def erode(b, r):
    out = b.copy()
    for dy in range(-r, r + 1):
        for dx in range(-r, r + 1):
            if dx * dx + dy * dy <= r * r:
                out &= np.roll(np.roll(b, dy, 0), dx, 1)
    return out


def big_components(b, min_px):
    h, w = b.shape
    lab = np.zeros((h, w), np.int32)
    keep, cur = [], 0
    ys, xs = np.nonzero(b)
    for y0, x0 in zip(ys, xs):
        if lab[y0, x0]:
            continue
        cur += 1
        stack, n = [(y0, x0)], 0
        lab[y0, x0] = cur
        while stack:
            y, x = stack.pop()
            n += 1
            for yy, xx in ((y + 1, x), (y - 1, x), (y, x + 1), (y, x - 1)):
                if 0 <= yy < h and 0 <= xx < w and b[yy, xx] and not lab[yy, xx]:
                    lab[yy, xx] = cur
                    stack.append((yy, xx))
        if n >= min_px:
            keep.append(cur)
    return np.isin(lab, keep)


def water_mask(im, horizon, quay, min_px, r_dst, r_src):
    a = np.asarray(im).astype(int)
    r, g, b = a[..., 0], a[..., 1], a[..., 2]
    blue = (b > r + 55) & (b > 80)
    band = np.zeros_like(blue)
    band[horizon:quay] = True
    water = big_components(blue & band, min_px)
    m = np.zeros(a.shape, np.uint8)
    m[..., 0] = erode(water, r_dst) * 255
    m[..., 1] = erode(water, r_src) * 255
    return m, int(water.sum())


def flat_print(ki):
    """Kaimauer, Pflaster, Hausmauer und Felsen in KI-Auflösung flach drucken (siehe flatten_cells.py)."""
    H, W = ki.shape[:2]
    fx, fy = W / SIZE[0], H / SIZE[1]

    def box(x0, y0, x1, y1):
        m = np.zeros((H, W), bool)
        m[int(y0 * fy):int(y1 * fy), int(x0 * fx):int(x1 * fx)] = True
        return m

    region = np.zeros((H, W), bool)
    for bx in FLAT_BOXES:
        region |= box(*bx)
    rock = np.zeros((H, W), bool)
    for bx in ROCK_BOXES:
        rock |= box(*bx)
    for bx in KEEP_BOXES:
        region &= ~box(*bx)
    a = ki.astype(int)
    blue = a[..., 2] > a[..., 0] + 40
    warm_sky = (a[..., 0] > a[..., 2] + 70) & (a[..., 0] > 170)
    region &= ~(blue | warm_sky)

    def keep(med, is_rock):
        r, g, b = med
        return (b > g + 12 and b > r - 10) or (r > g + 45) or (r + g + b > 600)   # Himmel, Wolken, Weißes

    return flatten_cells.flatten(ki, region, rock, keep)


def main():
    src = Image.open(ROOT / "assets/raw/bg2.png").convert("RGB")
    ki = np.asarray(src.crop(CROP))
    flat, st = flat_print(ki)
    kim = Image.fromarray(flat)
    im = kim.resize(SIZE, Image.LANCZOS)
    m, n_water = water_mask(im, HORIZON_Y, QUAY_Y, 1500, 1, 3)
    # Nahaufnahme: Druckausschnitt view .. view + SIZE/zoom, direkt aus der KI-Vorlage
    cu = SCENE["closeup"]
    z, (vx, vy) = cu["zoom"], cu["view"]
    fx, fy = ki.shape[1] / SIZE[0], ki.shape[0] / SIZE[1]
    boxc = (vx * fx, vy * fy, (vx + SIZE[0] / z) * fx, (vy + SIZE[1] / z) * fy)
    imc = kim.resize(SIZE, Image.LANCZOS, box=boxc)
    hc, qc = round((HORIZON_Y - vy) * z), round((QUAY_Y - vy) * z)
    mc, n_water_c = water_mask(imc, max(0, hc), qc, int(1500 * z * z), 1, 4)
    scene = dict(SCENE, closeup=dict(cu, horizon_y=max(0, hc), quay_y=qc),
                 flat_stats={k: st[k] for k in ("cells", "one", "two", "three", "std_before", "std_after", "px")})
    for d in OUTS:
        d.mkdir(parents=True, exist_ok=True)
        im.save(d / "bg.png")
        imc.save(d / "bg_close.png")
        Image.fromarray(m, "RGB").save(d / "water.png")
        Image.fromarray(mc, "RGB").save(d / "water_close.png")
        (d / "scene.json").write_text(json.dumps(scene, indent=1))
    print("ok bg.png", im.size, "Wasser", n_water, "px; bg_close.png Wasser", n_water_c, "px")


if __name__ == "__main__":
    main()
