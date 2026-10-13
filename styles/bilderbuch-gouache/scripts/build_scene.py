#!/usr/bin/env python3
"""Hintergrund, Boote, gemalte Effekte und Oberflächenteile für den Eintrag bilderbuch-gouache.

    .venv/bin/python styles/bilderbuch-gouache/scripts/build_scene.py

Eingänge: assets/raw/bg.png und assets/raw/boats.png (agy), tools/gouache.py (Pinselbibliothek des Eintrags).
Ausgänge (assets/, von build_all.sh nach demo/art/ kopiert):
  bg.png                  Ausschnitt 16:9 aus der bemalten Fläche (ohne Papierrand), 1280x720
  boat_a.png, boat_b.png  Boote, vormultipliziert verkleinert, Farbe in den Rand ausgebreitet
  fx/*.png                in Code gemalte Gouache-Tupfer: Rauch, Lichthöfe, Strahlen, Glitzer, Sterne, Schatten,
                          Wellenstriche an den Booten, Aufzählungstupfer und Unterstreichung für die Oberfläche
  paper.png               Papierkorn zum Multiplizieren über das ganze Bild (kachelbar)
  scene.json              Lage aller Lichter, Sterne, Boote, Wasserband (von Hand im Raster gemessen, siehe unten)
Alle Effekte werden in doppelter Größe gemalt und dann halbiert (Pinselspuren bleiben fein, Kanten glatt).
"""
import json, pathlib, sys

import numpy as np
from PIL import Image

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(ROOT / "tools"))
from gutil import label, premul_resize, bleed_rgb  # noqa: E402
from gouache import (noise, ellipse_sdf, roundrect_sdf, dab_alpha, paint_rgb, to_image,  # noqa: E402
                     smoothstep)

A = ROOT / "assets"
FX = A / "fx"

# Ausschnitt der bemalten Fläche im Rohbild (1264x848; Papierrand ca. 40 px rundum, ausgemessen)
CROP = (48, 100, 1218, 758)      # 1170x658 = 16:9
OUT = (1280, 720)

# Von Hand im 40-px-Raster des Ausschnitts gemessen (Bildschirmkoordinaten 1280x720)
SCENE = {
    "chimney": [221, 141],          # Oberkante Schornsteintopf
    "lamp": [1148, 176],            # Leuchtturmlampe
    "lantern": [895, 373],          # Laterne am Pfahl (Glas)
    "window": [113, 487, 64, 76],   # Fenster des Häuschens: Mitte, Breite, Höhe
    "horizon_y": 410,
    "water": [312, 412, 1080, 533],  # Wasserfläche ohne Landzunge: x0, y0, x1, y1
    "quay_y": 535,                   # Oberkante Kaimauer
    "feet_y": 652,                   # Laufzeile des Dachses
    "boats": {
        "boat_b": {"x": 392, "water_y": 503, "phase": 0.0},
        "boat_a": {"x": 808, "water_y": 505, "phase": 1.7},
    },
}
BOAT_SCALE = 0.34
BOAT_SRC = {  # Komponente im Rohbogen (x0, y0, x1, y1) und Wasserlinie im Rohbogen
    "boat_a": {"box": (94, 164, 609, 637), "water": 592},
    "boat_b": {"box": (669, 161, 1169, 638), "water": 598},
}


