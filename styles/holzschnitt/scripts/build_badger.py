#!/usr/bin/env python3
"""Farbauszug und Bogen des Dachs-Kuriers aus dem KI-Laufbogen.

    .venv/bin/python styles/holzschnitt/scripts/build_badger.py

Eingang: assets/raw/walk.png (gpt-image, 2x5 Figuren nach dem Blender-Layout assets/ref/walk_layout.png)
Ausgang (assets/ und demo/art/):
  badger.png   Bogen in einer Reihe: walk_0 … walk_7, stand, turn, blink (turn mit geschlossenem Auge).
               RGB = Platten (R Schwarz, G Petrol, B Zinnober), A = Figur samt ausgespartem Papierrand.
  badger.json  Bildgröße, Fußlinie und Bezugspunkt je Bild, gemessene Sohlen in Bogenpixeln

Ablauf je Zelle: größte Alphafläche der Zelle (Alpha >= 128), Farbauszug wie beim Hintergrund (CIELAB, nächste
Druckfarbe, 3x3-Mehrheitsfilter), Papierrand: Alpha um 6 px (KI) erweitert und dort Papier (keine Farbe) - wie
der stehengelassene helle Rand, den Holzschneider um Figuren vor dunklem Grund schneiden. Ausrichtung: x bleibt in
Zellkoordinaten (Kopf steht in allen Zellen auf ±5 px gleich), y an der Sohle (unterste Alphazeile). Verkleinern
mit Flächenmittel, Farbe vorher mit Alpha multipliziert.
"""
import json, pathlib
import numpy as np
from PIL import Image

import inklib

ROOT = pathlib.Path(__file__).resolve().parents[1]
OUTS = [ROOT / "assets", ROOT / "demo/art"]
SCALE = 0.47            # 432 px Figur -> 203 px
CELL_W = 307
TOP, BOT = 470, 6       # Rahmen über / unter der Sohle (KI-Pixel)
RIM = 6                 # Papierrand in KI-Pixeln

# Augen (Zellkoordinaten, von Hand an 3-fach vergrößerten Köpfen abgelesen): Das Modell hat das Auge als schwarzen
# Punkt mit dünnem hellem Ring in den schwarzen Augenstreif gesetzt; nach Farbauszug und Verkleinern verschwindet
# es. Darum wird es wie im Holzschnitt ausgeschnitten: Papierscheibe mit schwarzer Pupille (zur Nase versetzt).
EYES = {"walk_0": [(215, 117, 10)], "walk_1": [(222, 117, 10)], "walk_2": [(218, 115, 10)], "walk_3": [(213, 117, 10)],
        "walk_4": [(215, 120, 10)], "walk_5": [(212, 92, 10)], "walk_6": [(215, 92, 10)], "walk_7": [(215, 95, 10)],
        "stand": [(215, 93, 10)], "turn": [(165, 91, 9), (214, 89, 10)]}

SEP = [
    ("black",   (14, 17, 16),    (1, 0, 0)),
    ("black2",  (26, 41, 41),    (1, 0, 0)),
    ("cream",   (249, 227, 188), (0, 0, 0)),
    ("cream2",  (239, 202, 145), (0, 0, 0)),
    ("tan",     (174, 152, 117), (0, 0, 0)),
    ("teal",    (25, 69, 75),    (0, 1, 0)),
    ("red",     (188, 56, 12),   (0, 0, 1)),
    ("brown",   (103, 37, 15),   (0, 0, 1)),   # Tasche, Schalschatten: Zinnober
]


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


