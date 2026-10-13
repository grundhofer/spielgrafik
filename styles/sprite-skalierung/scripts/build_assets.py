#!/usr/bin/env python3
"""Baut aus den KI-Rohbildern die Sprites für die Demo.

    .venv/bin/python styles/sprite-skalierung/scripts/build_assets.py

Je Objekt: aus dem Blatt ausschneiden (Zusammenhangskomponenten), auf eine feste Speicherdichte bringen
(Requisiten 40 Pixel je Meter, wie vorgezeichnete Sprites in Maximalgröße), je Zielpixel die häufigste
vorquantisierte Farbe im Zellinneren (keine Mischfarben, 1-Bit-Alpha), danach höchstens 15 Farben + transparent
je Sprite (4 Bit je Pixel) mit Farben aus 15-Bit-RGB. Schreibt demo/art/*.png, demo/data/sprites.json und
Übersichtsblätter nach assets/.
"""
import json, pathlib, sys

import numpy as np
from PIL import Image

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import sslib  # noqa: E402

SD = pathlib.Path(__file__).resolve().parents[1]
RAW, ART, DATA, AS = SD / "assets/raw", SD / "demo/art", SD / "demo/data", SD / "assets"
PPM = 40.0  # Speicherdichte der Requisiten: Pixel je Meter in der größten (gespeicherten) Stufe
# Eigene Palettenfarben für Lichter (Palettenanimation in Godot: der Shader ersetzt genau diese Farbe)
KEY_LANTERN = (255, 214, 66)
KEY_WINDOW = (255, 206, 82)
KEY_LH = (255, 247, 156)


def with_key(g, mask, key, n=15, boost_mask=None):
    """Pixel unter mask bekommen die Schlüsselfarbe key, der Rest höchstens n-1 Farben (15-Bit-RGB)."""
    key = tuple(int(v) for v in sslib.snap5(np.array(key)))
    rest = g.copy()
    rest[mask, 3] = 0
    q, pal = sslib.reduce_palette(rest, n - 1, boost_mask=boost_mask)
    q[mask, :3] = key
    q[mask, 3] = 255
    return q, len(pal) + 1, key, int(mask.sum())


def crop(im, box, pad=2):
    x0, y0, x1, y1 = box[:4]
    return im[max(0, y0 - pad):y1 + pad, max(0, x0 - pad):x1 + pad]


def grid(im_crop, cell, anchor="bottom"):
    """Auf ein Raster mit Zellgröße cell bringen; Raster an Unterkante und Mitte des Objekts verankert."""
    a = im_crop[..., 3] > 127
    ys, xs = np.nonzero(a)
    x0, x1, y0, y1 = xs.min(), xs.max() + 1, ys.min(), ys.max() + 1
    cx = (x0 + x1) / 2
    phx = cx - cell * np.ceil((cx - x0) / cell)
    phy = y1 - cell * np.ceil((y1 - y0) / cell)
    return sslib.to_grid(im_crop, (x0, y0, x1, y1), cell, cell, phx, phy)


def trim(img):
    a = img[..., 3] > 0
    ys, xs = np.nonzero(a)
    return img[ys.min():ys.max() + 1, xs.min():xs.max() + 1]


def yellow_centroid(img, region=None):
    r, g, b, a = [img[..., i].astype(float) for i in range(4)]
    m = (a > 0) & (r > 220) & (g > 140) & (b < 70)
    if region is not None:
        x0, y0, x1, y1 = region
        mm = np.zeros_like(m)
        mm[y0:y1, x0:x1] = True
        m &= mm
    ys, xs = np.nonzero(m)
    if not len(xs):
        return None
    return [round(float(xs.mean()), 1), round(float(ys.mean()), 1), int(len(xs))]


