"""Renderbilder -> 256-Farben-Knotenbilder und eingebettete Bildfolgen (wie 8-Bit-CD-ROM-Spiele um 1995).

    .venv/bin/python styles/vorgerendert-diashow/scripts/bake.py

Liest assets/raw/render/<knoten>/loop_NNNN.png (Umgebungsschleife, 2 s, 15 Bilder/s) und
assets/raw/render/steg/badger_NNNN.png (Dachs-Clip) und schreibt nach assets/nodes/ und demo/nodes/:

  palette.png            256×1, gemeinsame Palette aller Knoten (Bilder, Clips und Oberfläche)
  text_palette.png       12×1, die Farben der Textzeile (Schwarz, Textrampe, Gold); Godot rastet das Band unter
                         dem Bild nur auf diese Farben ein
  <knoten>/base.png      Standbild 544×332, 8 Bit mit Palette, Fehlerdiffusion (Floyd-Steinberg)
  <knoten>/clip_<n>.png  Bildfolge eines rechteckigen Ausschnitts (Raster), wie ein eingebetteter Videoausschnitt
  <knoten>/meta.json     Rechtecke, Bildzahl, Spalten, Bildrate, Schleifen

Ablauf:
  1. Leuchtfeuer-Stern (Kreuzfilter-Glanz der Zeit) in linearem Licht auf die Steg-Bilder addieren, Stärke aus
     derselben Blitzkurve wie im Render.
  2. Palette: k-Means (in einer wahrnehmungsnahen Lab-Näherung) über Stichproben aller Bilder, Dachs-Bereich
     stärker gewichtet; dazu feste Farben für Rahmen, Schrift und Mauszeiger.
  3. Jedes Bild mit Floyd-Steinberg auf die Palette (Pillow).
  4. Bewegte Bereiche: Pixel, die in der Quelle mehr als THR von Bild 0 abweichen, kommen aus dem Bild selbst,
     alle anderen aus dem Standbild (sonst „kocht“ das Fehlerdiffusionsmuster im ganzen Bild). In weichen
     Rechtecken (nodes.json → soft_rects, z. B. der Rauch) genügt eine Abweichung von THR_SOFT, ohne Opening:
     Dort zählen auch die halbdurchsichtigen Ränder, sonst schneidet die Schwelle die weiche Bewegung weg.
     Zusammenhängende bewegte Bereiche -> Rechtecke -> eine Bildfolge je Rechteck.
  5. Dachs-Clip: Pixel, die der Dachs verändert (Figur, Schatten, Spiegelung), aus dem Dachs-Bild, alle anderen
     aus der Umgebungsschleife derselben Phase. Damit passt der Clip nahtlos über die Wasser-Bildfolge.
Deterministisch: feste Seeds, gleiche Eingaben ergeben bitgleiche Ausgaben.
"""
import json
import math
import pathlib
import shutil

import numpy as np
from PIL import Image

STYLE = pathlib.Path(__file__).resolve().parent.parent
RAW = STYLE / "assets" / "raw" / "render"
OUT = STYLE / "assets" / "nodes"
DEMO_OUT = STYLE / "demo" / "nodes"
DATA = json.loads((STYLE / "demo" / "data" / "nodes.json").read_text())
W, H = DATA["image_size"]
LOOP_N = int(round(DATA["loop_s"] * DATA["fps"]))
THR = 3          # 8-Bit-Abweichung, ab der ein Pixel als bewegt gilt
THR_SOFT = 1     # dasselbe in weichen Rechtecken (Rauch), ohne Opening
SEED = 1995

# feste Farben (sRGB): Rahmen, Schrift, Mauszeiger. Die Schrift wird in Godot geglättet und danach auf die
# Palette eingerastet; die Rampe sorgt dafür, dass die Kantenpixel neutral bleiben.
UI_COLORS = [
    "000000", "FFFFFF",
    # Textrampe Schwarz -> Pergament (Fließtext)
    "1E1B16", "3B362C", "5C5444", "80755F", "A79A7E", "CDBF9F", "EADCBA",
    # Hervorhebung Gold
    "4A3A12", "8C6C22", "C99A34", "F2C85A",
    # Zeiger: Grautöne
    "B8B8B8", "6E6E6E",
]
# Textband: nur Schwarz, Textrampe und Gold (ohne Weiß und die Zeigergrautöne, sonst bekämen die warmen Schriftkanten
# neutrale Grausäume)
TEXT_COLORS = UI_COLORS[:1] + UI_COLORS[2:13]


