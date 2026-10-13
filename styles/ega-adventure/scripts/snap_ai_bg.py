#!/usr/bin/env python3
"""KI-Hintergrund auf das Bildformat bringen: Ausschnitt 320:168, Raster 160×168 Doppelpixel, 16 EGA-Farben,
Krümel entfernen. Danach erzeugt vectorize.py die Zeichenbefehle.

    .venv/bin/python styles/ega-adventure/scripts/snap_ai_bg.py raw.png out_index.png [--top 0.1]
        [--map "rgbhex=ega,..."] [--min 3]
Schritte:
  1. Ausschnitt: volle Breite, Höhe = Breite·168/320, ab --top (Anteil der Bildhöhe).
  2. Jedes Quellpixel der nächstgelegenen EGA-Farbe zuordnen (Oklab); optional Zuordnung über --map
     erzwingen (z. B. Orange -> 12 statt 6).
  3. Je Zielzelle (ca. 9,6×4,8 Quellpixel bei 1536 Breite) gewinnt die häufigste EGA-Farbe.
  4. Farbflächen kleiner als --min Pixel gehen in der häufigsten Nachbarfarbe auf (Sterne: einzelne helle
     Pixel auf Schwarz/Blau bleiben).
"""
import argparse, pathlib, sys

import numpy as np
from PIL import Image

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(ROOT / "tools"))
from agipic import EGA_RGB, W, H, to_rgb  # noqa: E402
from sprites import oklab  # noqa: E402


def nearest_ega(rgb, overrides):
    lab = oklab(rgb.astype(np.float32))
    plab = oklab(EGA_RGB.astype(np.float32))
    d = ((lab[..., None, :] - plab[None, None]) ** 2).sum(-1)
    idx = d.argmin(-1).astype(np.uint8)
    for src, dst in overrides:
        sl = oklab(np.array([[src]], np.float32))[0, 0]
        dd = ((lab - sl) ** 2).sum(-1)
        idx[dd < 0.004] = dst
    return idx


def majority(idx, sw, sh):
    out = np.zeros((H, W), np.uint8)
    for cy in range(H):
        y0, y1 = int(cy * sh / H), max(int(cy * sh / H) + 1, int((cy + 1) * sh / H))
        for cx in range(W):
            x0, x1 = int(cx * sw / W), max(int(cx * sw / W) + 1, int((cx + 1) * sw / W))
            cnt = np.bincount(idx[y0:y1, x0:x1].ravel(), minlength=16)
            out[cy, cx] = cnt.argmax()
    return out


def clean(img, min_px):
    img = img.copy()
    for _ in range(6):
        changed = 0
        seen = np.zeros(img.shape, bool)
        for y in range(H):
            for x in range(W):
                if seen[y, x]:
                    continue
                c = img[y, x]
                comp, stack = [(x, y)], [(x, y)]
                seen[y, x] = True
                while stack:
                    cx, cy = stack.pop()
                    for nx, ny in ((cx - 1, cy), (cx + 1, cy), (cx, cy - 1), (cx, cy + 1)):
                        if 0 <= nx < W and 0 <= ny < H and not seen[ny, nx] and img[ny, nx] == c:
                            seen[ny, nx] = True
                            stack.append((nx, ny))
                            comp.append((nx, ny))
                if len(comp) >= min_px:
                    continue
                nb = []
                for cx, cy in comp:
                    for nx, ny in ((cx - 1, cy), (cx + 1, cy), (cx, cy - 1), (cx, cy + 1)):
                        if 0 <= nx < W and 0 <= ny < H and img[ny, nx] != c:
                            nb.append(int(img[ny, nx]))
                if not nb:
                    continue
                major = np.bincount(nb, minlength=16).argmax()
                if len(comp) == 1 and c in (7, 15) and major in (0, 1):
                    continue  # Stern
                for cx, cy in comp:
                    img[cy, cx] = major
                changed += 1
        if not changed:
            break
    return img


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("raw")
    ap.add_argument("out")
    ap.add_argument("--top", type=float, default=None, help="Ausschnitt ab diesem Anteil der Höhe (Standard: mittig)")
    ap.add_argument("--map", default="", help="z. B. 'e07030=12,203060=1'")
    ap.add_argument("--min", type=int, default=3)
    a = ap.parse_args()
    im = Image.open(a.raw).convert("RGB")
    sw = im.width
    sh = round(sw * H / (2 * W))
    top = (im.height - sh) / 2 if a.top is None else a.top * im.height
    top = int(max(0, min(im.height - sh, top)))
    rgb = np.asarray(im.crop((0, top, sw, top + sh)))
    overrides = []
    for item in filter(None, a.map.split(",")):
        h, e = item.split("=")
        overrides.append(([int(h[i:i + 2], 16) for i in (0, 2, 4)], int(e)))
    idx = nearest_ega(rgb, overrides)
    snapped = majority(idx, sw, sh)
    cleaned = clean(snapped, a.min)
    to_rgb(cleaned).save(a.out)
    print(f"Ausschnitt {sw}×{sh} ab y={top}, Zelle {sw / W:.1f}×{sh / H:.1f}; "
          f"Farben {len(np.unique(cleaned))}, durch Aufräumen geändert {int((cleaned != snapped).sum())} Pixel")


if __name__ == "__main__":
    main()
