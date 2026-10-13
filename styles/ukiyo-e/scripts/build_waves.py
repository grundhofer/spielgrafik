#!/usr/bin/env python3
"""Zerlegt den KI-Wellenbogen in einzelne Wellen-Sprites für die Vordergrund-Brandung.

    .venv/bin/python styles/ukiyo-e/scripts/build_waves.py

Eingang: assets/raw/waves.png (gpt-image, 2 Reihen: drei hohe Brecher, drei flache Wellenzüge, echter Alphakanal)
Ausgang (assets/ und demo/art/):
  wave_0.png … wave_5.png  je Welle ein RGBA-Sprite, verkleinert (Lanczos, vormultipliziertes Alpha)
  wave_0_close.png …       dieselben Wellen 1,6-mal so groß für die Nahaufnahme (direkt aus der KI-Vorlage)
  waves.json               Größe je Sprite und Lage der geraden Unterkante (für die Anordnung in der Demo)

Zuordnung: Zusammenhangsflächen (Alpha >= 128); große Flächen (> 20000 px) sind Wellenkörper, kleine (Gischttropfen)
gehören zum Körper, dessen Hüllrechteck am nächsten liegt. Der weiche Alpharand bleibt in einem 2-px-Saum erhalten.
Seitenkanten: Das Modell hat den Wellenkörper unten links und rechts senkrecht abgeschnitten (mit Kontur).
Nebeneinander gesetzt ergab das sichtbare senkrechte Nähte. Darum wird bei jeder Welle auf beiden Seiten der untere
Körper (ab 20 KI-Zeilen über der Zeile, ab der er > 80 % der Breite deckt) über 40 KI-px ausgeblendet (je Zeile vom
äußersten Pixel aus, oben über 30 Zeilen weich eingeblendet); so taucht jede Welle aus der dahinterliegenden auf.
"""
import json, pathlib
import numpy as np
from PIL import Image

ROOT = pathlib.Path(__file__).resolve().parents[1]
OUTS = [ROOT / "assets", ROOT / "demo/art"]
SCALE = {0: 0.40, 1: 0.40, 2: 0.40, 3: 0.40, 4: 0.40, 5: 0.40}
ZOOM = 1.6              # Nahaufnahme (scene.json "closeup"): zweite Fassung jeder Welle in 1,6-facher Größe


def label(b):
    h, w = b.shape
    lab = np.zeros((h, w), np.int32)
    cur = 0
    ys, xs = np.nonzero(b)
    for y0, x0 in zip(ys, xs):
        if lab[y0, x0]:
            continue
        cur += 1
        stack = [(y0, x0)]
        lab[y0, x0] = cur
        while stack:
            y, x = stack.pop()
            for yy, xx in ((y + 1, x), (y - 1, x), (y, x + 1), (y, x - 1)):
                if 0 <= yy < h and 0 <= xx < w and b[yy, xx] and not lab[yy, xx]:
                    lab[yy, xx] = cur
                    stack.append((yy, xx))
    return lab, cur


def dilate(b, r):
    out = b.copy()
    for dy in range(-r, r + 1):
        for dx in range(-r, r + 1):
            if dx * dx + dy * dy <= r * r:
                out |= np.roll(np.roll(b, dy, 0), dx, 1)
    return out


def side_fade(a, from_rows, F=40.0, ramp_in=30):
    """Faktor 0..1: blendet beide Seitenkanten des Wellenkörpers a (bool, ohne abgelöste Tropfen) aus, für jede Welle
    und jede Seite (erzwungen). Je Zeile wird vom äußersten Körperpixel nach innen über F KI-px ausgeblendet
    (Smoothstep), ab from_rows = (links, rechts); darüber über ramp_in Zeilen weich eingeblendet. Die erste Fassung
    erkannte senkrechte Kanten nur, wenn die Kante über >= 8 Zeilen auf 3 px gerade war; an wave_2 (rechts), wave_4
    (links) und wave_5 (beidseitig) griff das nicht, weil Gischtfinger und Konturknicke die Kante unterbrachen."""
    h, w = a.shape
    out = np.ones((h, w), np.float32)
    xx = np.arange(w, dtype=np.float32)[None, :]
    yy = np.arange(h, dtype=np.float32)[:, None]
    has = a.any(1)
    left = np.where(has, np.argmax(a, 1), 0).astype(np.float32)[:, None]
    right = np.where(has, w - 1 - np.argmax(a[:, ::-1], 1), w - 1).astype(np.float32)[:, None]
    for d, fr in ((xx - left, from_rows[0]), (right - xx, from_rows[1])):
        wgt = np.clip((yy - (fr - ramp_in)) / ramp_in, 0, 1)
        r = np.clip(d / F, 0, 1)
        r = r * r * (3 - 2 * r)
        out *= 1 - wgt * (1 - r)
    return out


def fade_rows(a, full_row):
    """Erste Zeile je Seite, ab der ausgeblendet wird: wo die Kante ihre unterste Lage bis auf 8 KI-px erreicht (der
    senkrechte Schnitt beginnt), spätestens 20 Zeilen über der Zeile mit voller Breite."""
    rows = np.nonzero(a.any(1))[0]
    bottom = rows.max()
    res = []
    for side in ("L", "R"):
        e = [np.nonzero(a[y])[0].min() if side == "L" else np.nonzero(a[y])[0].max() for y in range(bottom + 1)
             if a[y].any()]
        ys = [y for y in range(bottom + 1) if a[y].any()]
        eb = e[-1]
        y_first = bottom
        for y, x in zip(reversed(ys), reversed(e)):
            if (x <= eb + 8) if side == "L" else (x >= eb - 8):
                y_first = y
            else:
                break
        res.append(min(y_first, full_row - 20))
    return res


