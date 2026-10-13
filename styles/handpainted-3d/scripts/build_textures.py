#!/usr/bin/env python3
"""Zerlegt das KI-Texturblatt (3×3) in neun kachelbare Texturen und legt den gemalten Himmel ab.

    .venv/bin/python styles/handpainted-3d/scripts/build_textures.py

Eingaben:  assets/raw/textures.png (genimg, 3×3 Felder mit schwarzen Fugen), assets/raw/sky.png
Ausgaben:  demo/textures/<name>.png (512×512, nahtlos), demo/textures/sky.png, demo/textures/brush.png (Code),
           assets/textures/*.png (Kopien), assets/preview/textures_tiled.png (jede Textur 2×2 gekachelt)

Kachelbar machen: je Achse ov Pixel Überlappung; im Überlappungsband wird je Zeile (bzw. Spalte) an der
Linie geringster Abweichung (dynamische Programmierung) geschnitten und 3 px weich überblendet. Links der
Linie stammen die Pixel vom Ende des Feldes (setzt die Nachbarkachel fort), rechts vom Anfang. Die Linie
ist an beiden Enden auf die Bandmitte gezwungen, damit die zweite Achse die erste nicht wieder aufbricht.
Farben bleiben wie gemalt (der Stil steckt in ihnen); getönt wird im Shader.
"""
import pathlib
import shutil

import numpy as np
from PIL import Image

SD = pathlib.Path(__file__).resolve().parent.parent
RAW = SD / "assets" / "raw"
OUT = SD / "demo" / "textures"
COPY = SD / "assets" / "textures"
PREV = SD / "assets" / "preview"
NAMES = ["paving", "wall", "roof", "planks", "planks_dark", "rock", "grass", "sand", "plaster"]
TRIM = 5          # Rand je Feld, der an die Fuge grenzt (Farbsaum)
OV = 44           # Überlappung in Pixeln
SIZE = 512        # Zielgröße


def find_cells(a):
    """Zellgrenzen aus den dunklen Fugen (Mittelwert je Spalte/Zeile < 25)."""
    def runs(prof):
        light = prof >= 25
        out, start = [], None
        for i, v in enumerate(light):
            if v and start is None:
                start = i
            if not v and start is not None:
                out.append((start, i))
                start = None
        if start is not None:
            out.append((start, len(prof)))
        return [r for r in out if r[1] - r[0] > 100]
    g = a.mean(2)
    cols, rows = runs(g.mean(0)), runs(g.mean(1))
    assert len(cols) == 3 and len(rows) == 3, (cols, rows)
    return rows, cols


def min_cut(err, ends):
    """err: (n, ov) Fehler je Zeile und Spalte im Band. Liefert je Zeile die Schnittspalte (1..ov-1)."""
    n, ov = err.shape
    cost = err.copy()
    big = 1e9
    mid = ov // 2
    pen = np.full((n, ov), 0.0)
    pen[:, :2] = big
    pen[:, ov - 2:] = big
    for r in list(range(ends)) + list(range(n - ends, n)):
        pen[r, :] = big
        pen[r, mid] = 0.0
    cost += pen
    acc = cost.copy()
    back = np.zeros((n, ov), dtype=int)
    for r in range(1, n):
        prev = acc[r - 1]
        cand = np.stack([np.r_[big, prev[:-1]], prev, np.r_[prev[1:], big]])
        k = cand.argmin(0)
        acc[r] += cand[k, np.arange(ov)]
        back[r] = np.arange(ov) + k - 1
    path = np.zeros(n, dtype=int)
    path[-1] = int(acc[-1].argmin())
    for r in range(n - 1, 0, -1):
        path[r - 1] = back[r, path[r]]
    return path


def seamless_x(t, ov):
    h, w, _ = t.shape
    wn = w - ov
    A = t[:, wn:w]          # setzt die linke Nachbarkachel fort
    B = t[:, 0:ov]          # setzt den Rest der eigenen Kachel fort
    err = ((A - B) ** 2).sum(2)
    path = min_cut(err, ends=6)
    j = np.arange(ov)[None, :]
    # weicher Übergang über 3 px um die Schnittlinie: 1 = A, 0 = B
    m = np.clip((path[:, None] - j) / 3.0 + 0.5, 0.0, 1.0)[..., None]
    out = t[:, :wn].copy()
    out[:, :ov] = A * m + B * (1 - m)
    return out