def main():
    ART.mkdir(parents=True, exist_ok=True)
    DATA.mkdir(parents=True, exist_ok=True)
    meta = {}
    out = {}

    # --- Dachs: 3 Laufbilder von hinten, gemeinsames Raster und eine gemeinsame Palette ---
    im = sslib.load_rgba(RAW / "badger_run.png")
    boxes = sorted(sslib.components(im[..., 3], min_px=5000, gap=6), key=lambda b: b[0])
    assert len(boxes) == 3, boxes
    H_TARGET = 64
    hmax = max(b[3] - b[1] for b in boxes)
    cell = hmax / H_TARGET
    frames = [trim(grid(crop(im, b), cell)) for b in boxes]
    # gemeinsame Palette
    W = max(f.shape[1] for f in frames)
    Hh = max(f.shape[0] for f in frames)
    joint = np.zeros((Hh, W * 3, 4), dtype=np.int32)
    for i, f in enumerate(frames):
        joint[Hh - f.shape[0]:, i * W:i * W + f.shape[1]] = f
    joint, pal = sslib.reduce_palette(joint, 15)
    frames = [trim(joint[:, i * W:(i + 1) * W]) for i in range(3)]
    out["badger"] = frames
    # Ausrichtung: Kopfmitte (oberes Viertel) und Fußzeile (unterste Zeile) je Bild
    head = []
    for f in frames:
        al = f[..., 3] > 0
        q = max(1, f.shape[0] // 4)
        ys, xs = np.nonzero(al[:q])
        head.append(round(float(xs.mean()), 2))
    meta["badger"] = {"cell_src_px": round(cell, 2), "colors": int(len(pal)),
                      "frames": [list(f.shape[1::-1]) for f in frames], "head_cx": head}

    # --- Requisiten ---
    im = sslib.load_rgba(RAW / "props.png")
    boxes = sslib.components(im[..., 3], min_px=5000, gap=6)
    boxes = sorted(boxes, key=lambda b: (b[1] > 510, b[0]))  # Reihe, dann x
    names = ["barrel", "crates", "bollard", "post", "rope", "parcel"]
    # Größe in Metern (Höhe, außer Taurolle und Paket: Breite)
    size_m = {"barrel": ("h", 0.95), "crates": ("h", 1.35), "bollard": ("h", 0.6), "post": ("h", 2.8),
              "rope": ("w", 0.95), "parcel": ("w", 0.55)}
    for n, b in zip(names, boxes):
        ax, m = size_m[n]
        ext = (b[3] - b[1]) if ax == "h" else (b[2] - b[0])
        c = ext / (m * PPM)
        g = trim(grid(crop(im, b), c))
        if n == "post":
            hh, ww = g.shape[:2]
            yy, xx = np.mgrid[:hh, :ww]
            m = ((g[..., 0] > 200) & (g[..., 1] > 120) & (g[..., 2] < 70) & (xx > ww * 0.45)
                 & (yy > hh * 0.3) & (yy < hh * 0.62))
            g, ncol, key, cnt = with_key(g, m, KEY_LANTERN)
            meta["keys"] = {"lantern": list(key)}
            meta["lantern_px"] = cnt
        else:
            g, pal = sslib.reduce_palette(g, 15)
            ncol = len(pal)
        out[n] = g
        meta[n] = {"cell_src_px": round(c, 2), "colors": int(ncol), "size": list(g.shape[1::-1]), "ppm": PPM}

    # --- Boote ---
    im = sslib.load_rgba(RAW / "boats.png")
    boxes = sorted(sslib.components(im[..., 3], min_px=5000, gap=6), key=lambda b: b[0])
    for n, b, hm in zip(["boat_a", "boat_b"], boxes, [4.6, 5.0]):
        c = (b[3] - b[1]) / (hm * PPM)
        g = trim(grid(crop(im, b), c))
        g, pal = sslib.reduce_palette(g, 15)
        out[n] = g
        meta[n] = {"cell_src_px": round(c, 2), "colors": int(len(pal)), "size": list(g.shape[1::-1]), "ppm": PPM}

    # --- Häuschen ---
    im = sslib.load_rgba(RAW / "cottage.png")
    b = sslib.components(im[..., 3], min_px=5000, gap=6)[0]
    c = (b[3] - b[1]) / (5.6 * PPM)
    g = trim(grid(crop(im, b), c))
    hh, ww = g.shape[:2]
    yy, xx = np.mgrid[:hh, :ww]
    glass = (g[..., 0] > 220) & (g[..., 1] > 170) & (g[..., 2] < 80) & (xx > ww * 0.6) & (yy > hh * 0.45)
    g, ncol, key, cnt = with_key(g, glass, KEY_WINDOW)
    meta["keys"]["window"] = list(key)
    meta["window_px"] = cnt
    out["cottage"] = g
    meta["cottage"] = {"cell_src_px": round(c, 2), "colors": int(ncol), "size": list(g.shape[1::-1]), "ppm": PPM}

    # --- Horizont: Inseln links, Felsnase mit Leuchtturm rechts (Lücke bei x ≈ 815) ---
    im = sslib.load_rgba(RAW / "horizon.png")
    HC = 4.8
    parts = {"hz_islands": im[:, :816].copy(), "hz_headland": im[:, 816:].copy()}
    hz = {}
    for n, sub in parts.items():
        b = sslib.components(sub[..., 3], min_px=50, gap=12)
        x0 = min(q[0] for q in b); y0 = min(q[1] for q in b)
        x1 = max(q[2] for q in b); y1 = max(q[3] for q in b)
        hz[n] = trim(grid(crop(sub, (x0, y0, x1, y1)), HC))
    # je Teil eine eigene Palette (15 Farben); beim Leuchtturm zählen die oberen 45 % der Zeilen
    # (Turm, Haus, Bäume) 40-fach, sonst gehen rotes Band und Lampe in den Felsfarben unter
    for n, v in hz.items():
        boost = np.zeros(v.shape[:2], bool)
        if n == "hz_headland":
            boost[:int(v.shape[0] * 0.45)] = True
            lamp = np.zeros_like(boost)
            lamp[:int(v.shape[0] * 0.3)] = True
            lamp &= (v[..., 0] > 200) & (v[..., 1] > 150) & (v[..., 2] < 110) & (v[..., 3] > 0)
            q, ncol, key, cnt = with_key(v, lamp, KEY_LH, boost_mask=boost)
            meta["keys"]["lighthouse"] = list(key)
            meta["lighthouse_px"] = cnt
        else:
            q, pal = sslib.reduce_palette(v, 15)
            ncol = len(pal)
        out[n] = trim(q)
        meta[n] = {"cell_src_px": HC, "colors": int(ncol), "size": list(out[n].shape[1::-1])}

    # --- Wolken: sechs Bänder ---
    im = sslib.load_rgba(RAW / "clouds.png")
    boxes = sorted(sslib.components(im[..., 3], min_px=5000, gap=6), key=lambda b: b[1])
    CC = 6.0
    cl = [trim(grid(crop(im, b), CC)) for b in boxes]
    Hh = max(v.shape[0] for v in cl)
    Wt = sum(v.shape[1] for v in cl)
    joint = np.zeros((Hh, Wt, 4), dtype=np.int32)
    x = 0
    for v in cl:
        joint[Hh - v.shape[0]:, x:x + v.shape[1]] = v
        x += v.shape[1]
    joint, pal = sslib.reduce_palette(joint, 15)
    x = 0
    for i, v in enumerate(cl):
        n = f"cloud_{i}"
        out[n] = trim(joint[:, x:x + v.shape[1]])
        x += v.shape[1]
        meta[n] = {"cell_src_px": CC, "colors": int(len(pal)), "size": list(out[n].shape[1::-1])}

    # --- Sonderpunkte ---
    pts = {}
    def key_centroid(img, key):
        m = (img[..., 0] == key[0]) & (img[..., 1] == key[1]) & (img[..., 2] == key[2]) & (img[..., 3] > 0)
        ys, xs = np.nonzero(m)
        return [round(float(xs.mean()), 1), round(float(ys.mean()), 1), int(len(xs))] if len(xs) else None
    pts["post_lamp"] = key_centroid(out["post"], meta["keys"]["lantern"])
    c = out["cottage"]
    pts["cottage_window"] = key_centroid(c, meta["keys"]["window"])
    a = c[..., 3] > 0
    w = c.shape[1]
    cols = [x for x in range(int(w * 0.6), w) if a[:, x].any()]
    tops = {x: int(np.nonzero(a[:, x])[0].min()) for x in cols}
    ymin = min(tops.values())
    xs = [x for x, t in tops.items() if t <= ymin + 1]
    pts["cottage_chimney"] = [round(float(np.mean(xs)), 1), ymin]
    h = out["hz_headland"]
    pts["lighthouse_lamp"] = key_centroid(h, meta["keys"]["lighthouse"])
    meta["points"] = pts

    # --- schreiben (demo/art für Godot, Kopie in assets/sprites) ---
    SPR = AS / "sprites"
    SPR.mkdir(exist_ok=True)
    for n, img in out.items():
        for dst in (ART, SPR):
            if n == "badger":
                for i, f in enumerate(img):
                    sslib.save(f, dst / f"badger_{i}.png")
            else:
                sslib.save(img, dst / f"{n}.png")
    (DATA / "sprites.json").write_text(json.dumps(meta, indent=1))
    sheets(out)
    print(json.dumps(meta, indent=1))


def sheets(out):
    """Übersicht aller Sprites in Speichergröße (×2) auf dunklem und hellem Grund."""
    items = list(out["badger"]) + [out[k] for k in out if k != "badger"]
    pad = 6
    rows, row, wsum = [], [], 0
    for it in items:
        if wsum + it.shape[1] + pad > 640 and row:
            rows.append(row)
            row, wsum = [], 0
        row.append(it)
        wsum += it.shape[1] + pad
    rows.append(row)
    H = sum(max(i.shape[0] for i in r) + pad for r in rows) + pad
    W = max(sum(i.shape[1] + pad for i in r) for r in rows) + pad
    for name, bg in (("sprites_sheet_dark.png", (24, 20, 40)), ("sprites_sheet_light.png", (220, 220, 210))):
        sheet = Image.new("RGBA", (W, H), bg + (255,))
        y = pad
        for r in rows:
            x = pad
            rh = max(i.shape[0] for i in r)
            for it in r:
                sheet.alpha_composite(Image.fromarray(it.astype(np.uint8), "RGBA"), (x, y + rh - it.shape[0]))
                x += it.shape[1] + pad
            y += rh + pad
        sheet = sheet.resize((W * 2, H * 2), Image.NEAREST)
        sheet.convert("RGB").save(AS / name)


if __name__ == "__main__":
    main()
