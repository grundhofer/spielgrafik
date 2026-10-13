#!/usr/bin/env python3
"""Rohrender (assets/raw/render/<shot>/) zu den Spieldaten einer festen Einstellung verarbeiten.

    .venv/bin/python styles/vorgerendert-fixkamera/scripts/bake.py [totale nah]

Je Einstellung entsteht in assets/bg/<shot>/ (und als Kopie in demo/bg/<shot>/):
  base.png     320×240, das ruhende Hintergrundbild: Median über alle Bilder der Schleife
  anim.png     Bildfolge-Overlay: nur das Rechteck, in dem sich etwas bewegt, alle Bilder als Raster
               (RGBA; A = weiche Maske, wo sich das Bild ändert)
  depth.png    Tiefenbild 320×240: Abstand entlang der Blickachse in Metern, 24 Bit in RGB
               (d = (R·65536 + G·256 + B) / 16777215 · DEPTH_RANGE), je Pixel der Median der 4×4 Strahlen
  lantern.png  Lichtebene der Laterne (Bild 0 minus Bild ohne Laterne, linear, sRGB-kodiert)
  meta.json    Kamera, Rechteck, Raster, Bildrate, Kennzahlen
Verkleinert wird in linearem Licht (Mittel aus 4×4 Pixeln), wie ein Renderer mit 16 Strahlen je Pixel.
"""
import json
import pathlib
import shutil
import subprocess
import sys

import numpy as np
from PIL import Image

STYLE = pathlib.Path(__file__).resolve().parent.parent
W, H, SS = 320, 240, 4
DEPTH_RANGE = 1000.0
THRESH = 3.0 / 255.0      # Änderung (sRGB, 0..1), ab der ein Pixel als bewegt gilt
PAD = 2                   # Rand um das bewegte Rechteck (Pixel)


def to_lin(a):
    return np.where(a <= 0.04045, a / 12.92, ((a + 0.055) / 1.055) ** 2.4)


def to_srgb(l):
    l = np.clip(l, 0.0, None)
    return np.where(l <= 0.0031308, l * 12.92, 1.055 * np.power(l, 1 / 2.4) - 0.055)


def load_down(path):
    a = np.asarray(Image.open(path).convert("RGB"), dtype=np.float32) / 255.0
    l = to_lin(a).reshape(H, SS, W, SS, 3).mean(axis=(1, 3))
    return l  # linear


def q8(srgb):
    return (np.clip(srgb, 0, 1) * 255.0 + 0.5).astype(np.uint8)


def read_exr_depth(path):
    """Tiefe aus dem EXR über Blender lesen (Pillow kann kein EXR); gibt float32 H*SS × W*SS zurück."""
    npy = path.with_suffix(".npy")
    if not npy.exists() or npy.stat().st_mtime < path.stat().st_mtime:
        code = ("import bpy, numpy as np; im = bpy.data.images.load(r'%s'); "
                "a = np.array(im.pixels[:], dtype=np.float32).reshape(im.size[1], im.size[0], 4)[::-1, :, 0]; "
                "np.save(r'%s', a)") % (path, npy)
        r = subprocess.run(["blender", "-b", "--factory-startup", "--python-expr", code],
                           capture_output=True, text=True)
        if not npy.exists():
            sys.exit("EXR nicht lesbar: " + r.stdout[-400:] + r.stderr[-400:])
    return np.load(npy)


