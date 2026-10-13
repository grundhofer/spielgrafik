#!/usr/bin/env python3
"""Papierteile für Oberfläche und Effekte, aus Code mit dem Papierkorn des KI-Hintergrunds.

note.png    Notizzettel (cremefarben, liniert, oben gerissen) für Zeile, Antworten und Parser
tape_*.png  zwei Kreppbandstreifen (halbdurchsichtig, gezackte Enden)
slip_*.png  drei Antwortzettel aus verschiedenen Papieren (geschnitten, leicht schief)
snip_*.png  Papierschnipsel für die Buchstaben des Ortsnamens (Erpresserbrief-Collage)
beam.png    Lichtkeil des Leuchtturms aus Seidenpapier
pin.png     Musterklammer (Messing) für die Gelenke der Puppe

    .venv/bin/python styles/papier-collage/scripts/prep_ui.py
"""
import json, pathlib, sys
import numpy as np
from PIL import Image, ImageDraw, ImageFilter

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from pc_util import save_rgba, shadow_from_alpha  # noqa: E402

HERE = pathlib.Path(__file__).resolve().parent.parent
RAW = HERE / "assets" / "raw"
OUT = HERE / "assets" / "ui"
rng = np.random.default_rng(23)

b = np.asarray(Image.open(RAW / "back.png").convert("RGB")).astype(np.float64)
_g = b[692:746, :, :].mean(-1)
_g = _g / _g.mean()
GRAIN = np.concatenate([np.concatenate([_g, _g[:, ::-1]], 1)] * 2, 0)   # 108 x 2528


def grain(h, w, ox=0, oy=0, strength=1.0):
    ys = (np.arange(h) + oy) % GRAIN.shape[0]
    xs = (np.arange(w) + ox) % GRAIN.shape[1]
    g = GRAIN[ys][:, xs]
    return 1 + (g - 1) * strength


def noise1d(n, octaves, seed_off=0):
    x = np.arange(n, dtype=float)
    out = np.zeros(n)
    for f, a in octaves:
        ph = rng.uniform(0, 2 * np.pi, 2)
        out += a * (0.6 * np.sin(2 * np.pi * f * x + ph[0]) + 0.4 * np.sin(2 * np.pi * f * 1.41 * x + ph[1]))
    return out


def torn_top(w, h, base, color, rim=3.0, white=(238, 235, 226), ox=0):
    """Rechteck mit gerissener Oberkante und weißem Faserrand."""
    edge = base + noise1d(w, [(1 / 120, 2.0), (1 / 37, 1.1), (1 / 11, 0.6), (1 / 3, 0.35)])
    rw = rim + 1.2 * np.sin(np.arange(w) / 9.0) * 0 + rng.uniform(0, 1.5, w)
    fib = rng.uniform(0, 1, w) < 0.2
    edge_o = edge - np.where(fib, rng.uniform(0.5, 2.0, w), 0)
    yy = np.arange(h)[:, None]
    cov = np.clip(yy - edge_o[None] + 0.5, 0, 1)
    colz = np.clip(yy - (edge + rw)[None] + 0.5, 0, 1)
    g = grain(h, w, ox)
    paper = np.array(color, float)[None, None] * g[..., None]
    wh = np.array(white, float)[None, None] * (0.95 + 0.05 * g[..., None])
    rgb = wh * (1 - colz[..., None]) + paper * colz[..., None]
    return rgb, cov, edge


def cut_poly_alpha(w, h, poly, ss=4):
    im = Image.new("L", (w * ss, h * ss), 0)
    ImageDraw.Draw(im).polygon([(x * ss, y * ss) for x, y in poly], fill=255)
    return np.asarray(im.resize((w, h), Image.LANCZOS)).astype(float) / 255


def jag_rect(w, h, m, jit):
    """Geschnittenes Viereck: Ecken leicht verschoben, Kanten mit wenigen Knicken (Schere)."""
    pts = []
    corners = [(m, m), (w - m, m), (w - m, h - m), (m, h - m)]
    for i in range(4):
        x0, y0 = corners[i]
        x1, y1 = corners[(i + 1) % 4]
        x0 += rng.uniform(-jit, jit); y0 += rng.uniform(-jit, jit)
        pts.append((x0, y0))
        for t in (0.33, 0.66):
            pts.append((x0 + (x1 - x0) * t + rng.uniform(-jit * 0.4, jit * 0.4),
                        y0 + (y1 - y0) * t + rng.uniform(-jit * 0.4, jit * 0.4)))
    return pts


