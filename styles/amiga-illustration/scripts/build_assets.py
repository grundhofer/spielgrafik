#!/usr/bin/env python3
"""Baut die 32-Farben-Illustration (Amiga OCS, 320x144) und die Dachs-BOBs in derselben Palette.

    .venv/bin/python styles/amiga-illustration/scripts/build_assets.py [--source auto|blender|ai] [--preview]
    .venv/bin/python styles/amiga-illustration/scripts/build_assets.py --picture closeup [--preview]
    ... --out DIR       Testlauf (z. B. mit fremdem Bild per --ai-image /abs/pfad.png), schreibt nur nach DIR

--source auto (Standard): KI-Bild assets/raw/bg.png, sobald es da ist, sonst das Blender-Rendering (raw/bg3d; seit
dem KI-Bild gelöscht, bei Bedarf mit blender/render_bg.py neu rendern).
--picture closeup: Nahaufnahme assets/raw/closeup.png mit eigenen 32 Registern (closeup_index.png,
closeup_palette.json); ohne Wasser im Bild werden die 5 Farbzyklus-Register zu festen Farben.
Erkannte Lagen und Maskengrößen: assets/picture_detect.json bzw. closeup_detect.json; Korrekturen in
assets/ai_layout.json bzw. closeup_layout.json (siehe load_ai.py). --preview schreibt *_preview_x3.png und
*_masks_x3.png nach assets/raw/.

Schritte:
  1. Vorlage laden (Blender-Rendering oder KI-Bild) und in linearem Licht auf 320x144 verkleinern; Masken für
     Wasser, Leuchtturmlampe, Laternenglas und Fenster (beim KI-Bild automatisch, load_ai.py).
  2. Dachs: materialtreue Verkleinerung der Blender-Renderings (badger_cells.py).
  3. Palette: 32 Register im 12-Bit-Raster (16 Stufen je Kanal). Register 0..22 fest (k-means in Oklab über Bild
     und Dachs), 23..27 Farbzyklus Wasser (wie ein CRNG-Bereich in DPaint), 28 Lampe, 29 Laterne, 30 Fenster,
     31 Lichthof der Lampe.
  4. Bild mit geordnetem Muster-Dithering (Bayer 4x4, Farbpaare) auf die festen Register bringen, Wellenstriche
     und Lichter auf die Animationsregister setzen.
  5. Dachs je Bild in der Malweise des Bildes (badger_paint.py): festes Kopfteil mit Gesicht, Tonleitern aus Figuren-
     und Bildregistern mit Muster-Dithering, Paket mit Schnur, selektive Kontur nur auf der Schattenseite.
Ausgaben in assets/ und demo/art/: picture_index.png (Graustufe = Register), palette.json, badger.png (Blatt,
Indexwerte im Rotkanal + Alpha), badger.json, picture_preview.png.
"""
import argparse
import json
import pathlib
import sys

import numpy as np
from PIL import Image

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from amiga import BAYER4, dither, lin_to_srgb, oklab, snap12, srgb_to_lin, to_hex12, kmeans_lab  # noqa: E402
import badger_cells  # noqa: E402
import badger_paint  # noqa: E402

STYLE = HERE.parent
RAW = STYLE / "assets/raw"
OUT_ASSETS = STYLE / "assets"
OUT_DEMO = STYLE / "demo/art"
W, H = 320, 144
N_STATIC = 23
WATER = list(range(23, 28))
LAMP, LANTERN, WINDOW, HALO = 28, 29, 30, 31


def box_linear(img, w, h):
    a = srgb_to_lin(np.asarray(img.convert("RGB"), dtype=np.float64))
    fy, fx = a.shape[0] // h, a.shape[1] // w
    a = a[:h * fy, :w * fx].reshape(h, fy, w, fx, 3).mean((1, 3))
    return lin_to_srgb(a)


def majority(idmap, w, h, k):
    fy, fx = idmap.shape[0] // h, idmap.shape[1] // w
    c = idmap[:h * fy, :w * fx].reshape(h, fy, w, fx).transpose(0, 2, 1, 3).reshape(h, w, -1)
    cnt = np.stack([(c == j).sum(-1) for j in range(k)], -1)
    return np.argmax(cnt, -1)