# ---------------------------------------------------------------------------------------------
def load(p):
    return np.asarray(Image.open(p).convert("RGB"), dtype=np.uint8)


def srgb_to_lin(x):
    x = x / 255.0
    return np.where(x <= 0.04045, x / 12.92, ((x + 0.055) / 1.055) ** 2.4)


def lin_to_srgb(x):
    x = np.clip(x, 0, 1)
    return np.where(x <= 0.0031308, x * 12.92, 1.055 * x ** (1 / 2.4) - 0.055) * 255.0


def to_lab(rgb8):
    """OKLab aus sRGB (8 Bit), für die Palettensuche."""
    lin = srgb_to_lin(rgb8.astype(np.float64))
    m1 = np.array([[0.4122214708, 0.5363325363, 0.0514459929],
                   [0.2119034982, 0.6806995451, 0.1073969566],
                   [0.0883024619, 0.2817188376, 0.6299787005]])
    lms = np.cbrt(lin @ m1.T)
    m2 = np.array([[0.2104542553, 0.7936177850, -0.0040720468],
                   [1.9779984951, -2.4285922050, 0.4505937099],
                   [0.0259040371, 0.7827717662, -0.8086757660]])
    return lms @ m2.T


def from_lab(lab):
    m2i = np.linalg.inv(np.array([[0.2104542553, 0.7936177850, -0.0040720468],
                                  [1.9779984951, -2.4285922050, 0.4505937099],
                                  [0.0259040371, 0.7827717662, -0.8086757660]]))
    m1i = np.linalg.inv(np.array([[0.4122214708, 0.5363325363, 0.0514459929],
                                  [0.2119034982, 0.6806995451, 0.1073969566],
                                  [0.0883024619, 0.2817188376, 0.6299787005]]))
    lms = (lab @ m2i.T) ** 3
    return np.clip(np.round(lin_to_srgb(lms @ m1i.T)), 0, 255).astype(np.uint8)


# ---------------------------------------------------------------------------------------------
# Projektion (wie Blender: Kamera blickt von pos auf target, Bildwinkel horizontal)
def project(node, p):
    pos, tgt = np.array(node["pos"], float), np.array(node["target"], float)
    fwd = tgt - pos
    fwd /= np.linalg.norm(fwd)
    right = np.cross(fwd, [0, 1, 0])
    right /= np.linalg.norm(right)
    up = np.cross(right, fwd)
    v = np.array(p, float) - pos
    x, y, z = v @ right, v @ up, v @ fwd
    f = (W / 2) / math.tan(math.radians(node["hfov"]) / 2)
    return W / 2 + f * x / z - 0.5, H / 2 - f * y / z - 0.5


def lamp_flash(t):
    """Gleiche Kurve wie blender/render_nodes.py: ein Blitz je 2-s-Schleife, Höhepunkt bei 0,4 s."""
    L = DATA["loop_s"]
    x = ((t - 0.4) / L + 0.5) % 1.0 - 0.5
    return math.exp(-(x * L / 0.12) ** 2)


def star_glare(img8, cx, cy, k):
    """Kreuzfilter-Stern + Hof um das Leuchtfeuer, linear addiert (k = 0..1)."""
    if k < 0.02:
        return img8
    lin = srgb_to_lin(img8.astype(np.float64))
    yy, xx = np.mgrid[0:H, 0:W].astype(np.float64)
    dx, dy = xx - cx, yy - cy
    r = np.hypot(dx, dy)
    col = np.array([1.0, 0.86, 0.6])
    halo = 0.9 * np.exp(-(r / 5.0) ** 2) + 0.25 * np.exp(-(r / 14.0) ** 2)
    streak = np.zeros_like(r)
    for ang in (0.0, 90.0, 45.0, 135.0):
        a = math.radians(ang)
        along = dx * math.cos(a) + dy * math.sin(a)
        across = -dx * math.sin(a) + dy * math.cos(a)
        length = 34.0 if ang in (0.0, 90.0) else 16.0
        streak += np.exp(-(across / 0.7) ** 2) * np.exp(-np.abs(along) / length) * (0.9 if ang in (0.0, 90.0) else 0.45)
    add = (halo + streak)[..., None] * col[None, None, :] * k
    return np.clip(np.round(lin_to_srgb(lin + add)), 0, 255).astype(np.uint8)


