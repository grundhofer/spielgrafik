#!/usr/bin/env python3
"""Blue-Noise-Schwellenmatrix (64×64, kachelbar) mit dem Void-and-Cluster-Verfahren erzeugen.

    .venv/bin/python styles/einbit-3d/scripts/make_bluenoise.py [--size 64] [--sigma 1.5] [--seed 7]

Schreibt demo/textures/bluenoise64.png (8 Bit Grau, Rang 0..N-1 auf 0..255 abgebildet) und eine Kopie nach
assets/bluenoise64.png. Der Post-Shader liest die Textur mit texelFetch (keine Filterung) als
Schwellwert für Himmel, Rauch und Lichtkegel; Oberflächen nutzen die 8×8-Bayer-Matrix.

Verfahren (Ulichney 1993): Energie = toroidal gefalteter Gauß um jeden gesetzten Punkt. Phase 0 verteilt
ein Startmuster (10 % Punkte) gleichmäßig, Phase 1 vergibt dessen Ränge absteigend (dichtester Haufen
zuerst entfernen), Phase 2 füllt bis zur Hälfte die größte Lücke auf, Phase 3 füllt den Rest, indem die
Rollen von Punkten und Lücken getauscht werden. Deterministisch über --seed.
"""
import argparse, pathlib

import numpy as np
from PIL import Image

HERE = pathlib.Path(__file__).resolve().parent.parent

ap = argparse.ArgumentParser()
ap.add_argument("--size", type=int, default=64)
ap.add_argument("--sigma", type=float, default=1.5)
ap.add_argument("--seed", type=int, default=7)
a = ap.parse_args()

N = a.size
rng = np.random.default_rng(a.seed)

# Toroidaler Gauß-Kern, Mitte bei (0, 0); np.roll verschiebt ihn an jeden Punkt.
d = np.minimum(np.arange(N), N - np.arange(N))
kern = np.exp(-(d[:, None] ** 2 + d[None, :] ** 2) / (2 * a.sigma ** 2))


def add(energy, y, x, sign):
    energy += sign * np.roll(np.roll(kern, y, 0), x, 1)


def energy_of(pattern):
    e = np.zeros((N, N))
    for y, x in zip(*np.nonzero(pattern)):
        add(e, y, x, 1.0)
    return e


# Phase 0: Startmuster gleichmäßig verteilen
pat = np.zeros((N, N), bool)
ones = rng.choice(N * N, N * N // 10, replace=False)
pat.flat[ones] = True
e = energy_of(pat)
for _ in range(10 * N * N):
    c = np.unravel_index(np.argmax(np.where(pat, e, -np.inf)), e.shape)   # dichtester Haufen
    pat[c] = False
    add(e, *c, -1.0)
    v = np.unravel_index(np.argmin(np.where(pat, np.inf, e)), e.shape)    # größte Lücke
    pat[v] = True
    add(e, *v, 1.0)
    if v == c:
        break
start = pat.copy()
start_e = e.copy()
n_start = int(start.sum())

rank = np.zeros((N, N), int)
# Phase 1: Ränge des Startmusters absteigend
pat, e = start.copy(), start_e.copy()
for r in range(n_start - 1, -1, -1):
    c = np.unravel_index(np.argmax(np.where(pat, e, -np.inf)), e.shape)
    pat[c] = False
    add(e, *c, -1.0)
    rank[c] = r
# Phase 2: bis zur Hälfte in die größte Lücke
pat, e = start.copy(), start_e.copy()
for r in range(n_start, N * N // 2):
    v = np.unravel_index(np.argmin(np.where(pat, np.inf, e)), e.shape)
    pat[v] = True
    add(e, *v, 1.0)
    rank[v] = r
# Phase 3: Rollen tauschen, Energie der noch leeren Plätze; dichtesten Haufen der Leeren füllen
e = energy_of(~pat)
for r in range(N * N // 2, N * N):
    c = np.unravel_index(np.argmax(np.where(~pat, e, -np.inf)), e.shape)
    pat[c] = True
    add(e, *c, -1.0)
    rank[c] = r

assert sorted(rank.flat) == list(range(N * N)), "Ränge nicht eindeutig"
img = (rank * 256 // (N * N)).astype(np.uint8)
for out in (HERE / "demo" / "textures" / f"bluenoise{N}.png", HERE / "assets" / f"bluenoise{N}.png"):
    out.parent.mkdir(parents=True, exist_ok=True)
    Image.fromarray(img, "L").save(out)
    print(out)

# Kontrolle: Spektrum ohne tiefe Frequenzen (Blue Noise) und gleich verteilte Stufen
f = np.abs(np.fft.fftshift(np.fft.fft2(img.astype(float) - img.mean())))
cy = N // 2
low = f[cy - 2:cy + 3, cy - 2:cy + 3].mean()
print(f"Startpunkte {n_start}; Stufen je Grauwert {np.bincount(img.flat).min()}–{np.bincount(img.flat).max()}; "
      f"tiefe Frequenzen {low:.1f} gegenüber Mittel {f.mean():.1f}")