def save(name, rgb, A, blur=3.0, pad=10):
    save_rgba(OUT / f"{name}.png", rgb, A)
    shadow_from_alpha(A, blur, pad).save(OUT / f"{name}_shadow.png")
    return {"file": f"{name}.png", "shadow": f"{name}_shadow.png", "size": [A.shape[1], A.shape[0]], "pad": pad}


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    meta = {}
    # Notizzettel
    W, H = 1236, 118
    rgb, A, edge = torn_top(W, H, 9, (236, 228, 208), rim=2.5, ox=300)
    # seitlich und unten geschnitten: leicht schräge Kanten
    side = cut_poly_alpha(W, H, [(3, 0), (W - 2, 0), (W - 5, H - 3), (5, H - 2)])
    A = A * side
    yy = np.arange(H)[:, None] + np.zeros((1, W))
    for ly in range(40, H - 6, 25):                              # blasse Linien
        line = np.clip(1 - np.abs(yy - ly) / 0.9, 0, 1) * 0.22
        rgb = rgb * (1 - line[..., None]) + np.array([120, 150, 190])[None, None] * line[..., None]
    xx = np.arange(W)[None, :] + np.zeros((H, 1))
    margin = np.clip(1 - np.abs(xx - 58) / 1.0, 0, 1) * 0.35 * (yy > edge[None, :] + 6)
    rgb = rgb * (1 - margin[..., None]) + np.array([200, 90, 90])[None, None] * margin[..., None]
    meta["note"] = save("note", rgb, A, 4.0, 14)
    # Kreppband
    for i in range(2):
        w, h = 92, 30
        poly = [(4, 3 + rng.uniform(-1, 1))]
        for y in np.linspace(3, h - 3, 7):
            poly.append((w - 4 + rng.uniform(-2.5, 2.5), y))
        for y in np.linspace(h - 3, 3, 7):
            poly.append((4 + rng.uniform(-2.5, 2.5), y))
        a = cut_poly_alpha(w, h, poly) * 0.78
        g = grain(h, w, 500 + 90 * i)
        rgbt = np.array([226, 210, 168], float)[None, None] * g[..., None]
        meta[f"tape_{i}"] = save(f"tape_{i}", rgbt, a, 2.0, 8)
    # Antwortzettel
    papers = [(244, 240, 228), (214, 186, 140), (232, 222, 150)]
    widths = [282, 248, 304]
    for i, (w, col) in enumerate(zip(widths, papers)):
        h = 36
        a = cut_poly_alpha(w, h, jag_rect(w, h, 3, 1.6))
        g = grain(h, w, 1000 + 333 * i, 17 * i)
        rgbs = np.array(col, float)[None, None] * g[..., None]
        meta[f"slip_{i}"] = save(f"slip_{i}", rgbs, a, 2.5, 10)
    # Buchstabenschnipsel (Ortsname)
    snip_cols = [(244, 240, 230), (206, 178, 132), (40, 40, 46), (190, 58, 56), (230, 226, 210), (120, 132, 150),
                 (236, 214, 120)]
    meta["snips"] = []
    for i in range(18):
        w, h = int(rng.integers(36, 46)), int(rng.integers(46, 56))
        a = cut_poly_alpha(w, h, jag_rect(w, h, 3, 2.4))
        col = snip_cols[i % len(snip_cols)] if i % 5 else snip_cols[(i * 3) % len(snip_cols)]
        g = grain(h, w, 1700 + 61 * i, 5 * i)
        rgbs = np.array(col, float)[None, None] * g[..., None]
        info = save(f"snip_{i}", rgbs, a, 2.0, 8)
        info["paper"] = list(col)
        meta["snips"].append(info)
    # Lichtkeil aus Seidenpapier (zeigt nach links, Spitze rechts in der Lampe)
    # Textur 150 px hoch bei 116 px Keilbreite: die Ränder laufen nicht an die Texturkante. Das ferne Ende ist
    # rund und gerissen (Halbbogen + Rissrauschen, Faserrand etwas dichter) statt senkrecht abgeschnitten.
    w, h, hw = 560, 150, 54
    top = h / 2 - hw * (1 - np.arange(w) / w) ** 1.0 - 4 + noise1d(w, [(1 / 40, 1.4), (1 / 9, 0.6)])
    bot = h / 2 + hw * (1 - np.arange(w) / w) ** 1.0 + 4 + noise1d(w, [(1 / 40, 1.4), (1 / 9, 0.6)])
    yy = np.arange(h)[:, None]
    xx = np.arange(w)[None, :]
    a = np.clip(yy - top[None] + 0.5, 0, 1) * np.clip(bot[None] - yy + 0.5, 0, 1)
    dy = (np.arange(h) - h / 2) / (hw + 6)
    end = 8 + 30 * (1 - np.sqrt(np.clip(1 - dy ** 2, 0, 1))) + noise1d(h, [(1 / 23, 2.2), (1 / 7, 1.0), (1 / 2.5, 0.6)])
    end -= np.where(rng.uniform(0, 1, h) < 0.2, rng.uniform(0.6, 2.4, h), 0)           # einzelne Fasern
    a *= np.clip(xx - end[:, None] + 0.5, 0, 1)
    a *= 1 + 0.35 * np.clip(1 - np.abs(xx - end[:, None] - 1.5) / 1.5, 0, 1)            # Faserrand
    fade = 0.25 + 0.75 * (np.arange(w) / w) ** 0.6                  # zur Lampe hin dichter
    g = grain(h, w, 2100, 30, 1.6)
    a = a * fade[None, :] * (0.85 + 0.15 * g)
    rgbb = np.array([255, 236, 170], float)[None, None] * np.ones((h, w, 1))
    save_rgba(OUT / "beam.png", rgbb, a)
    meta["beam"] = {"file": "beam.png", "size": [w, h], "pivot": [w - 6, h / 2]}
    # Musterklammer
    s = 28
    yy, xx = np.mgrid[0:s, 0:s] + 0.5
    r = np.hypot(xx - s / 2, yy - s / 2)
    a = np.clip(s / 2 - 2 - r + 0.5, 0, 1)
    lit = np.clip(1 - np.hypot(xx - s * 0.38, yy - s * 0.36) / (s * 0.5), 0, 1)
    base = np.array([150, 112, 48], float)
    rgbp = base[None, None] * (0.7 + 0.6 * lit[..., None])
    rim = np.clip(1 - np.abs(r - (s / 2 - 3)) / 1.2, 0, 1)
    rgbp = rgbp * (1 - 0.35 * rim[..., None])
    meta["pin"] = save("pin", np.clip(rgbp, 0, 255), a, 1.5, 6)
    (OUT / "ui.json").write_text(json.dumps(meta, indent=1))
    print("ok", len(meta))


if __name__ == "__main__":
    main()
