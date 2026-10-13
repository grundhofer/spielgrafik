#!/usr/bin/env python3
"""Pixel-Texturen für die 3D-Szene (HD-2D) aus dem KI-Texturblatt assets/raw/textures.png.

    .venv/bin/python styles/hd-2d/scripts/build_textures.py [--preview out.png]

Ablauf je Feld des 4×4-Blatts (gpt-image, 1254×1254 statt 1024×1024 geliefert):
  1. Feldgrenzen über die schwarzen Fugen finden (Spalten mit hellen Pixeln), 3 px Rand abschneiden.
  2. Auf N×N Texel einrasten: k-means (Oklab) auf K Farben je Feld, je Texel die häufigste Farbe im
     Zellinneren (Pseudo-Raster im Blatt ≈ 4,47 Bildpixel je Kunstpixel, also ≈ 65,5 Kunstpixel je Feld).
  3. Kachelbar machen (das Modell malt nur ungefähr nahtlos): waagrecht und dann senkrecht je OVL Texel
     Überlappung mit Schnitt minimaler Abweichung (dynamische Programmierung, Schnittweg je Zeile ±1).
     Die Kachel schrumpft dabei auf (N − OVL)², Rand rechts geht nahtlos in Rand links über.
  4. Normal Map aus der Helligkeit (Oklab L, Fugen dunkel = tief), periodisch gerechnet.
Ausgaben: demo/textures/<name>.png und <name>_n.png (Kopie der Farbtexturen in assets/textures/),
assets/textures_preview.png (3×3 gekachelt).
"""
import argparse
import json
import pathlib
import sys

import numpy as np
from PIL import Image

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from hd2dlib import kmeans, nearest, oklab, oklab_to_rgb, runs  # noqa: E402

ROOT = pathlib.Path(__file__).resolve().parents[1]
N = 64
OVL = 8
K = 18
# Reihenfolge im Blatt (Zeile für Zeile), Name der Ausgabe
NAMES = ["paving", "fieldstone", "stone_dark", "slate",
         "wood", "wood_dark", "white_boards", "red_boards",
         "grass", "rock", "sand", "wet_stone",
         "rope", "iron", "plaster", "deck"]


def reduce_mode(lbl, k, out_n, inset=0.2):
    H, W = lbl.shape
    sx, sy = W / out_n, H / out_n
    out = np.zeros((out_n, out_n), np.int64)
    for y in range(out_n):
        y0 = int(np.floor((y + inset) * sy)); y1 = max(y0 + 1, int(np.ceil((y + 1 - inset) * sy)))
        for x in range(out_n):
            x0 = int(np.floor((x + inset) * sx)); x1 = max(x0 + 1, int(np.ceil((x + 1 - inset) * sx)))
            out[y, x] = np.bincount(lbl[y0:y1, x0:x1].ravel(), minlength=k).argmax()
    return out


def seam_wrap_x(lab):
    """Waagrecht kachelbar machen. lab: H×W×3 (Oklab). Ergebnis H×(W−OVL)×3 und Schnittspalten."""
    H, W, _ = lab.shape
    A = lab[:, :OVL]            # linker Rand
    Bs = lab[:, W - OVL:]       # rechter Rand (setzt sich nahtlos in die Spalte W−OVL−1 fort)
    E = np.sqrt(((A - Bs) ** 2).sum(-1))  # H×OVL
    # Schnitt bei Spalte c (1..OVL−1): links davon Bs, ab c A; Kosten = Abweichung an der Schnittspalte
    cost = np.full((H, OVL), np.inf)
    back = np.zeros((H, OVL), np.int64)
    cost[0, 1:] = E[0, 1:]
    for y in range(1, H):
        for c in range(1, OVL):
            best, bc = np.inf, c
            for dc in (-1, 0, 1):
                pc = c + dc
                if 1 <= pc < OVL and cost[y - 1, pc] < best:
                    best, bc = cost[y - 1, pc], pc
            cost[y, c] = best + E[y, c] + 0.5 * E[y, c - 1]
            back[y, c] = bc
    # periodisch auch senkrecht: Schnitt oben und unten sollen zusammenpassen -> einfacher Endpunkt
    c = int(np.argmin(cost[-1]))
    cuts = [0] * H
    for y in range(H - 1, -1, -1):
        cuts[y] = c
        c = back[y, c]
    out = lab[:, :W - OVL].copy()
    for y in range(H):
        out[y, :cuts[y]] = Bs[y, :cuts[y]]
    return out, cuts


