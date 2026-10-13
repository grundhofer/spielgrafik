#!/usr/bin/env python3
"""Bogen des Dachs-Kuriers aus dem KI-Laufbogen (gpt-image, 2x5 Figuren nach dem Blender-Layout).

    .venv/bin/python styles/ukiyo-e/scripts/build_badger.py

Eingang: assets/raw/walk.png, assets/ref/layout.json (Zellen 307x512)
Ausgang (assets/ und demo/art/):
  badger.png        Totale: eine Reihe walk_0 … walk_7, stand, turn, blink (turn mit geschlossenen Augen), RGBA,
                    Faktor 0,26875 (Figur 113 px, passend zu Tür, Fässern und Laterne)
  badger_close.png  Nahaufnahme: dieselben Bilder mit Faktor 0,43 (Figur 181 px) = 1,6-fache Totale
  badger.json       Bildgrößen, Sohlenlinien, Maßstäbe, Messwerte je KI-Zelle

Die Farben bleiben, wie das Bildmodell sie gedruckt hat (flache Farben, schwarze Kontur, kein Farbauszug nötig).
Je Zelle: größte Alphafläche (Alpha >= 128), der weiche Alpharand der KI bleibt in einem 2-px-Saum erhalten.
Ausrichtung: x in Zellkoordinaten (Nasenspitze in allen Laufzellen auf ±3 KI-px gleich), y an der Sohle (unterste
Alphazeile). Verkleinern mit vormultipliziertem Alpha (Lanczos).
Blinzeln: Im Dreiviertelbild werden beide Augen mit dem Grau des Augenstreifs zugedeckt und ein gebogener
Lidstrich in Konturschwarz gezeichnet (Augenstellen von Hand an 4-fach vergrößerten Köpfen abgelesen).
"""
import json, pathlib
import numpy as np
from PIL import Image, ImageDraw

ROOT = pathlib.Path(__file__).resolve().parents[1]
OUTS = [ROOT / "assets", ROOT / "demo/art"]
SCALE_CLOSE = 0.43      # ~421 KI-px Figur -> ~181 px (Nahaufnahme)
ZOOM = 1.6              # Nahaufnahme / Totale (scene.json "closeup")
SCALE = SCALE_CLOSE / ZOOM   # Totale: ~113 px
CELL_W = 307
TOP, BOT = 450, 6       # Rahmen über / unter der Sohle (KI-Pixel)
# Augen im Dreiviertelbild (Zellkoordinaten x, y, Halbachsen rx, ry), abgelesen an z_turnhead (4-fach)
TURN_EYES = [(177.5, 131.0, 8.5, 8.0), (223.5, 124.0, 5.5, 7.0)]
KEY = (24, 20, 22)


def largest_component(b):
    h, w = b.shape
    lab = np.zeros((h, w), np.int32)
    best, best_n, cur = 0, 0, 0
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
        if n > best_n:
            best_n, best = n, cur
    return lab == best


def dilate(b, r):
    out = b.copy()
    for dy in range(-r, r + 1):
        for dx in range(-r, r + 1):
            if dx * dx + dy * dy <= r * r:
                out |= np.roll(np.roll(b, dy, 0), dx, 1)
    return out


def close_eyes(rgba):
    """Augen zudecken (Grau des Augenstreifs, gemessen neben dem Auge) und Lidstrich zeichnen. rgba: uint8 HxWx4."""
    ss = 4
    im = Image.fromarray(rgba, "RGBA")
    big = im.resize((im.width * ss, im.height * ss), Image.NEAREST)
    dr = ImageDraw.Draw(big)
    arr = np.asarray(im)
    for ex, ey, rx, ry in TURN_EYES:
        # Streifengrau: Median eines Rings knapp außerhalb des Auges, nur dunkelgraue Pixel
        yy, xx = np.mgrid[0:arr.shape[0], 0:arr.shape[1]]
        d = ((xx - ex) / (rx + 4)) ** 2 + ((yy - ey) / (ry + 4)) ** 2
        ring = (d > 1.0) & (d < 1.8) & (arr[..., 3] > 200)
        px = arr[ring][:, :3].astype(int)
        grey = px[(px.sum(1) > 120) & (px.sum(1) < 330)]
        g = tuple(int(v) for v in np.median(grey, 0)) if len(grey) else (80, 80, 84)
        box = [(ex - rx - 1.5) * ss, (ey - ry - 1.5) * ss, (ex + rx + 1.5) * ss, (ey + ry + 1.5) * ss]
        dr.ellipse(box, fill=g + (255,))
        # Lidstrich: nach unten gebogener Bogen über die Augenbreite
        arc = [(ex - rx - 1) * ss, (ey - ry * 0.9) * ss, (ex + rx + 1) * ss, (ey + ry * 0.9) * ss]
        dr.arc(arc, start=20, end=160, fill=KEY + (255,), width=int(2.6 * ss))
    return np.asarray(big.resize(im.size, Image.LANCZOS))


