"""Kleine Pixel-Assets im Code: Himmel, Lichter, Rauch, Möwe, Wolken, Kachel-Cursor, Paket, Poller, Felsen, Schatten.

  .venv/bin/python styles/iso-pixel/scripts/build_fx.py

Alles auf ganzen Pixeln, Übergänge mit 4×4-Bayer-Raster statt Verlauf. Lichter (halo_*.png) sind für additive
Mischung gedacht: Stufen mit Bayer-Kanten, kein weicher Rand.
"""
import json
import pathlib
import sys

import numpy as np
from PIL import Image

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import isopal  # noqa: E402

ENTRY = HERE.parent
OUT = ENTRY / "demo/art"
BAYER4 = np.array([[0, 8, 2, 10], [12, 4, 14, 6], [3, 11, 1, 9], [15, 7, 13, 5]]) / 16.0
hx = isopal.hx


def save(name, arr):
    Image.fromarray(arr.astype(np.uint8)).save(OUT / name)


def sky():
    W, H = 426, 240
    stops = [(0, "#110f28"), (50, "#1b173b"), (95, "#2c2250"), (125, "#4a2f5f"), (148, "#7c3e66"),
             (163, "#b45a62"), (174, "#dd8455"), (181, "#eda762"), (188, "#c8685a"), (200, "#6d3a58"),
             (216, "#35264a"), (240, "#1a1632")]
    ys = np.array([s[0] for s in stops], float)
    cols = [hx(s[1]) for s in stops]
    img = np.zeros((H, W, 4), np.uint8)
    img[..., 3] = 255
    for y in range(H):
        i = int(np.clip(np.searchsorted(ys, y, side="right") - 1, 0, len(ys) - 2))
        t = (y - ys[i]) / (ys[i + 1] - ys[i])
        for x in range(W):
            c = cols[i + 1] if t > BAYER4[y % 4, x % 4] else cols[i]
            img[y, x, :3] = c
    return img


def stars(seed=7):
    rng = np.random.RandomState(seed)
    pts = []
    while len(pts) < 46:
        x, y = int(rng.randint(2, 300)), int(rng.randint(2, 118))
        pts.append([x, y, int(rng.rand() < 0.15), float(rng.rand())])
    return pts


def halo(rx, ry, levels, color):
    """Stufen-Lichthof: Ellipse rx×ry, levels = Deckkraft je Ring von innen nach außen, Ringgrenzen mit Bayer."""
    W, H = 2 * rx + 1, 2 * ry + 1
    img = np.zeros((H, W, 4), np.uint8)
    n = len(levels)
    for y in range(H):
        for x in range(W):
            d = np.hypot((x - rx) / (rx + 0.5), (y - ry) / (ry + 0.5))
            if d >= 1:
                continue
            f = d * n + (BAYER4[y % 4, x % 4] - 0.5) * 0.9
            k = int(np.clip(np.floor(f), 0, n - 1))
            a = levels[k]
            if a <= 0:
                continue
            img[y, x, :3] = color
            img[y, x, 3] = int(a * 255)
    return img


def flare(rx=26, ry=9):
    """Aufblitzen des Leuchtfeuers: Kreuz aus Pixelstrahlen (waagrecht lang, senkrecht kurz), kurze Diagonalen,
    Enden nur jedes zweite Pixel."""
    W, H = 2 * rx + 1, 2 * ry + 1
    img = np.zeros((H, W, 4), np.uint8)
    col = hx("#fff3c8")
    for y in range(H):
        for x in range(W):
            dx, dy = abs(x - rx), abs(y - ry)
            a = 0.0
            if dy == 0:
                a = 1.0 - dx / (rx + 1)
                if dx > rx * 0.55 and (x % 2):
                    a = 0.0
            elif dx == 0:
                a = 1.0 - dy / (ry + 1)
                if dy > ry * 0.55 and (y % 2):
                    a = 0.0
            elif dx == dy and dx <= 3:
                a = 0.55
            if dx <= 1 and dy <= 1:
                a = 1.0
            if a <= 0.12:
                continue
            img[y, x, :3] = col
            img[y, x, 3] = int(255 * min(1.0, 0.35 + a))
    return img