# ---------------------------------------------------------------------------------------------
def kmeans_palette(samples_lab, weights, k, iters, rng):
    # Start: gewichtete Zufallsauswahl, dann Lloyd-Iterationen
    idx = rng.choice(len(samples_lab), size=k, replace=False, p=weights / weights.sum())
    c = samples_lab[idx].copy()
    for _ in range(iters):
        lab_assign = np.empty(len(samples_lab), dtype=np.int32)
        for s in range(0, len(samples_lab), 50000):
            blk = samples_lab[s:s + 50000]
            d = ((blk[:, None, :] - c[None, :, :]) ** 2).sum(-1)
            lab_assign[s:s + 50000] = d.argmin(1)
        for j in range(k):
            m = lab_assign == j
            if m.any():
                w = weights[m][:, None]
                c[j] = (samples_lab[m] * w).sum(0) / w.sum()
            else:   # leeres Cluster neu setzen
                c[j] = samples_lab[rng.integers(len(samples_lab))]
    return c


def quantize(img8, pal_img):
    return np.asarray(Image.fromarray(img8, "RGB").quantize(palette=pal_img, dither=Image.Dither.FLOYDSTEINBERG))


def dilate(mask, r):
    out = mask.copy()
    for dy in range(-r, r + 1):
        for dx in range(-r, r + 1):
            sh = np.zeros_like(mask)
            ys, yd = (slice(dy, None), slice(0, -dy if dy else None)) if dy >= 0 else (slice(0, dy), slice(-dy, None))
            xs, xd = (slice(dx, None), slice(0, -dx if dx else None)) if dx >= 0 else (slice(0, dx), slice(-dx, None))
            sh[yd, xd] = mask[ys, xs]
            out |= sh
    return out


def opening(mask):
    """Vereinzelte Pixel (Rauschunterschiede einzelner Abtastungen) entfernen, Flächen behalten."""
    eroded = ~dilate(~mask, 1)
    return dilate(eroded, 1) & mask | (dilate(eroded, 2) & mask)


def components(mask):
    """Zusammenhängende Bereiche (8er-Nachbarschaft) -> Liste von Bounding-Boxes (x0, y0, x1, y1)."""
    lab = np.zeros(mask.shape, np.int32)
    boxes = []
    n = 0
    for y0, x0 in zip(*np.nonzero(mask)):
        if lab[y0, x0]:
            continue
        n += 1
        stack = [(y0, x0)]
        lab[y0, x0] = n
        bx = [x0, y0, x0, y0]
        while stack:
            y, x = stack.pop()
            bx[0], bx[1], bx[2], bx[3] = min(bx[0], x), min(bx[1], y), max(bx[2], x), max(bx[3], y)
            for yy in (y - 1, y, y + 1):
                for xx in (x - 1, x, x + 1):
                    if 0 <= yy < H and 0 <= xx < W and mask[yy, xx] and not lab[yy, xx]:
                        lab[yy, xx] = n
                        stack.append((yy, xx))
        boxes.append(bx)
    return boxes


def merge_boxes(boxes, gap):
    boxes = [list(b) for b in boxes]
    changed = True
    while changed:
        changed = False
        for i in range(len(boxes)):
            for j in range(i + 1, len(boxes)):
                a, b = boxes[i], boxes[j]
                if a[0] - gap <= b[2] and b[0] - gap <= a[2] and a[1] - gap <= b[3] and b[1] - gap <= a[3]:
                    boxes[i] = [min(a[0], b[0]), min(a[1], b[1]), max(a[2], b[2]), max(a[3], b[3])]
                    boxes.pop(j)
                    changed = True
                    break
            if changed:
                break
    return boxes