def main():
    im = np.asarray(Image.open(ROOT / "assets/raw/walk.png").convert("RGBA"))
    lay = json.loads((ROOT / "assets/ref/layout.json").read_text())
    frames, meta = [], []
    for c in lay["cells"]:
        x, y, w, h = c["x"], c["y"], c["w"], c["h"]
        sub = im[y:y + h, x:x + w]
        a = largest_component(sub[..., 3] >= 128)
        # Löcher in der Figur (Papier zwischen Arm und Körper bleibt Figur, wenn es innen liegt) - Alpha der KI reicht
        ys, xs = np.nonzero(a)
        sole = int(ys.max())
        idx = inklib.majority3(inklib.classify(sub[..., :3], SEP), len(SEP))
        pl = inklib.plates_from_index(idx, SEP) * a[..., None]
        yy, xx = np.mgrid[0:h, 0:w]
        closed = pl.copy()
        for ex, ey, er in EYES[c["name"]]:
            d2 = (xx - ex) ** 2 + (yy - ey) ** 2
            pl[d2 <= er * er] = (0, 0, 0)                                    # Papierscheibe
            pl[(xx - ex - 2) ** 2 + (yy - ey) ** 2 <= (er * 0.55) ** 2] = (1, 0, 0)   # Pupille
            # geschlossen: Lidstrich als Papierbogen (untere Hälfte eines Rings)
            ring = (d2 <= (er - 1) ** 2) & (d2 >= (er - 6) ** 2) & (yy >= ey)
            closed[ring] = (0, 0, 0)
        rim = dilate(a, RIM) & ~a
        alpha = (a | rim).astype(np.float32)
        # Rahmen: Zellbreite, TOP über bis BOT unter der Sohle
        y0 = sole - TOP
        canvas_p = np.zeros((TOP + BOT, w, 3), np.float32)
        canvas_a = np.zeros((TOP + BOT, w), np.float32)
        sy0, sy1 = max(0, y0), min(h, sole + BOT)
        canvas_p[sy0 - y0:sy1 - y0] = pl[sy0:sy1]
        canvas_a[sy0 - y0:sy1 - y0] = alpha[sy0:sy1]
        frames.append((canvas_p, canvas_a))
        if c["name"] == "turn":
            canvas_c = np.zeros_like(canvas_p)
            canvas_c[sy0 - y0:sy1 - y0] = closed[sy0:sy1]
            blink = (canvas_c, canvas_a.copy())
        # Sohlen (unterste 3 Zeilen) in Zellkoordinaten
        bot = a[sole - 2:sole + 1]
        cols = np.nonzero(bot.any(0))[0]
        gaps = np.nonzero(np.diff(cols) > 2)[0]
        contact = [(int(q[0]), int(q[-1])) for q in np.split(cols, gaps + 1)]
        top = a[ys.min():ys.min() + (sole - ys.min()) // 4]
        meta.append({"name": c["name"], "sole_ai": sole + y, "height_ai": int(sole - ys.min() + 1),
                     "contact_ai": contact, "head_x_ai": [int(np.nonzero(top.any(0))[0].min()),
                                                          int(np.nonzero(top.any(0))[0].max())],
                     "cx_ai": round(float(xs.mean()), 1)})

    # Blinzeln: Dreiviertelbild mit geschlossenen Augen (Lidstrich statt Auge)
    frames.append(blink)
    meta.append(dict(meta[-1], name="blink"))

    fw = round(CELL_W * SCALE)
    fh = round((TOP + BOT) * SCALE)
    sheet = np.zeros((fh, fw * len(frames), 4), np.float32)
    for i, (p, a) in enumerate(frames):
        pa = np.concatenate([p * a[..., None], a[..., None]], -1)
        chans = [np.asarray(Image.fromarray(pa[..., k], "F").resize((fw, fh), Image.BOX)) for k in range(4)]
        al = chans[3]
        col = np.stack(chans[:3], -1) / np.maximum(al[..., None], 1e-4)
        col[al < 1e-3] = 0
        sheet[:, i * fw:(i + 1) * fw, :3] = col
        sheet[:, i * fw:(i + 1) * fw, 3] = al
    img = Image.fromarray(np.clip(sheet * 255 + 0.5, 0, 255).astype(np.uint8), "RGBA")
    for d in OUTS:
        d.mkdir(parents=True, exist_ok=True)
        img.save(d / "badger.png")
    info = {"frame_w": fw, "frame_h": fh, "frames": len(frames), "scale": SCALE,
            "sole_y": round(TOP * SCALE, 2), "names": [m["name"] for m in meta], "measure": meta}
    for d in OUTS:
        (d / "badger.json").write_text(json.dumps(info, indent=1))
    print("ok badger.png", img.size, "frame", fw, fh, "sole_y", info["sole_y"])
    for m in meta:
        print(m["name"], m["height_ai"], m["contact_ai"], m["cx_ai"])


if __name__ == "__main__":
    main()