def smoke_puff(r):
    s = 2 * r + 2
    img = np.zeros((s, s, 4), np.uint8)
    hi, mid, lo = hx("#c9c0d2"), hx("#9d92b0"), hx("#6f6488")    # heller als die Szene: vor dem Nachthimmel lesbar
    for y in range(s):
        for x in range(s):
            d = np.hypot(x - r - 0.5, (y - r - 0.5) * 1.15)
            if d <= r:
                c = mid
                if (x - r) + (y - r) < -r * 0.5:
                    c = hi
                elif (x - r) + (y - r) > r * 0.6:
                    c = lo
                img[y, x, :3] = c
                img[y, x, 3] = 255
    return img


def dither_fade(img, keep):
    """Ausdünnen per Bayer: keep = Anteil der Pixel, die bleiben."""
    out = img.copy()
    H, W = img.shape[:2]
    for y in range(H):
        for x in range(W):
            if BAYER4[y % 4, x % 4] >= keep:
                out[y, x, 3] = 0
    return out


def gull(frame):
    """Möwe 11×6, Flügel oben / Mitte / unten."""
    W, H = 11, 6
    img = np.zeros((H, W, 4), np.uint8)
    body = isopal.dusk(hx("#e6e2ea"))
    shade = isopal.dusk(hx("#a49cb4"))
    tip = isopal.OUTLINE
    shapes = {
        0: ["...........", "#.........#", ".##.....##.", "...##B##...", ".....B.....", "..........."],
        1: ["...........", "...........", "###.....###", "...##B##...", ".....B.....", "..........."],
        2: ["...........", "...........", "...........", "..###B###..", ".##..B..##.", "#.........#"],
    }
    for y, row in enumerate(shapes[frame]):
        for x, ch in enumerate(row):
            if ch == "#":
                img[y, x, :3] = tip if x in (0, 10) else (shade if y >= 3 else body)
                img[y, x, 3] = 255
            elif ch == "B":
                img[y, x, :3] = body
                img[y, x, 3] = 255
    return img


def cloud(w, h, seed):
    """Flache Abendwolke aus überlappenden Ellipsen: Oberseite violett, Unterkante vom Abendrot beleuchtet."""
    rng = np.random.RandomState(seed)
    img = np.zeros((h, w, 4), np.uint8)
    top = hx("#3a2c58")
    mid = hx("#4f3a68")
    low = hx("#87455f")
    lit = hx("#d87a58")
    blobs = []
    x = 4.0
    while x < w - 4:
        prof = np.sin(np.pi * x / w) ** 0.8                 # in der Mitte hoch, zu den Enden flach
        ry = max(2.0, h * prof * rng.uniform(0.55, 1.0))
        blobs.append((x, h - 0.5, ry * rng.uniform(1.4, 1.9), ry))
        x += ry * rng.uniform(0.9, 1.4)
    mask = np.zeros((h, w), bool)
    for y in range(h):
        for xx in range(w):
            for bx, by, rx, ry in blobs:
                if ((xx + 0.5 - bx) / rx) ** 2 + ((y + 0.5 - by) / ry) ** 2 < 1 and y < h - 0:
                    mask[y, xx] = True
    for y in range(h):
        for xx in range(w):
            if not mask[y, xx]:
                continue
            below = y + 1 < h and mask[y + 1, xx]
            above = y > 0 and mask[y - 1, xx]
            c = mid
            if not above:
                c = top
            if not below:
                c = lit
            elif y + 2 < h and not mask[y + 2, xx]:
                c = low
            img[y, xx, :3] = c
            img[y, xx, 3] = 255
    return img