def bake(shot):
    src = STYLE / "assets" / "raw" / "render" / shot
    out = STYLE / "assets" / "bg" / shot
    out.mkdir(parents=True, exist_ok=True)
    cam = json.loads((src / "camera.json").read_text())
    files = sorted(src.glob("f_*.png"))
    n = int(round(cam["loop_s"] * cam["fps"]))
    if len(files) != n:
        sys.exit(f"{shot}: {len(files)} Bilder, erwartet {n}")
    frames = np.stack([load_down(f) for f in files])          # n, H, W, 3 linear
    srgb = to_srgb(frames)
    base_s = np.median(srgb, axis=0)
    base8 = q8(base_s)
    Image.fromarray(base8).save(out / "base.png")

    # bewegte Pixel: größte Abweichung vom Median über die Schleife
    dev = np.abs(srgb - base_s[None]).max(axis=(0, 3))
    moving = dev > THRESH
    # 1 px erweitern (weiche Kante)
    m = moving.copy()
    for dy in (-1, 0, 1):
        for dx in (-1, 0, 1):
            m |= np.roll(np.roll(moving, dy, 0), dx, 1)
    ys, xs = np.nonzero(m)
    x0, x1 = max(0, xs.min() - PAD), min(W, xs.max() + 1 + PAD)
    y0, y1 = max(0, ys.min() - PAD), min(H, ys.max() + 1 + PAD)
    rw, rh = x1 - x0, y1 - y0
    # weiche Maske: bewegt = 1, erweiterter Rand = 0,5
    alpha = np.where(moving, 1.0, np.where(m, 0.5, 0.0))[y0:y1, x0:x1]
    cols = int(np.ceil(np.sqrt(n * rh / rw)))
    cols = max(1, min(n, cols))
    rows = int(np.ceil(n / cols))
    atlas = np.zeros((rows * rh, cols * rw, 4), np.uint8)
    for i in range(n):
        cy, cx = divmod(i, cols)
        tile = q8(srgb[i, y0:y1, x0:x1])
        atlas[cy * rh:(cy + 1) * rh, cx * rw:(cx + 1) * rw, :3] = tile
        atlas[cy * rh:(cy + 1) * rh, cx * rw:(cx + 1) * rw, 3] = (alpha * 255 + 0.5).astype(np.uint8)
    Image.fromarray(atlas, "RGBA").save(out / "anim.png", optimize=True)

    # Lichtebene der Laterne
    lit0 = frames[0]
    dim = load_down(src / "dim.png")
    L = np.clip(lit0 - dim, 0.0, None)
    # Rauschgrenze: Unterschiede unter 0,003 (linear) sind Renderrauschen, kein Laternenlicht. Liegt die
    # Laterne nicht im Bild (Lichtebene überall schwach), bleibt die Ebene leer, sonst flackert nur Rauschen.
    L[L.max(axis=2) < 0.003] = 0.0
    if L.max() < 0.1:
        L[:] = 0.0
    Image.fromarray(q8(to_srgb(L))).save(out / "lantern.png")

    # Tiefe: Median der 4×4 Strahlen je Pixel (ein echter Wert einer getroffenen Fläche, kein Mittel)
    z = read_exr_depth(src / "depth.exr")
    blocks = z.reshape(H, SS, W, SS).transpose(0, 2, 1, 3).reshape(H, W, SS * SS)
    blocks = np.sort(blocks, axis=2)
    d = blocks[:, :, SS * SS // 2 - 1]
    enc = np.round(np.clip(d / DEPTH_RANGE, 0, 1) * 16777215).astype(np.uint32)
    rgb = np.stack([(enc >> 16) & 255, (enc >> 8) & 255, enc & 255], axis=2).astype(np.uint8)
    Image.fromarray(rgb).save(out / "depth.png")
    # Vorschau der Tiefe (nur zum Ansehen)
    vis = np.clip(1.0 - np.log1p(np.minimum(d, 200.0)) / np.log1p(200.0), 0, 1)
    Image.fromarray((vis * 255).astype(np.uint8)).save(out / "depth_preview.png")

    meta = {
        "shot": shot, "size": [W, H], "camera": cam, "depth_range": DEPTH_RANGE,
        "anim": {"rect": [int(x0), int(y0), int(rw), int(rh)], "cols": cols, "rows": rows, "frames": n,
                 "fps": cam["fps"], "loop_s": cam["loop_s"],
                 "moving_share": round(float(moving.mean()), 4),
                 "rect_share": round(rw * rh / (W * H), 4)},
        "lantern_max": round(float(L.max()), 4),
        "step_last_to_first_max_8bit": int(np.abs(q8(srgb[0]).astype(int) - q8(srgb[-1]).astype(int)).max()),
        "near_depth_m": round(float(d.min()), 3),
    }
    (out / "meta.json").write_text(json.dumps(meta, indent=1))
    dst = STYLE / "demo" / "bg" / shot
    dst.mkdir(parents=True, exist_ok=True)
    for f in ("base.png", "anim.png", "depth.png", "lantern.png", "meta.json"):
        shutil.copy2(out / f, dst / f)
    print(shot, json.dumps(meta["anim"]), "lantern_max", meta["lantern_max"], "near", meta["near_depth_m"])


if __name__ == "__main__":
    for s in (sys.argv[1:] or ["totale", "nah"]):
        bake(s)