def sheet(frames, cols):
    h, w = frames[0].shape[:2]
    rows = math.ceil(len(frames) / cols)
    out = np.zeros((rows * h, cols * w), np.uint8)
    for i, f in enumerate(frames):
        out[(i // cols) * h:(i // cols + 1) * h, (i % cols) * w:(i % cols + 1) * w] = f
    return out


def save_p(arr, pal_flat, path):
    im = Image.fromarray(arr.astype(np.uint8), "P")
    im.putpalette(pal_flat)
    im.save(path, optimize=False)


# ---------------------------------------------------------------------------------------------
def main():
    rng = np.random.default_rng(SEED)
    nodes = DATA["nodes"]
    clip = DATA["badger_clip"]
    fps = DATA["fps"]

    # 1. Bilder laden, Stern aufs Leuchtfeuer
    frames = {}
    for name, node in nodes.items():
        frames[name] = [load(RAW / name / f"loop_{i:04d}.png") for i in range(LOOP_N)]
    bad = [load(RAW / clip["node"] / f"badger_{j:04d}.png") for j in range(clip["frames"])]
    lamp = [10.2, 12.58, -25.6]
    glare_info = {}
    for name, node in nodes.items():
        cx, cy = project(node, lamp)
        if not (0 <= cx < W and 0 <= cy < H):
            continue
        glare_info[name] = [round(cx, 1), round(cy, 1)]
        frames[name] = [star_glare(f, cx, cy, lamp_flash(i / fps)) for i, f in enumerate(frames[name])]
        if name == clip["node"]:
            bad = [star_glare(f, cx, cy, lamp_flash((j / fps) % DATA["loop_s"])) for j, f in enumerate(bad)]

    # 2. Palette
    smp, wts = [], []
    for name in nodes:
        for i in range(0, LOOP_N, 3):
            px = frames[name][i].reshape(-1, 3)
            sel = rng.choice(len(px), 9000, replace=False)
            smp.append(px[sel])
            wts.append(np.ones(len(sel)))
    # Dachs-Pixel (Abweichung vom Umgebungsbild) stärker gewichten, damit Figur und Schal eigene Farben bekommen
    for j in range(0, clip["frames"], 6):
        diff = np.abs(bad[j].astype(int) - frames[clip["node"]][j % LOOP_N].astype(int)).max(-1) > 8
        px = bad[j][diff]
        if len(px):
            sel = rng.choice(len(px), min(len(px), 2500), replace=False)
            smp.append(px[sel])
            wts.append(np.full(len(sel), 4.0))
    smp = np.concatenate(smp)
    wts = np.concatenate(wts)
    ui = np.array([[int(h[i:i + 2], 16) for i in (0, 2, 4)] for h in UI_COLORS], np.uint8)
    k = 256 - len(ui)
    centers = kmeans_palette(to_lab(smp), wts, k, 14, rng)
    pal = from_lab(centers)
    pal = np.concatenate([ui, pal])
    # doppelte Einträge (nach dem Runden) durch leicht versetzte ersetzen, damit die Palette 256 eindeutige Farben hat
    seen = set()
    for i in range(len(pal)):
        t = tuple(pal[i])
        while t in seen:
            t = (min(255, t[0] + 1), t[1], t[2])
        pal[i] = t
        seen.add(t)
    order = np.argsort(to_lab(pal)[:, 0], kind="stable")      # nach Helligkeit sortiert (übersichtlicher)
    pal = pal[order]
    pal_flat = pal.reshape(-1).tolist()
    pal_img = Image.new("P", (1, 1))
    pal_img.putpalette(pal_flat)

    for d in (OUT, DEMO_OUT):
        if d.exists():
            shutil.rmtree(d)
        d.mkdir(parents=True)
    Image.fromarray(pal.reshape(1, 256, 3), "RGB").save(OUT / "palette.png")
    tp = np.array([[int(h[i:i + 2], 16) for i in (0, 2, 4)] for h in TEXT_COLORS], np.uint8)
    assert all(tuple(c) in {tuple(x) for x in pal} for c in tp)
    Image.fromarray(tp.reshape(1, len(tp), 3), "RGB").save(OUT / "text_palette.png")

    meta_all = {"image_size": [W, H], "fps": fps, "loop_frames": LOOP_N, "palette": "palette.png",
                "glare": glare_info, "nodes": {}}
    stats = {}
    for name in nodes:
        src = frames[name]
        q = [quantize(f, pal_img) for f in src]
        base = q[0]
        soft = np.zeros((H, W), bool)
        for x, y, w, h in nodes[name].get("soft_rects", []):
            soft[y:y + h, x:x + w] = True
        moved = []
        for f in src:
            d = np.abs(f.astype(int) - src[0].astype(int)).max(-1)
            moved.append((opening(d > THR) & ~soft) | ((d > THR_SOFT) & soft))
        masks = [dilate(m, 1) for m in moved]
        comp = [np.where(m, qi, base) for m, qi in zip(masks, q)]
        union = np.zeros((H, W), bool)
        for m in masks:
            union |= m
        boxes = merge_boxes(components(dilate(union, 2)), 6)
        boxes = [b for b in boxes if (b[2] - b[0] + 1) * (b[3] - b[1] + 1) >= 16]
        nd = OUT / name
        nd.mkdir()
        save_p(base, pal_flat, nd / "base.png")
        clips = []
        for ci, (x0, y0, x1, y1) in enumerate(sorted(boxes, key=lambda b: (b[1], b[0]))):
            x0, y0 = max(0, x0), max(0, y0)
            x1, y1 = min(W - 1, x1), min(H - 1, y1)
            crops = [c[y0:y1 + 1, x0:x1 + 1] for c in comp]
            cols = max(1, min(LOOP_N, 2048 // (x1 - x0 + 1)))
            fn = f"clip_{ci}.png"
            save_p(sheet(crops, cols), pal_flat, nd / fn)
            clips.append({"file": fn, "rect": [int(x0), int(y0), int(x1 - x0 + 1), int(y1 - y0 + 1)],
                          "frames": LOOP_N, "cols": int(cols), "loop_from": 0, "kind": "ambient"})
        stats[name] = {"moving_share_mean": round(float(np.mean([m.mean() for m in masks[1:]])), 4),
                       "clip_rects": [c["rect"] for c in clips]}
        if name == clip["node"]:
            # Dachs-Clip: nur Pixel, die der Dachs verändert; sonst Umgebungs-Zusammensetzung derselben Phase
            qb = [quantize(f, pal_img) for f in bad]
            bm = [dilate(opening(np.abs(f.astype(int) - src[j % LOOP_N].astype(int)).max(-1) > THR), 1)
                  for j, f in enumerate(bad)]
            bcomp = [np.where(m, qb[j], comp[j % LOOP_N]) for j, m in enumerate(bm)]
            bu = np.zeros((H, W), bool)
            for m in bm:
                bu |= m
            ys, xs = np.nonzero(dilate(bu, 1))
            x0, x1, y0, y1 = xs.min(), xs.max(), ys.min(), ys.max()
            crops = [c[y0:y1 + 1, x0:x1 + 1] for c in bcomp]
            cols = max(1, min(len(crops), 2048 // (x1 - x0 + 1)))
            save_p(sheet(crops, cols), pal_flat, nd / "badger.png")
            clips.append({"file": "badger.png", "rect": [int(x0), int(y0), int(x1 - x0 + 1), int(y1 - y0 + 1)],
                          "frames": len(crops), "cols": int(cols), "loop_from": clip["loop_start"], "kind": "badger"})
            stats[name]["badger_rect"] = clips[-1]["rect"]
            stats[name]["badger_pixels_max"] = int(max(m.sum() for m in bm))
        meta = {"name": nodes[name]["name"], "base": "base.png", "clips": clips}
        (nd / "meta.json").write_text(json.dumps(meta, indent=1, ensure_ascii=False))
        meta_all["nodes"][name] = meta
        print(name, stats[name])

    (OUT / "nodes_meta.json").write_text(json.dumps(meta_all, indent=1, ensure_ascii=False))
    shutil.copytree(OUT, DEMO_OUT, dirs_exist_ok=True)
    (STYLE / "assets" / "bake_stats.json").write_text(json.dumps(stats, indent=1, ensure_ascii=False))
    print("Palette:", len({tuple(c) for c in pal}), "Farben")


if __name__ == "__main__":
    main()