def downscale(rgba, size):
    f = rgba.astype(np.float32) / 255.0
    a = f[..., 3:4]
    pm = np.concatenate([f[..., :3] * a, a], -1)
    ch = [np.asarray(Image.fromarray(pm[..., k], "F").resize(size, Image.LANCZOS)) for k in range(4)]
    al = np.clip(ch[3], 0, 1)
    col = np.stack(ch[:3], -1) / np.maximum(al[..., None], 1e-4)
    col[al < 1e-3] = 0
    out = np.concatenate([np.clip(col, 0, 1), al[..., None]], -1)
    return (out * 255 + 0.5).astype(np.uint8)


def main():
    im = np.asarray(Image.open(ROOT / "assets/raw/walk.png").convert("RGBA"))
    lay = json.loads((ROOT / "assets/ref/layout.json").read_text())
    frames, meta = [], []
    for c in lay["cells"]:
        x, y, w, h = c["x"], c["y"], c["w"], c["h"]
        sub = im[y:y + h, x:x + w].copy()
        core = largest_component(sub[..., 3] >= 128)
        keep = dilate(core, 2)
        sub[..., 3] = (sub[..., 3] * keep).astype(np.uint8)
        ys, xs = np.nonzero(core)
        sole, top = int(ys.max()), int(ys.min())
        canvas = np.zeros((TOP + BOT, w, 4), np.uint8)
        y0 = sole - TOP
        sy0, sy1 = max(0, y0), min(h, sole + BOT)
        canvas[sy0 - y0:sy1 - y0] = sub[sy0:sy1]
        frames.append(canvas)
        bot = core[sole - 2:sole + 1]
        cols = np.nonzero(bot.any(0))[0]
        gaps = np.nonzero(np.diff(cols) > 2)[0]
        contact = [(int(q[0]), int(q[-1])) for q in np.split(cols, gaps + 1)]
        up = core[top:top + (sole - top) // 4]
        meta.append({"name": c["name"], "sole_ai": sole, "height_ai": sole - top + 1, "contact_ai": contact,
                     "nose_x_ai": int(np.nonzero(up.any(0))[0].max()), "cx_ai": round(float(xs.mean()), 1)})
        if c["name"] == "turn":
            # Augen in Rahmenkoordinaten: y + (TOP - sole)
            shift = TOP - sole
            global TURN_EYES
            TURN_EYES = [(ex, ey + shift, rx, ry) for ex, ey, rx, ry in TURN_EYES]
            blink = close_eyes(canvas)
    frames.append(blink)
    meta.append(dict(meta[-1], name="blink"))

    info = {"frames": len(frames), "top_ai": TOP, "names": [m["name"] for m in meta]}
    for name, sc, key in (("badger.png", SCALE, ""), ("badger_close.png", SCALE_CLOSE, "_close")):
        fw, fh = round(CELL_W * sc), round((TOP + BOT) * sc)
        sheet = np.zeros((fh, fw * len(frames), 4), np.uint8)
        for i, fr in enumerate(frames):
            sheet[:, i * fw:(i + 1) * fw] = downscale(fr, (fw, fh))
        img = Image.fromarray(sheet, "RGBA")
        for d in OUTS:
            d.mkdir(parents=True, exist_ok=True)
            img.save(d / name)
        info.update({"frame_w" + key: fw, "frame_h" + key: fh, "scale" + key: sc, "sole_y" + key: round(TOP * sc, 2)})
        print("ok", name, img.size, "frame", fw, fh, "sole_y", info["sole_y" + key])
    info["measure"] = meta
    for d in OUTS:
        (d / "badger.json").write_text(json.dumps(info, indent=1))
    for m in meta:
        print(f'{m["name"]:7s} h {m["height_ai"]}  Kontakt {m["contact_ai"]}  Nase {m["nose_x_ai"]}  cx {m["cx_ai"]}')


if __name__ == "__main__":
    main()
