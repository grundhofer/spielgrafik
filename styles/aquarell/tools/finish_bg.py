#!/usr/bin/env python3
"""Legt um einen fertig gemalten Hintergrund (1280x720) den Aquarellrand: Die Farbe endet zum Papier hin in
unregelmäßigen, ausgefransten Kanten mit dunklerem Trockenrand; unten läuft sie in Trockenpinsel-Strichen aus, darunter
bleibt Papier für den Text.

    .venv/bin/python styles/aquarell/tools/finish_bg.py IN.png OUT.png [--bottom 600] [--top 22] [--side 18]
        [--seed 7] [--preview p.png]

Ausgabe RGBA: Alpha = Farbauftrag (0 = Papier). Godot legt das Bild auf die Papierfläche.
"""
import argparse
import numpy as np
from PIL import Image

import wc


def edge_line(n, base, amp, cell, seed, octaves=4):
    """1D-Randverlauf: base ± amp, mit fBm-Rauschen."""
    v = wc.value_noise(1, n, cell, seed, octaves)[0]
    return base + (v - 0.5) * 2 * amp


def vignette(w=1280, h=720, top=22, side=18, bottom=600, seed=7):
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float64)
    t = edge_line(w, top, 12, 90, seed)[None, :] + edge_line(w, 0, 4, 12, seed + 9)[None, :]
    b = edge_line(w, bottom, 16, 150, seed + 1)[None, :] + edge_line(w, 0, 6, 25, seed + 2)[None, :]
    l = edge_line(h, side, 10, 70, seed + 3)[:, None] + edge_line(h, 0, 3, 10, seed + 10)[:, None]
    r = w - edge_line(h, side, 10, 70, seed + 4)[:, None] - edge_line(h, 0, 3, 10, seed + 11)[:, None]
    # Kantenschärfe wechselt: hier trocken und hart, dort nass ausgelaufen
    st = 1.2 + 9.0 * wc.smoothstep(0.55, 0.9, wc.value_noise(1, w, 120, seed + 6, 3)[0])[None, :]
    sl = 1.2 + 7.0 * wc.smoothstep(0.55, 0.9, wc.value_noise(1, h, 90, seed + 7, 3)[0])[:, None]
    sr = 1.2 + 7.0 * wc.smoothstep(0.55, 0.9, wc.value_noise(1, h, 90, seed + 8, 3)[0])[:, None]
    m = (wc.smoothstep(t - st, t + st, yy) * wc.smoothstep(l - sl, l + sl, xx)
         * wc.smoothstep(r + sr, r - sr, xx))
    # unten: Trockenpinsel – die Farbe reißt in waagerechten Strichen auf
    dry = wc.value_noise(h, w, 9, seed + 5, 3, aniso=(9.0, 0.35))
    depth = (yy - (b - 34)) / 34.0                    # 0 am Beginn der Auslaufzone, 1 an der Kante
    keep = dry > wc.smoothstep(0.0, 1.0, depth) * 0.95 + 0.02
    bottom_m = np.where(depth < 0, 1.0, np.where(depth > 1, 0.0, keep.astype(np.float64)))
    bottom_m = wc.blur(bottom_m, 0.7)
    m = m * bottom_m
    return np.clip(m, 0, 1)


def apply(rgb, mask, rim=0.35):
    """Trockenrand: innen an der Farbgrenze sammelt sich Pigment (Dichte höher)."""
    lin = wc.s2l(rgb)
    D = -np.log(np.clip(lin / wc.s2l(wc.PAPER), 1e-4, 1.0))
    D = D * (1 + rim * wc.inner_edge(mask, 3.0))[..., None]
    return wc.to_srgb_image(wc.s2l(wc.PAPER) * np.exp(-D), mask)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("inp")
    ap.add_argument("out")
    ap.add_argument("--bottom", type=float, default=600)
    ap.add_argument("--top", type=float, default=22)
    ap.add_argument("--side", type=float, default=18)
    ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("--preview", default="")
    a = ap.parse_args()
    rgb = np.asarray(Image.open(a.inp).convert("RGB").resize((1280, 720), Image.LANCZOS)).astype(np.float64) / 255
    m = vignette(top=a.top, side=a.side, bottom=a.bottom, seed=a.seed)
    im = apply(rgb, m)
    im.save(a.out)
    if a.preview:
        bg = Image.new("RGBA", im.size, tuple(int(c * 255) for c in wc.PAPER) + (255,))
        bg.alpha_composite(im)
        bg.convert("RGB").save(a.preview)
    print("ok", a.out)


if __name__ == "__main__":
    main()