def half(im):
    return premul_resize(im, (im.width // 2, im.height // 2))


def layer(h, w, sdf, rgb, seed, **kw):
    a = dab_alpha(sdf, seed, **{k: v for k, v in kw.items() if k in
                                ("wobble", "wobble_cell", "streak", "streak_cells", "soft", "holes")})
    c = paint_rgb(h, w, rgb, seed, **{k: v for k, v in kw.items() if k in
                                      ("streak_amp", "grain_amp", "cells", "tint", "tint_amp")})
    return c, a


def over(dst_rgb, dst_a, rgb, a):
    out_a = a + dst_a * (1 - a)
    out_rgb = (rgb * a[..., None] + dst_rgb * dst_a[..., None] * (1 - a[..., None])) / np.maximum(out_a, 1e-4)[..., None]
    return out_rgb, out_a


def smoke_puff(seed, size=150):
    """Runder Rauchtupfer: dunklere Grundform, hellere Kuppe oben links (helle Farbe auf dunkler, wie Gouache)."""
    h = w = size
    r = size * 0.36
    sdf = ellipse_sdf(h, w, w / 2, h / 2 + 2, r * 1.08, r)
    rgb, a = layer(h, w, sdf, (176, 168, 186), seed, wobble=5, wobble_cell=26, streak=3.5, streak_cells=(6, 26),
                   soft=1.2, holes=0.12, streak_amp=0.05, grain_amp=0.03, cells=(5, 24), tint=(196, 170, 176),
                   tint_amp=0.5)
    sdf2 = ellipse_sdf(h, w, w / 2 - r * 0.18, h / 2 - r * 0.2, r * 0.8, r * 0.7)
    rgb2, a2 = layer(h, w, sdf2, (226, 216, 214), seed + 50, wobble=5, wobble_cell=22, streak=4, streak_cells=(5, 22),
                     soft=1.2, holes=0.18, streak_amp=0.05, grain_amp=0.03, cells=(5, 20), tint=(240, 222, 204),
                     tint_amp=0.6)
    a2 = a2 * a
    rgb, a = over(rgb, a, rgb2, a2)
    return half(to_image(rgb, a))


def halo(seed, size, rings, cols):
    """Lichthof wie im Bilderbuch: konzentrische, flach gemalte Ringe heller Farbe, außen durchscheinend."""
    h = w = size
    rgb = np.zeros((h, w, 3), np.float32)
    al = np.zeros((h, w), np.float32)
    for i, (rr, col, op) in enumerate(zip(rings, cols, [0.14, 0.22, 0.42, 0.95])):
        sdf = ellipse_sdf(h, w, w / 2, h / 2, rr * size / 2, rr * size / 2)
        c, a = layer(h, w, sdf, col, seed + i * 7, wobble=size * 0.02, wobble_cell=size * 0.15, streak=size * 0.012,
                     streak_cells=(4, 30), soft=1.4, holes=0.1, streak_amp=0.04, grain_amp=0.03, cells=(4, 30))
        rgb, al = over(rgb, al, c, a * op)
    return half(to_image(rgb, al))


def rays(seed, size=220, n=8, inner=0.2, outer=0.48):
    """Kurze gemalte Strahlen um die Leuchtturmlampe (Kinderbuch-Zeichen für Blinken)."""
    h = w = size
    y, x = np.mgrid[0:h, 0:w].astype(np.float32)
    dx, dy = x - w / 2, y - h / 2
    rad = np.hypot(dx, dy) / (size / 2)
    ang = np.arctan2(dy, dx)
    rng = np.random.RandomState(seed)
    al = np.zeros((h, w), np.float32)
    for k in range(n):
        a0 = k * 2 * np.pi / n + rng.uniform(-0.08, 0.08)
        o = outer * rng.uniform(0.82, 1.05)
        d = np.abs(np.angle(np.exp(1j * (ang - a0))))
        width = 0.075 * (1.15 - (rad - inner) / (o - inner) * 0.6)
        sdf = (width - d * rad) * size / 2 * 0.9
        sdf = np.minimum(sdf, (rad - inner) * size / 2)
        sdf = np.minimum(sdf, (o - rad) * size / 2)
        a = dab_alpha(sdf, seed + k, wobble=1.5, wobble_cell=12, streak=2.5, streak_cells=(3, 14), soft=1.0, holes=0.08)
        al = np.maximum(al, a)
    rgb = paint_rgb(h, w, (255, 226, 150), seed, streak_amp=0.04, grain_amp=0.03, cells=(3, 14),
                    tint=(255, 196, 120), tint_amp=0.5)
    return half(to_image(rgb, al))


def stroke(seed, w, h, rgb, tint=None, holes=0.2):
    """Kurzer waagerechter Pinselstrich mit runden Enden und Trockenpinsel-Fransen."""
    H, W = h * 2 + 12, w * 2 + 12
    sdf = roundrect_sdf(H, W, 6, 6, W - 6, H - 6, h)
    c, a = layer(H, W, sdf, rgb, seed, wobble=1.6, wobble_cell=14, streak=h * 0.5, streak_cells=(2, 28), soft=1.0,
                 holes=holes, streak_amp=0.05, grain_amp=0.03, cells=(2, 30), tint=tint, tint_amp=0.5 if tint else 0)
    return half(to_image(c, a))


def star(seed, size=40):
    h = w = size
    y, x = np.mgrid[0:h, 0:w].astype(np.float32)
    dx, dy = np.abs(x - w / 2), np.abs(y - h / 2)
    # vierzackiger Stern als Abstandsfeld (Raute + Kreuz)
    cross = np.minimum(size * 0.42 - (dx + dy * 4.5), size * 0.42 - (dy + dx * 4.5))
    core = size * 0.16 - np.hypot(dx, dy)
    sdf = np.maximum(cross * 0.5, core)
    c, a = layer(h, w, sdf, (252, 240, 214), seed, wobble=0.6, wobble_cell=8, streak=0.6, streak_cells=(2, 6), soft=0.9,
                 holes=0.0, streak_amp=0.03, grain_amp=0.02, cells=(2, 8))
    return half(to_image(c, a))


def underline(seed, w=230, h=13):
    """Unterstreichung für die gewählte Antwort: ein trockener Pinselstrich, links satt, rechts ausfasernd."""
    H, W = h * 2 + 16, w * 2 + 16
    y, x = np.mgrid[0:H, 0:W].astype(np.float32)
    t = (x - 8) / (W - 16)
    thick = h * (1.0 - 0.45 * t) + 2 * np.sin(t * 7 + seed)
    cy = H / 2 + 3 * np.sin(t * 3.1 + 0.4)
    sdf = np.minimum(thick - np.abs(y - cy), np.minimum(x - 8, W - 8 - x) * 1.0)
    a = dab_alpha(sdf, seed, wobble=2.0, wobble_cell=16, streak=h * 0.9, streak_cells=(2, 40), soft=1.0, holes=0.0)
    dry = noise(H, W, 2, 22, seed + 9, 1)
    a *= 1 - (dry < (0.15 + 0.55 * t)).astype(np.float32) * smoothstep(0.35, 1.0, t) * 0.9
    c = paint_rgb(H, W, (236, 150, 104), seed, streak_amp=0.06, grain_amp=0.03, cells=(2, 40), tint=(244, 182, 120),
                  tint_amp=0.5)
    return half(to_image(c, a))


def bullet(seed, col, size=24):
    h = w = size * 2
    sdf = ellipse_sdf(h, w, w / 2, h / 2, w * 0.4, h * 0.38)
    c, a = layer(h, w, sdf, col, seed, wobble=2.5, wobble_cell=18, streak=2.5, streak_cells=(3, 20), soft=1.1,
                 holes=0.1, streak_amp=0.05, grain_amp=0.03, cells=(3, 18))
    return half(to_image(c, a))


def band(seed, w=370, h=126):
    """Dunkler Pinselstreifen hinter den Antworten: wie eine gemalte Wolkenbank im Himmel, damit die helle Schrift
    auch im helleren unteren Himmel lesbar bleibt. Trockenpinsel an den Enden, waagerechte Strichspuren."""
    H, W = h * 2 + 40, w * 2 + 40
    sdf = roundrect_sdf(H, W, 20, 20, W - 20, H - 20, h * 0.9)
    c, a = layer(H, W, sdf, (42, 68, 90), seed, wobble=8, wobble_cell=50, streak=12, streak_cells=(4, 80), soft=1.4,
                 holes=0.28, streak_amp=0.06, grain_amp=0.03, cells=(3, 70), tint=(56, 58, 92), tint_amp=0.5)
    return half(to_image(c, a))


def shadow(seed, w=140, h=26):
    H, W = h * 2, w * 2
    sdf = ellipse_sdf(H, W, W / 2, H / 2, W * 0.46, H * 0.4)
    c, a = layer(H, W, sdf, (122, 88, 74), seed, wobble=3, wobble_cell=24, streak=5, streak_cells=(3, 30), soft=1.2,
                 holes=0.15, streak_amp=0.05, grain_amp=0.03, cells=(3, 30), tint=(110, 86, 96), tint_amp=0.5)
    return half(to_image(c, a))


def paper(seed=5, size=512):
    """Kachelbares Papierkorn (um 1 herum), wird im Shader multipliziert."""
    rng = np.random.RandomState(seed)
    g = rng.rand(size, size).astype(np.float32)
    big = np.zeros((size, size), np.float32)
    for cell, amp in ((2, 0.5), (5, 0.3), (16, 0.2)):
        small = rng.rand(size // cell, size // cell).astype(np.float32)
        im = Image.fromarray((small * 255).astype(np.uint8)).resize((size, size), Image.BICUBIC)
        # kachelbar machen: Ränder überblenden
        arr = np.asarray(im, np.float32) / 255.0
        big += amp * arr
    v = 0.6 * big + 0.4 * g
    v = (v - v.mean()) / v.std()
    v = np.clip(128 + v * 22, 0, 255).astype(np.uint8)
    return Image.fromarray(v, "L")


def find_stars(bg):
    """Kleine helle Punkte im Himmel (gemalte Sterne), für das Funkeln. Nur dort, wo die Umgebung Himmel ist
    (bläulich und dunkel), sonst findet die Suche Glanzlichter am Schornstein, Leuchtturm und Dach."""
    a = np.asarray(bg.convert("RGB"), np.float32)
    lum = a.mean(2)
    h, w = lum.shape
    small = bg.convert("RGB").resize((w // 8, h // 8), Image.BOX)
    blur = np.asarray(small.resize((w, h), Image.BILINEAR), np.float32)
    sky = (blur[..., 2] > blur[..., 0] + 15) & (blur.mean(2) < 140)
    m = (lum - blur.mean(2) > 45) & (np.arange(h)[:, None] < 330) & sky
    lab, n = label(m)
    out = []
    for i in range(1, n + 1):
        ys, xs = np.nonzero(lab == i)
        if 1 <= len(ys) <= 30 and sky[int(ys.mean()), int(xs.mean())]:
            out.append([round(float(xs.mean()), 1), round(float(ys.mean()), 1)])
    return out


def build_bg():
    raw = Image.open(A / "raw/bg.png").convert("RGB")
    bg = raw.crop(CROP).resize(OUT, Image.LANCZOS)
    bg.save(A / "bg.png")
    return bg


def build_boats():
    raw = Image.open(A / "raw/boats.png").convert("RGBA")
    arr = np.asarray(raw).copy()
    lab, n = label(arr[..., 3] > 8)
    info = {}
    for name, s in BOAT_SRC.items():
        x0, y0, x1, y1 = s["box"]
        sub = lab[y0:y1, x0:x1]
        ids, cnt = np.unique(sub[sub > 0], return_counts=True)
        keep = ids[cnt > 200]
        part = arr[y0:y1, x0:x1].copy()
        part[~np.isin(sub, keep)] = 0
        # Magenta-Rest am Rand
        rgb = part[..., :3].astype(np.float32)
        m = np.clip(np.minimum(rgb[..., 0], rgb[..., 2]) - rgb[..., 1], 0, None)
        rgb[..., 0] -= m
        rgb[..., 2] -= m
        part[..., :3] = rgb.clip(0, 255).astype(np.uint8)
        im = bleed_rgb(Image.fromarray(part, "RGBA"), 6)
        w, h = round(im.width * BOAT_SCALE), round(im.height * BOAT_SCALE)
        sm = bleed_rgb(premul_resize(im, (w, h)), 4)
        sm.save(A / f"{name}.png")
        info[name] = {"w": w, "h": h, "water_local": round((s["water"] - y0) * BOAT_SCALE, 1)}
    return info


def main():
    FX.mkdir(parents=True, exist_ok=True)
    bg = build_bg()
    boats = build_boats()
    for i in range(3):
        smoke_puff(31 + i * 13).save(FX / f"smoke_{i}.png")
    halo(7, 260, [1.0, 0.68, 0.4, 0.18], [(240, 200, 150), (246, 212, 156), (252, 226, 170), (255, 244, 212)]) \
        .save(FX / "halo_lamp.png")
    halo(9, 200, [1.0, 0.66, 0.38, 0.16], [(240, 170, 110), (248, 196, 128), (255, 220, 150), (255, 240, 200)]) \
        .save(FX / "halo_lantern.png")
    halo(13, 160, [1.0, 0.7, 0.45, 0.2], [(236, 168, 112), (246, 190, 126), (252, 210, 150), (255, 232, 190)]) \
        .save(FX / "halo_window.png")
    rays(17).save(FX / "rays.png")
    for i, (w, col, tint) in enumerate([(46, (250, 234, 204), (250, 206, 166)), (30, (244, 224, 198), None),
                                        (60, (250, 196, 150), (252, 222, 186)), (38, (206, 226, 222), None)]):
        stroke(40 + i, w, 4, col, tint, holes=0.2).save(FX / f"glint_{i}.png")
    for i in range(2):
        stroke(60 + i, 92, 3, (156, 186, 196), (190, 206, 206), holes=0.3).save(FX / f"ripple_{i}.png")
    star(70).save(FX / "star.png")
    underline(80).save(FX / "underline.png")
    for i, col in enumerate([(232, 132, 104), (110, 168, 170), (226, 176, 92)]):
        bullet(90 + i, col).save(FX / f"bullet_{i}.png")
    shadow(99).save(FX / "shadow.png")
    band(101).save(FX / "band.png")
    paper().save(A / "paper.png")
    scene = dict(SCENE)
    scene["stars"] = find_stars(bg)
    for k, v in boats.items():
        scene["boats"][k].update(v)
    (A / "scene.json").write_text(json.dumps(scene, indent=1))
    print("ok bg", bg.size, "boats", boats, "stars", len(scene["stars"]))


if __name__ == "__main__":
    main()