def load_blender():
    src = RAW / "bg3d"
    rgb = box_linear(Image.open(src / "shaded.png"), W, H)
    cam = json.loads((src / "camera.json").read_text())
    ids = np.asarray(Image.open(src / "id.png").convert("RGB")).astype(np.float64)
    names = ["none", "Water", "Glass"]
    cols = np.array([[0, 0, 0], [0, 0, 255], [255, 255, 0]], dtype=np.float64)
    near = np.argmin(((ids[..., None, :] - cols[None, None]) ** 2).sum(-1), -1)
    exact = (np.abs(ids - cols[near]).max(-1) < 40)
    near = np.where(exact, near, 0)
    m = majority(near, W, H, 3)
    water = m == 1
    glass = m == 2
    lamps = cam["lamps"]
    yy, xx = np.mgrid[0:H, 0:W]

    def around(name, r):
        x, y = lamps[name][0], lamps[name][1]
        return (xx - x) ** 2 + (yy - y) ** 2 <= r * r
    lamp = glass & around("LighthouseLight", 6)
    lantern = glass & around("LanternLight", 6)
    window = glass & ~lamp & ~lantern
    sky = np.asarray(Image.open(src / "id.png").convert("RGB")).astype(np.float64)
    sky = majority(((sky.sum(-1) < 10)).astype(int), W, H, 2) == 1
    return rgb, {"water": water, "lamp": lamp, "lantern": lantern, "window": window, "sky": sky,
                 "lamp_xy": lamps["LighthouseLight"][:2], "lantern_xy": lamps["LanternLight"][:2],
                 "chimney_xy": lamps["ChimneySmoke"][:2], "feet_y": cam["walk_points"]["0"][1],
                 "stop_x": 100, "gull_y": 24}


# Feste Figurenregister: je Materialgruppe eine kurze Tonleiter (k-means über alle Bilder der Figur)
BADGER_RAMPS = [(("FurDark", "Eye", "Nose"), 2), (("FurLight", "Shirt"), 2), (("Cap", "Vest"), 3), (("Scarf",), 2),
                (("Satchel",), 0), (("Parcel", "Brass"), 1)]     # 0: Tasche nur aus Bildregistern (Holzbraun)
CHROMA = {("Cap", "Vest"): 1.7, ("Scarf",): 1.15}
# Grün in drei Stufen (Schatten, Mitte, Licht) mit festem Farbton (Oklab a, b; Motiv: dunkelgrün, das Rendering ist
# eher oliv), damit Mütze und Weste grün bleiben und gedithert schattiert werden
HUE = {("Cap", "Vest"): (-0.045, 0.025)}
RAMP_Q = {("FurDark", "Eye", "Nose"): (0.08, 0.6), ("FurLight", "Shirt"): (0.35, 0.97),
          ("Cap", "Vest"): (0.06, 0.45, 0.98)}     # Kostümfarben wie von Hand gewählt etwas kräftiger


def boost(rgb, k):
    from amiga import lin_to_oklab
    lab = oklab(rgb)
    lab[:, 1:] *= k
    # Oklab -> lineares RGB
    m2i = np.linalg.inv(np.array([[0.2104542553, 0.7936177850, -0.0040720468],
                                  [1.9779984951, -2.4285922050, 0.4505937099],
                                  [0.0259040371, 0.7827717662, -0.8086757660]]))
    m1i = np.linalg.inv(np.array([[0.4122214708, 0.5363325363, 0.0514459929],
                                  [0.2119034982, 0.6806995451, 0.1073969566],
                                  [0.0883024619, 0.2817188376, 0.6299787005]]))
    lms = (lab @ m2i.T) ** 3
    return lin_to_srgb(lms @ m1i.T)