def cursor(expand):
    """Kachel-Cursor: Eckwinkel einer 32×16-Raute, um expand px nach außen versetzt (Pulsieren)."""
    W, H = 32 + 4 * expand + 2, 16 + 2 * expand + 2
    img = np.zeros((H, W, 4), np.uint8)
    col = hx("#f4dc8a")
    dark = isopal.OUTLINE
    cx, cy = W / 2, H / 2
    hw, hh = 16 + 2 * expand, 8 + expand
    for y in range(H):
        for x in range(W):
            sx, sy = x + 0.5 - cx, y + 0.5 - cy
            d = abs(sx) / hw + abs(sy) / hh
            on_edge = abs(d - 1.0) < 0.5 / hh
            near_corner = (abs(sx) > hw * 0.62) or (abs(sy) > hh * 0.62)
            if on_edge and near_corner:
                img[y, x, :3] = col
                img[y, x, 3] = 255
    # dunkle Kante unter der hellen Linie (lesbar auf hellem Pflaster)
    out = img.copy()
    for y in range(H - 1):
        for x in range(W):
            if img[y, x, 3] and not img[y + 1, x, 3]:
                out[y + 1, x, :3] = dark
                out[y + 1, x, 3] = 200
    return out


def iso_box(w, top_h, side_h, ramp, string=None):
    """Kleine Kiste in 2:1-Iso: Raute w×top_h, Seiten side_h; Oberseite Stufe 3, links 2, rechts 1."""
    W, H = w, top_h + side_h
    img = np.zeros((H, W, 4), np.uint8)
    cx, cy = w / 2, top_h / 2
    for y in range(H):
        for x in range(W):
            sx, sy = x + 0.5, y + 0.5
            top = abs(sx - cx) / (w / 2) + abs(sy - cy) / (top_h / 2) < 1
            yl = cy + (sx) * (top_h / w)            # untere linke Kante
            yr = cy + (w - sx) * (top_h / w)
            if top:
                c = ramp[3]
                if string and (abs((sx - cx) / (w / 2) - (sy - cy) / (top_h / 2)) < 0.22 or
                               abs((sx - cx) / (w / 2) + (sy - cy) / (top_h / 2)) < 0.22):
                    c = string
            elif sx <= cx and yl <= sy < yl + side_h:
                c = ramp[2]
                if string and abs(sx - cx / 1.0 * 0.5) < 0.6:
                    c = string
            elif sx > cx and yr <= sy < yr + side_h:
                c = ramp[1]
                if string and abs(sx - (cx + w / 4)) < 0.6:
                    c = string
            else:
                continue
            img[y, x, :3] = c
            img[y, x, 3] = 255
    out = np.zeros((H + 2, W + 2, 4), np.uint8)
    out[1:-1, 1:-1] = img
    a = out[..., 3] > 0
    p = np.pad(a, 1)
    ring = (p[:-2, 1:-1] | p[2:, 1:-1] | p[1:-1, :-2] | p[1:-1, 2:]) & ~a
    out[ring, :3] = isopal.OUTLINE
    out[ring, 3] = 255
    return out


def bollard():
    m = isopal.RAMPS["Metal"]
    rows = [".oo.", "o32o", "o21o", ".11.", ".10.", "o10o", "o00o", ".oo."]
    img = np.zeros((len(rows), 4, 4), np.uint8)
    for y, r in enumerate(rows):
        for x, ch in enumerate(r):
            if ch == ".":
                continue
            img[y, x, :3] = isopal.OUTLINE if ch == "o" else m[int(ch)]
            img[y, x, 3] = 255
    return img