def seamless(t, ov):
    t = seamless_x(t, ov)
    t = seamless_x(t.transpose(1, 0, 2), ov).transpose(1, 0, 2)
    return t


def make_brush(n=256, seed=20261012):
    """Pinseltupfer für die Figur: periodisches Rauschen (Frequenzband 3–14 Perioden je Kachel), weich auf
    5 Stufen gezogen und periodisch geglättet; Mittel 0,5. Graustufen, nahtlos."""
    rng = np.random.default_rng(seed)
    f = np.fft.fft2(rng.normal(size=(n, n)))
    ky, kx = np.meshgrid(np.fft.fftfreq(n) * n, np.fft.fftfreq(n) * n, indexing="ij")
    k = np.hypot(kx * 0.7, ky * 1.3)          # leicht gestreckte Tupfer
    band = np.exp(-((k - 5.0) / 3.0) ** 2)
    v = np.real(np.fft.ifft2(f * band))
    v = (v - v.mean()) / (v.std() * 4.5) + 0.5
    q = np.round(np.clip(v, 0, 1) * 4) / 4      # 5 Stufen wie Farbtupfer
    # periodisch glätten (FFT-Gauss), damit die Stufen weich auslaufen
    g = np.exp(-(kx ** 2 + ky ** 2) / (2 * 40.0 ** 2))
    q = np.real(np.fft.ifft2(np.fft.fft2(q) * g))
    q = np.clip(q - q.mean() + 0.5, 0, 1)
    return Image.fromarray((q * 255 + 0.5).astype(np.uint8), "L")


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    COPY.mkdir(parents=True, exist_ok=True)
    PREV.mkdir(parents=True, exist_ok=True)
    a = np.asarray(Image.open(RAW / "textures.png").convert("RGB")).astype(np.float64)
    rows, cols = find_cells(a)
    tiles = []
    k = 0
    for r0, r1 in rows:
        for c0, c1 in cols:
            cell = a[r0 + TRIM:r1 - TRIM, c0 + TRIM:c1 - TRIM]
            s = min(cell.shape[:2])
            cell = cell[:s, :s]
            t = seamless(cell, OV)
            im = Image.fromarray(np.clip(t + 0.5, 0, 255).astype(np.uint8)).resize((SIZE, SIZE), Image.LANCZOS)
            im.save(OUT / f"{NAMES[k]}.png")
            im.save(COPY / f"{NAMES[k]}.png")
            print(f"{NAMES[k]:12s} Feld {r0}:{r1} x {c0}:{c1}  ({s}px -> {t.shape[1]}px -> {SIZE})")
            tiles.append(im)
            k += 1
    # Vorschau: jede Textur 2×2 gekachelt (Nähte prüfen), 3×3 Raster
    p = 256
    sheet = Image.new("RGB", (3 * 2 * p + 4 * 8, 3 * 2 * p + 4 * 8), (20, 20, 20))
    for i, im in enumerate(tiles):
        small = im.resize((p, p), Image.LANCZOS)
        x0 = 8 + (i % 3) * (2 * p + 8)
        y0 = 8 + (i // 3) * (2 * p + 8)
        for dx in (0, p):
            for dy in (0, p):
                sheet.paste(small, (x0 + dx, y0 + dy))
    sheet.save(PREV / "textures_tiled.png")
    # Himmel: unverändert übernehmen (Unterkante = Horizont)
    sky = Image.open(RAW / "sky.png").convert("RGB")
    sky.save(OUT / "sky.png")
    sky.save(COPY / "sky.png")
    print("sky", sky.size)
    br = make_brush()
    br.save(OUT / "brush.png")
    br.save(COPY / "brush.png")
    print("brush", br.size)


if __name__ == "__main__":
    main()