def badger_tones(frames):
    """Je Materialgruppe eine kurze Tonleiter aus Helligkeits-Perzentilen (Licht- und Schattenton weit genug
    auseinander, damit Gesichtsstreifen und Kostüm bei 48 px lesbar bleiben); gibt Farben und Gruppen zurück."""
    tones, group = [], []
    for g, (mats, n) in enumerate(BADGER_RAMPS):
        ks = [badger_cells.MATERIALS.index(m) for m in mats]
        px = np.concatenate([f["rgb"][np.isin(f["mat"], ks)] for f in frames])
        if mats in CHROMA:
            px = boost(px, CHROMA[mats])
        L = oklab(px)[:, 0]
        order = np.argsort(L)
        qs = RAMP_Q.get(mats, () if n == 0 else (0.5,) if n == 1 else (0.2, 0.85))
        for q in qs:
            k = int(q * (len(order) - 1))
            band = order[max(0, k - len(order) // 20):k + len(order) // 20 + 1]
            tone = px[band].mean(0)
            if mats in HUE:
                # fester Farbton über die ganze Leiter (sonst rasten dunkle Töne auf Grau ein)
                tone = badger_paint.lab_to_srgb(np.array([[L[order[k]], *HUE[mats]]]))[0]
            tones.append(tone)
            group.append(g)
    return snap12(np.array(tones)), group


def costume_greens(rgb, mask, qs=(0.25, 0.7)):
    """Zwei feste grüne Register für Weste und Mütze der Nahaufnahme: Helligkeit aus den Pixeln in den
    green_poly-Polygonen (ohne Lichter), Farbton wie die Figurenregister der Totale (HUE). Ohne sie verteilt k-means
    kein Register auf das gedämpfte Grün, und Weste und Mütze werden oliv-braun."""
    if not mask.any():
        return np.zeros((0, 3))
    L = oklab(rgb[mask].reshape(-1, 3))[:, 0]
    L = L[L < np.quantile(L, 0.9)]
    ab = HUE[("Cap", "Vest")]
    return snap12(badger_paint.lab_to_srgb(np.array([[np.quantile(L, q), *ab] for q in qs])))


def build_palette(rgb, masks, fixed, n_static=N_STATIC):
    special = masks["lamp"] | masks["lantern"] | masks["window"]
    samples = rgb[~special].reshape(-1, 3)
    # k-means hängt vom Start ab: 10 feste Starts, das Ergebnis mit dem kleinsten Fehler (im 12-Bit-Raster) gewinnt
    lab_s = oklab(samples)
    best = None
    for seed in range(1, 11):
        init = np.concatenate([fixed, samples[np.random.default_rng(seed).choice(len(samples), n_static - len(fixed))]])
        c, _ = kmeans_lab(samples, n_static, iters=30, seed=seed, init=init, fixed=len(fixed))
        cl = oklab(snap12(c))
        err = float(np.min(((lab_s[:, None] - cl[None]) ** 2).sum(-1), 1).mean())
        if best is None or err < best[0]:
            best = (err, c)
    cent = best[1]
    # Extreme sichern: dunkelstes und hellstes Register nach außen schieben (Dithering braucht die Enden)
    lab = oklab(cent)
    d, b = int(np.argmin(lab[:, 0])), int(np.argmax(lab[:, 0]))
    cent[d] = np.minimum(cent[d], np.percentile(samples, 0.5, axis=0)) * 0.6
    cent[b] = np.maximum(cent[b], np.percentile(samples, 99.7, axis=0))
    pal = np.zeros((32, 3), dtype=np.float64)
    order = np.argsort(oklab(cent)[:, 0])
    pal[:n_static] = snap12(cent[order])
    return pal


def water_ripples(idx, rgb, pal, masks, seed=11):
    """Wellenstriche für den Farbzyklus: kurze waagrechte Striche (zum Horizont hin kürzer), deren Register
    entlang des Strichs um je 1 weiterzählen. Rotiert die Palette, wandert der Glanz den Strich entlang."""
    water = masks["water"]
    rows = np.flatnonzero(water.any(1))
    if not len(rows):
        return idx, None
    y0, y1 = rows.min(), rows.max()
    vals = idx[water]
    # Grundfarbe: häufigstes blaues Register im Wasser
    lab = oklab(pal)
    blueish = [k for k in range(N_STATIC) if lab[k, 2] < -0.02 and lab[k, 0] > 0.18]
    counts = np.bincount(vals, minlength=32)
    base = max(blueish, key=lambda k: counts[k]) if blueish else int(np.argmax(counts))
    rng = np.random.default_rng(seed)
    out = idx.copy()
    n = len(WATER)
    for y in range(y0, y1 + 1):
        depth = (y - y0 + 1) / (y1 - y0 + 1)          # 0 = Horizont, 1 = vorn
        L = int(round(3 + 7 * depth))                  # Strichlänge
        gap = int(round(4 + 10 * depth))
        x = int(rng.integers(0, gap + L))
        while x < W:
            ln = max(2, L + int(rng.integers(-1, 2)))
            ph = int(rng.integers(0, n))
            for k in range(ln):
                xx = x + k
                if xx < W and water[y, xx]:
                    # nur auf Pixeln, deren Ton nahe der Wassergrundfarbe liegt (Spiegelungen bleiben)
                    if np.sqrt(((lab[idx[y, xx]] - lab[base]) ** 2).sum()) < 0.09:
                        out[y, xx] = WATER[(ph + k) % n]
            x += ln + gap + int(rng.integers(0, 3))
    return out, base


def pick(pal, allowed, rgb):
    """Register (aus allowed), dessen Farbe rgb in Oklab am nächsten liegt."""
    lab = oklab(pal[allowed])
    t = oklab(np.array([rgb], dtype=np.float64))[0]
    return int(allowed[int(np.argmin(((lab - t) ** 2).sum(-1)))])


def smoke_regs(pal, allowed, idx, xy):
    """Zwei Rauchregister: wenig Farbe, heller als der Himmel über dem Schornstein (hell, mittel). Abstände so, dass
    die Fahne vor dem tiefblauen Abendhimmel des KI-Bildes grau statt rosa wird."""
    x, y = int(xy[0]), int(xy[1])
    area = idx[max(0, y - 12):max(1, y - 1), max(0, x - 4):min(W, x + 30)]
    vals = area[area < N_STATIC]
    sky = oklab(pal[vals]).mean(0) if len(vals) else oklab(np.array([[60, 60, 100.0]]))[0]
    lab = oklab(pal[allowed])
    out = []
    for dl in (0.22, 0.12):
        target = np.array([sky[0] + dl, sky[1] * 0.5, sky[2] * 0.5])
        out.append(int(allowed[int(np.argmin(((lab - target) ** 2).sum(-1)))]))
    return out


def shadow_reg(pal, allowed, rgb, masks, k=0.3):
    """Register für den Kontaktschatten des Dachses (demo/scripts/shadow.gd): Pflaster um den Haltepunkt, abgedunkelt
    (k in linearem Licht)."""
    fl = int(np.floor(masks["feet_y"])) + 1
    x = int(masks.get("stop_x", 110))
    area = rgb[max(0, fl - 3):min(H, fl + 2), max(0, x - 30):min(W, x + 30)].reshape(-1, 3)
    target = lin_to_srgb(srgb_to_lin(area).mean(0) * k)
    return pick(pal, allowed, target)


def lighter(rgb, dl):
    lab = oklab(np.asarray(rgb, dtype=np.float64)[None])[0]
    # in sRGB annähern: Helligkeit durch Mischen mit Weiß/Blauweiß
    t = np.clip(dl, 0, 1)
    return snap12(rgb * (1 - t) + np.array([200, 215, 255]) * t)


def build_badger(frames, meta, pal, static, ramp_regs, outline, outs):
    """Dachs je Bild in der Malweise des Bildes (badger_paint.py: festes Kopfteil mit Gesicht, Tonleitern aus
    Figuren- und Bildregistern mit Muster-Dithering, Paket mit Schnur, selektive Kontur). Blatt: alle Bilder in einem
    Raster, badger.json: Zelle, Lage je Bild (linke Kante relativ zur Wurzel am Haltepunkt), Fußbreite für den
    Kontaktschatten."""
    cw, ch = meta["cell"]
    n = len(frames)
    cols = 15
    rows = (n + cols - 1) // cols
    sheet = np.zeros((rows * ch, cols * cw, 4), np.uint8)
    gof = badger_paint.group_of(BADGER_RAMPS)
    regs = badger_paint.group_regs(pal, static, ramp_regs, BADGER_RAMPS, frames,
                                   hue={g: HUE[mats] for g, (mats, _n) in enumerate(BADGER_RAMPS) if mats in HUE})
    med_l = badger_paint.group_median_l(BADGER_RAMPS, frames)
    fixes, places = badger_paint.paste_heads(frames)
    idxs = [badger_paint.paint_frame(f, fixes[k], pal, regs, gof, boost, CHROMA, BADGER_RAMPS, med_l, outline)
            for k, f in enumerate(frames)]
    badger_paint.stamp_heads(idxs, places)
    info = []
    for k, f in enumerate(frames):
        idx = idxs[k]
        op = idx >= 0
        rgba = np.zeros(idx.shape + (4,), np.uint8)
        rgba[op, :3] = pal[idx[op]].astype(np.uint8)
        rgba[op, 3] = 255
        r, c = divmod(k, cols)
        sheet[r * ch:(r + 1) * ch, c * cw:(c + 1) * cw] = rgba
        fr = f["meta"]
        info.append({"t": fr["t"], "state": fr["state"], "left": fr["left"],
                     "feet": badger_paint.feet_extent(f["mat"])})
    bj = {"fps": meta["fps"], "cell": [cw, ch], "cols": cols, "foot_margin": meta["foot_margin"],
          "frames": info, "times": meta["times"], "walk": meta["walk"],
          "tone_regs": {"+".join(BADGER_RAMPS[g][0]): [to_hex12(pal[r]) for r in rs] for g, rs in regs.items()}}
    for o in outs:
        Image.fromarray(sheet).save(o / "badger.png")
        (o / "badger.json").write_text(json.dumps(bj, indent=1))


def build_picture(rgb, masks, fixed, spread):
    """Bild auf 32 Register: Palette (23 feste + Animationsregister), Muster-Dithering, Wellenstriche, Lichter.
    Gibt Indexbild, Palette (32x3) und palette.json-Inhalt zurück."""
    # ohne Wasser (Nahaufnahme) werden die 5 Farbzyklus-Register zu festen Farben
    has_water = bool(masks["water"].any())
    n_static = N_STATIC if has_water else WATER[-1] + 1
    pal = build_palette(rgb, masks, fixed, n_static)
    static = list(range(n_static))
    idx = dither(rgb, pal, levels=16, allowed=static, spread=spread)
    idx, base = water_ripples(idx, rgb, pal, masks) if has_water else (idx, None)
    for x0, y0, x1, y1, col in masks.get("paint", []):
        idx[y0:y1, x0:x1] = pick(pal, static, [int(col[i:i + 2], 16) for i in (0, 2, 4)])

    def mean_col(m):
        return rgb[m].mean(0) if m.any() else np.array([255, 220, 140.0])
    pal[LAMP] = snap12(np.maximum(mean_col(masks["lamp"]), [255, 230, 150]))
    pal[LANTERN] = snap12(np.maximum(mean_col(masks["lantern"]), [255, 200, 110]))
    pal[WINDOW] = snap12(np.maximum(mean_col(masks["window"]), [255, 190, 100]))
    idx[masks["lamp"]] = LAMP
    idx[masks["lantern"]] = LANTERN
    idx[masks["window"]] = WINDOW
    if has_water:
        b = pal[base] if base is not None else pal[0]
        water_vals = [b, b, lighter(b, 0.18), lighter(b, 0.38), lighter(b, 0.18)]
        for k, r in enumerate(WATER):
            pal[r] = water_vals[k]
    # Lichthof: Schachbrett um die Lampe auf Himmelspixeln
    lx, ly = masks["lamp_xy"]
    yy, xx = np.mgrid[0:H, 0:W]
    halo = (((xx - lx) ** 2 + (yy - ly) ** 2) <= 5.5 ** 2) & ~masks["lamp"] & masks["sky"] & (((xx + yy) % 2) == 0)
    sky_vals = idx[halo]
    hb = int(np.bincount(sky_vals[sky_vals < n_static], minlength=32).argmax()) if halo.any() else 0
    idx[halo] = HALO
    pal[HALO] = pal[hb]
    palette = {
        "registers": [to_hex12(c) for c in pal],
        "rgb": ["%02x%02x%02x" % tuple(int(v) for v in c) for c in pal],
        "groups": {"water": {"start": WATER[0], "len": len(WATER) if has_water else 0, "steps_per_second": 7.5},
                   "lamp": LAMP, "lantern": LANTERN, "window": WINDOW, "halo": HALO,
                   "halo_off": "%02x%02x%02x" % tuple(int(v) for v in pal[hb]),
                   "halo_on": "%02x%02x%02x" % tuple(int(v) for v in snap12(pal[hb] * 0.35 + np.array([255, 220, 150]) * 0.65))},
        "lamp_xy": [float(v) for v in masks["lamp_xy"]], "lantern_xy": [float(v) for v in masks["lantern_xy"]],
    }
    return idx, pal, palette, base


def mask_overlay(rgb, masks, path, zoom=3):
    """Prüfbild: Ausschnitt mit Masken (Wasser blau, Lampe gelb, Laterne orange, Fenster magenta, Himmel grün)
    und Kreuzen an Schornstein, Fußlinie/Haltepunkt."""
    arr = np.clip(rgb, 0, 255).astype(np.float64).copy()
    for key, col in (("sky", (0, 255, 0)), ("water", (0, 120, 255)), ("lamp", (255, 255, 0)),
                     ("lantern", (255, 128, 0)), ("window", (255, 0, 255))):
        a_ = 0.18 if key == "sky" else 0.6
        arr[masks[key]] = arr[masks[key]] * (1 - a_) + np.array(col) * a_
    im = Image.fromarray(arr.astype(np.uint8)).resize((W * zoom, H * zoom), Image.NEAREST)
    from PIL import ImageDraw
    d = ImageDraw.Draw(im)
    def cross(x, y, col):
        x, y = x * zoom, y * zoom
        d.line([(x - 6, y), (x + 6, y)], fill=col)
        d.line([(x, y - 6), (x, y + 6)], fill=col)
    cross(*masks["chimney_xy"], (255, 255, 255))
    fy = masks["feet_y"] * zoom
    d.line([(0, fy), (W * zoom, fy)], fill=(255, 255, 255))
    cross(masks["stop_x"], masks["feet_y"], (255, 0, 0))
    im.save(path)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--source", default="auto", choices=["auto", "blender", "ai"],
                    help="auto: KI-Bild assets/raw/bg.png, falls vorhanden, sonst Blender-Rendering")
    ap.add_argument("--picture", default="bg", choices=["bg", "closeup"],
                    help="closeup: Nahaufnahme aus assets/raw/closeup.png (eigene 32 Register, kein Dachs-Blatt)")
    ap.add_argument("--preview", action="store_true")
    ap.add_argument("--spread", type=float, default=0.35)
    ap.add_argument("--no-outline", dest="outline", action="store_false", help="Dachs ohne selektive Kontur")
    ap.add_argument("--ai-image", default=None, help="Dateiname in assets/raw/ oder absoluter Pfad")
    ap.add_argument("--layout", default=None, help="Layout-Datei mit Korrekturen (Standard: assets/ai_layout.json "
                                                    "bzw. assets/closeup_layout.json)")
    ap.add_argument("--out", default=None, help="Testlauf: alles in diesen Ordner statt nach assets/ und demo/art/")
    ap.add_argument("--dry", action="store_true", help="nur Vorschau, nichts nach assets/ und demo/ schreiben")
    a = ap.parse_args()
    outs = [pathlib.Path(a.out)] if a.out else [OUT_ASSETS, OUT_DEMO]
    prev_dir = pathlib.Path(a.out) if a.out else OUT_ASSETS
    zoom_dir = pathlib.Path(a.out) if a.out else RAW          # Prüfbilder (x3, Masken) nicht ins Repo
    for o in outs:
        o.mkdir(parents=True, exist_ok=True)
    from load_ai import load_ai
    report = {}

    if a.picture == "closeup":
        name = a.ai_image or "closeup.png"
        src = pathlib.Path(name) if pathlib.Path(name).is_absolute() else RAW / name
        if not src.exists():
            sys.exit(f"fehlt: {src} (Auftrag 2 in assets/image_jobs.json)")
        rgb, masks = load_ai(str(src), a.layout, kind="closeup", report=report)
        idx, pal, palette, base = build_picture(rgb, masks, costume_greens(rgb, masks["green"]), a.spread)
        prev = pal[idx].astype(np.uint8)
        if not a.dry:
            for o in outs:
                Image.fromarray(idx.astype(np.uint8), "L").save(o / "closeup_index.png")
                (o / "closeup_palette.json").write_text(json.dumps(palette, indent=1))
            Image.fromarray(prev).save(prev_dir / "closeup_preview.png")
            (prev_dir / "closeup_detect.json").write_text(json.dumps(report, indent=1))
        if a.preview:
            Image.fromarray(prev).resize((W * 3, H * 3), Image.NEAREST).save(zoom_dir / "closeup_preview_x3.png")
            mask_overlay(rgb, masks, zoom_dir / "closeup_masks_x3.png")
        print("Register:", " ".join(palette["registers"]))
        print("Farben im Bild:", len(np.unique(idx)), "Wasser-Grundregister", base, "Erkannt:", json.dumps(report))
        return

    source = a.source
    ai_name = a.ai_image or "bg.png"
    if source == "auto":
        ai_src = pathlib.Path(ai_name) if pathlib.Path(ai_name).is_absolute() else RAW / ai_name
        source = "ai" if ai_src.exists() else "blender"
    if source == "blender":
        rgb, masks = load_blender()
    else:
        rgb, masks = load_ai(ai_name, a.layout, kind="bg", report=report)
    meta, frames = badger_cells.load(RAW / "badger3d")
    tones, tgroup = badger_tones(frames)
    idx, pal, palette, base = build_picture(rgb, masks, tones, a.spread)
    # Register der Figurentöne wiederfinden (Palette ist nach Helligkeit sortiert)
    ns = N_STATIC if palette["groups"]["water"]["len"] else WATER[-1] + 1
    ramp_regs = {}
    for c, g in zip(tones, tgroup):
        r = int(np.argmin(np.abs(pal[:ns] - c).sum(-1)))
        ramp_regs.setdefault(g, []).append(r)
    static = list(range(ns))
    palette.update({
        "source": source,
        "chimney_xy": [float(v) for v in masks["chimney_xy"]], "feet_y": float(masks["feet_y"]),
        "feet_line": int(np.floor(masks["feet_y"])) + 1, "stop_x": int(masks.get("stop_x", 110)),
        "smoke": smoke_regs(pal, static, idx, masks["chimney_xy"]),
        "gull": [pick(pal, static, c) for c in ((240, 240, 240), (175, 170, 180), (60, 55, 65))],
        "gull_x0": int(masks.get("gull_x0", 300)),
        "shadow": shadow_reg(pal, static, rgb, masks),
        "gull_y": int(masks.get("gull_y", 26)),
    })
    prev = pal[idx].astype(np.uint8)
    if not a.dry:
        for o in outs:
            Image.fromarray(idx.astype(np.uint8), "L").save(o / "picture_index.png")
            (o / "palette.json").write_text(json.dumps(palette, indent=1))
        Image.fromarray(prev).save(prev_dir / "picture_preview.png")
        if report:
            (prev_dir / "picture_detect.json").write_text(json.dumps(report, indent=1))
        else:
            (prev_dir / "picture_detect.json").unlink(missing_ok=True)      # Blender-Weg: nichts erkannt
        build_badger(frames, meta, pal, static, ramp_regs, a.outline, outs)
    print("Quelle:", source)
    print("Register:", " ".join(palette["registers"]))
    print("Farben im Bild:", len(np.unique(idx)), "Wasser-Grundregister", base)
    if report:
        print("Erkannt:", json.dumps(report))
    if a.preview:
        Image.fromarray(prev).resize((W * 3, H * 3), Image.NEAREST).save(zoom_dir / "picture_preview_x3.png")
        if source == "ai":
            mask_overlay(rgb, masks, zoom_dir / "picture_masks_x3.png")


if __name__ == "__main__":
    main()