def downscale(rgba, size):
    f = rgba.astype(np.float32) / 255.0
    a = f[..., 3:4]
    pm = np.concatenate([f[..., :3] * a, a], -1)
    ch = [np.asarray(Image.fromarray(pm[..., k], "F").resize(size, Image.LANCZOS)) for k in range(4)]
    al = np.clip(ch[3], 0, 1)
    col = np.stack(ch[:3], -1) / np.maximum(al[..., None], 1e-4)
    col[al < 1e-3] = 0
    return (np.concatenate([np.clip(col, 0, 1), al[..., None]], -1) * 255 + 0.5).astype(np.uint8)


def main():
    src = np.asarray(Image.open(ROOT / "assets/raw/waves.png").convert("RGBA"))
    core = src[..., 3] >= 128
    lab, n = label(core)
    sizes = np.bincount(lab.ravel())
    big = [i for i in range(1, n + 1) if sizes[i] > 20000]
    boxes = {}
    for i in big:
        ys, xs = np.nonzero(lab == i)
        boxes[i] = [xs.min(), ys.min(), xs.max(), ys.max()]
    owner = {i: i for i in big}
    for i in range(1, n + 1):
        if i in owner or sizes[i] == 0:
            continue
        ys, xs = np.nonzero(lab == i)
        cx, cy = xs.mean(), ys.mean()
        best = min(big, key=lambda k: max(boxes[k][0] - cx, 0, cx - boxes[k][2]) ** 2 +
                   max(boxes[k][1] - cy, 0, cy - boxes[k][3]) ** 2)
        owner[i] = best
    # Reihenfolge: oben links nach unten rechts
    order = sorted(big, key=lambda k: (boxes[k][1] > 600, boxes[k][0]))
    info = []
    for j, k in enumerate(order):
        m = np.isin(lab, [i for i, o in owner.items() if o == k])
        keep = dilate(m, 2)
        ys, xs = np.nonzero(m)
        x0, y0, x1, y1 = xs.min(), ys.min(), xs.max() + 1, ys.max() + 1
        rgba = src[y0:y1, x0:x1].copy()
        rgba[..., 3] = (rgba[..., 3] * keep[y0:y1, x0:x1]).astype(np.uint8)
        # gerade Unterkante: unterste Zeile, die über mehr als 80 % der Körperbreite deckt
        body = (lab[y0:y1, x0:x1] == k)
        bw = body.any(0).sum()
        full = np.nonzero(body.sum(1) > 0.8 * bw)[0]
        # Ausblenden nur am Wellenkörper (abgelöste Tropfen bleiben deckend), beide Seiten erzwungen
        full_row = int(full.min()) if len(full) else (y1 - y0) // 2
        from_rows = fade_rows(body, full_row)
        fade = side_fade(body, from_rows)
        fade = np.where(dilate(body, 3), fade, 1.0)
        rgba[..., 3] = (rgba[..., 3] * fade).astype(np.uint8)
        from_row = min(from_rows)
        s = SCALE[j]
        size = (max(1, round((x1 - x0) * s)), max(1, round((y1 - y0) * s)))
        out = downscale(rgba, size)
        img = Image.fromarray(out, "RGBA")
        size_c = (round(size[0] * ZOOM), round(size[1] * ZOOM))
        img_c = Image.fromarray(downscale(rgba, size_c), "RGBA")
        for d in OUTS:
            d.mkdir(parents=True, exist_ok=True)
            img.save(d / f"wave_{j}.png")
            img_c.save(d / f"wave_{j}_close.png")
        # Prüfung: Deckung am äußersten Pixel je Zeile im ausgeblendeten Bereich (soll klein sein)
        al = out[..., 3].astype(int)
        bs = np.asarray(Image.fromarray(body.astype(np.uint8) * 255).resize(size, Image.BILINEAR)) > 100
        el, er = [], []
        for side, fr, acc in (("L", from_rows[0], el), ("R", from_rows[1], er)):
            for y in range(int(np.ceil(fr * s)), size[1]):
                xs_ = np.nonzero(bs[y])[0]
                if len(xs_):
                    x_ = xs_.min() if side == "L" else xs_.max()
                    acc.append(int(al[y, x_]))
        edge_l, edge_r = max(el), max(er)
        print(f"   ausgeblendet ab KI-Zeile links {from_rows[0]}, rechts {from_rows[1]}; größte Deckung am äußersten Körperpixel darunter: links {edge_l}, rechts {edge_r}")
        # oberste Zeile des Wellenkörpers je Spalte (für die Anordnung): niedrigste Kammhöhe
        info.append({"file": f"wave_{j}.png", "src_box": [int(x0), int(y0), int(x1), int(y1)], "scale": s,
                     "size": list(size), "size_close": list(size_c), "full_width_from_y": round(float(full.min()) * s, 1) if len(full) else None})
        print(f"wave_{j}: Quelle {x1 - x0}x{y1 - y0} -> {size}, volle Breite ab y {info[-1]['full_width_from_y']}")
    for d in OUTS:
        (d / "waves.json").write_text(json.dumps(info, indent=1))


if __name__ == "__main__":
    main()