def water_rock(w, h, seed):
    rng = np.random.RandomState(seed)
    r = isopal.RAMPS["Rock"]
    foam = isopal.dusk(hx("#a9cdd2"))
    img = np.zeros((h + 2, w + 2, 4), np.uint8)
    cx = (w + 2) / 2
    for y in range(h + 2):
        for x in range(w + 2):
            dx = (x + 0.5 - cx) / (w / 2)
            top = h * (1 - dx * dx) ** 0.6 if abs(dx) < 1 else 0
            yy = (h + 1) - (y + 0.5)
            if yy < top + rng.uniform(-0.3, 0.3) and yy > 0:
                c = r[2] if dx < -0.1 else r[1]
                if yy > top - 1.2 and dx < 0.3:
                    c = r[3]
                img[y, x, :3] = c
                img[y, x, 3] = 255
    for x in range(w + 2):
        if img[h, x, 3] or img[h - 1, x, 3]:
            img[h + 1, x, :3] = foam
            img[h + 1, x, 3] = 255
    return img


def shadow(w, h):
    img = np.zeros((h, w, 4), np.uint8)
    for y in range(h):
        for x in range(w):
            if ((x + 0.5 - w / 2) / (w / 2)) ** 2 + ((y + 0.5 - h / 2) / (h / 2)) ** 2 < 1:
                img[y, x, :3] = isopal.OUTLINE
                img[y, x, 3] = 110
    return img


def tuft(seed):
    g = isopal.RAMPS["Grass"]
    pats = [["..3..", ".2.3.", "2.2.1"], ["3...", ".3.2", "2.2."], [".3.", "323", "2.2"]]
    p = pats[seed % 3]
    img = np.zeros((len(p), len(p[0]), 4), np.uint8)
    for y, r in enumerate(p):
        for x, ch in enumerate(r):
            if ch != ".":
                img[y, x, :3] = g[int(ch)]
                img[y, x, 3] = 255
    return img


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "fx").mkdir(exist_ok=True)
    save("sky.png", sky())
    warm = hx("#ffb860")
    save("fx/halo_lamp.png", halo(9, 9, [0.55, 0.32, 0.16], warm))
    save("fx/halo_lamp_small.png", halo(7, 7, [0.5, 0.28, 0.12], warm))
    save("fx/pool_lamp.png", halo(26, 13, [0.30, 0.20, 0.11], hx("#ffa850")))
    save("fx/pool_window.png", halo(18, 9, [0.24, 0.14, 0.07], hx("#ffa850")))
    save("fx/halo_window.png", halo(6, 6, [0.40, 0.18], warm))
    save("fx/halo_beacon.png", halo(10, 10, [0.75, 0.42, 0.18], hx("#fff0b8")))
    save("fx/flare.png", flare())
    for i, r in enumerate((2, 3, 4, 5)):
        p = smoke_puff(r)
        save(f"fx/smoke_{i}.png", p)
        save(f"fx/smoke_{i}_f.png", dither_fade(p, 0.5))
    for f in range(3):
        save(f"fx/gull_{f}.png", gull(f))
    save("fx/cloud_0.png", cloud(58, 13, 1))
    save("fx/cloud_1.png", cloud(44, 11, 2))
    save("fx/cloud_2.png", cloud(76, 14, 3))
    save("fx/cursor_0.png", cursor(0))
    save("fx/cursor_1.png", cursor(1))
    save("parcel.png", iso_box(10, 5, 4, isopal.RAMPS["Parcel"], string=isopal.RAMPS["Rope"][3]))
    save("bollard.png", bollard())
    save("rock_0.png", water_rock(9, 5, 3))
    save("rock_1.png", water_rock(6, 3, 4))
    save("fx/shadow_badger.png", shadow(18, 7))
    save("fx/shadow_small.png", shadow(14, 6))
    save("fx/shadow_crates.png", shadow(26, 11))
    for i in range(3):
        save(f"tuft_{i}.png", tuft(i))
    json.dump({"stars": stars()}, open(OUT / "fx/stars.json", "w"))
    print("fx ok")


if __name__ == "__main__":
    main()