def normal_map(L, strength):
    """Höhe aus Helligkeit (periodisch geglättet), Normalen per zentraler Differenz mit Umbruch."""
    h = L.copy()
    h = (h + np.roll(h, 1, 0) + np.roll(h, -1, 0) + np.roll(h, 1, 1) + np.roll(h, -1, 1)) / 5.0 * 0.5 + L * 0.5
    gx = (np.roll(h, -1, 1) - np.roll(h, 1, 1)) * 0.5
    gy = (np.roll(h, -1, 0) - np.roll(h, 1, 0)) * 0.5
    nx, ny, nz = -gx * strength, gy * strength, np.ones_like(h)   # Bild-y nach unten -> Normal-y nach oben
    ln = np.sqrt(nx ** 2 + ny ** 2 + nz ** 2)
    n = np.dstack([nx / ln, ny / ln, nz / ln])
    return np.clip(np.round((n * 0.5 + 0.5) * 255), 0, 255).astype(np.uint8)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--preview", default=str(ROOT / "assets" / "textures_preview.png"))
    ap.add_argument("--normal-strength", type=float, default=9.0)
    a = ap.parse_args()
    sheet = np.asarray(Image.open(ROOT / "assets" / "raw" / "textures.png").convert("RGB")).astype(np.int64)
    bright = sheet.max(2) > 40
    cols = [c for c in runs(bright.mean(0) > 0.5, 1) if c[1] - c[0] > 200]
    assert len(cols) == 4, cols
    cells = [(x0, x1, y0, y1) for (y0, y1) in cols for (x0, x1) in cols]   # Blatt ist quadratisch
    out_dir = ROOT / "demo" / "textures"
    out_dir.mkdir(parents=True, exist_ok=True)
    tiles, meta = [], {}
    for name, (x0, x1, y0, y1) in zip(NAMES, cells):
        c = sheet[y0 + 3:y1 - 3, x0 + 3:x1 - 3]
        lab = oklab(c.reshape(-1, 3))
        rng = np.random.default_rng(3)
        cent = kmeans(lab[rng.choice(len(lab), min(40000, len(lab)), replace=False)], K, iters=20, seed=3)
        lbl = nearest(lab, cent).reshape(c.shape[:2])
        idx = reduce_mode(lbl, K, N)
        t = cent[idx]                                   # N×N×3 Oklab
        t, cx = seam_wrap_x(t)
        tt, cy = seam_wrap_x(t.transpose(1, 0, 2))
        t = tt.transpose(1, 0, 2)
        rgb = np.clip(np.round(oklab_to_rgb(t.reshape(-1, 3))), 0, 255).astype(np.uint8).reshape(t.shape)
        Image.fromarray(rgb, "RGB").save(out_dir / f"{name}.png")
        (ROOT / "assets" / "textures").mkdir(exist_ok=True)
        Image.fromarray(rgb, "RGB").save(ROOT / "assets" / "textures" / f"{name}.png")
        nm = normal_map(t[..., 0], a.normal_strength)
        Image.fromarray(nm, "RGB").save(out_dir / f"{name}_n.png")
        tiles.append((name, rgb))
        meta[name] = {"cell": [int(x0), int(x1), int(y0), int(y1)], "size": list(rgb.shape[:2]),
                      "colors": int(len(np.unique(rgb.reshape(-1, 3), axis=0)))}
    (ROOT / "assets" / "textures.json").write_text(json.dumps(meta, indent=1))
    # Vorschau: jede Kachel 3×3 wiederholt, ×2 vergrößert (Nähte sichtbar machen)
    T = N - OVL
    pv = np.zeros((4 * (3 * T + 6), 4 * (3 * T + 6), 3), np.uint8)
    for i, (name, rgb) in enumerate(tiles):
        r, q = divmod(i, 4)
        big = np.tile(rgb, (3, 3, 1))
        pv[r * (3 * T + 6):r * (3 * T + 6) + 3 * T, q * (3 * T + 6):q * (3 * T + 6) + 3 * T] = big
    Image.fromarray(pv).resize((pv.shape[1] * 2, pv.shape[0] * 2), Image.NEAREST).save(a.preview)
    print(json.dumps(meta))


if __name__ == "__main__":
    main()
