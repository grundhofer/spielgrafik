#!/usr/bin/env python3
"""Bogen des Dachs-Kuriers aus dem KI-Laufbogen (gpt-image, 2x5 Figuren nach dem Blender-Layout), als Plakatdruck.

    .venv/bin/python styles/art-deco/scripts/build_badger.py

Aufbau nach styles/ukiyo-e/scripts/build_badger.py (Zellen, Ausrichtung an der Sohle, Verkleinern mit
vormultipliziertem Alpha). Neu ist der Farbauszug in Plakatfarben:
  Das Bildmodell malte die Figur mit weichen Airbrush-Verläufen und wirkte dadurch wie ein 3D-Spielzeug. Jedes
  Pixel bekommt deshalb die nächste von 16 Plakatfarben (CIELAB; Vorlagen = k-means-Mittel des Bogens, je
  Kostümteil zwei Töne: Licht und Schatten, dazu Kantenlicht, Gold, Augen). Mischtöne an Teilgrenzen
  (Braungrau, Violettgrau, Oliv, Graubeige) gehören zu keiner Farbe und werden aus den Nachbarn aufgefüllt;
  danach 3x3-Mehrheit (Augen, Nase und Mundstrich ausgenommen). Ergebnis: harte Kanten zwischen flachen
  Farbflächen wie im Steindruck, gleiche Farben in allen zehn Bildern.

Eingang: assets/raw/walk.png, assets/ref/layout.json (Zellen 307x512)
Ausgang (assets/ und demo/art/):
  walk_inks.png     ganzer Bogen nach dem Farbauszug (zur Kontrolle)
  badger_far.png    Totale: eine Reihe walk_0 … walk_7, stand, turn, blink; Faktor SCALE * ZOOM_FAR
  badger_close.png  Nahaufnahme: dieselben Bilder, Faktor SCALE * ZOOM_CLOSE
  badger.json       Bildgrößen, Sohlenlinien, Maßstäbe, Messwerte je KI-Zelle
Weltmaßstab: SCALE Weltpixel (Pixel des Plakatbildes) je KI-Pixel.
"""
import json, pathlib
import numpy as np
from PIL import Image, ImageDraw

ROOT = pathlib.Path(__file__).resolve().parents[1]
OUTS = [ROOT / "assets", ROOT / "demo/art"]
SCALE = 0.28            # ~421 KI-px Figur -> ~118 Weltpixel (Dachs vorn auf dem Kai, Tür 185 px weiter hinten)
ZOOM_FAR = 1280 / 1536  # Totale: ganzes Plakat in voller Breite
ZOOM_CLOSE = 1.35       # Nahaufnahme: 1,62-fache Totale
CELL_W = 307
TOP, BOT = 450, 6       # Rahmen über / unter der Sohle (KI-Pixel)

# Plakatfarben: Name -> Lab-Vorlagen (Mittel der k-means-Gruppen des Rohbogens, k = 24, Seed 7)
INKS = {
    "dark":        [(9.5, 1.1, -6.7)],
    "fur_dark":    [(17.0, 1.2, -13.2), (21.1, 1.4, -11.8)],
    "fur_light":   [(25.1, 1.3, -11.2)],
    "green_dark":  [(22.1, -11.4, 5.1), (27.4, -12.5, 8.1)],
    "green_light": [(32.0, -11.8, 11.7)],
    "brown_dark":  [(24.0, 18.8, 13.6)],
    "brown":       [(38.1, 23.4, 21.1)],
    "red_dark":    [(27.4, 41.1, 20.7)],
    "red":         [(35.0, 47.9, 27.4), (42.0, 54.9, 34.9)],
    "red_light":   [(54.2, 59.7, 48.9)],
    "parcel":      [(64.1, 23.2, 41.0)],
    "gold":        [(75.5, 19.6, 54.7)],
    "rim":         [(65.9, 40.2, 55.4)],
    "cream_shade": [(80.4, 8.2, 25.5)],
    "cream":       [(85.4, 8.8, 30.9), (90.3, 3.2, 26.0), (93.9, -4.6, 31.6)],
}
# Mischtöne an Teilgrenzen: werden aus den Nachbarn aufgefüllt
AMBIG = [(28.4, 3.0, 9.8), (29.5, 8.2, -3.3), (38.7, 1.7, 20.9), (58.5, 2.8, 14.1)]
# Druckfarbe je Plakatfarbe (sRGB). Aus den Mittelwerten des Rohbogens, leicht zu den Plakatfarben des
# Hintergrunds geschoben (Fell blauschwarz, Creme warm, Gold ocker).
INK_RGB = {
    "dark": (20, 22, 34), "fur_dark": (33, 42, 62), "fur_light": (56, 64, 86),
    "green_dark": (40, 62, 48), "green_light": (66, 88, 60),
    "brown_dark": (86, 44, 38), "brown": (138, 78, 58),
    "red_dark": (122, 30, 38), "red": (172, 44, 44), "red_light": (226, 82, 52),
    "parcel": (210, 140, 86), "gold": (236, 176, 88), "rim": (240, 128, 64),
    "cream_shade": (226, 186, 146), "cream": (248, 218, 172),
}
NAMES = list(INKS)


def srgb_to_lab(c):
    c = c / 255.0
    c = np.where(c > 0.04045, ((c + 0.055) / 1.055) ** 2.4, c / 12.92)
    M = np.array([[0.4124, 0.3576, 0.1805], [0.2126, 0.7152, 0.0722], [0.0193, 0.1192, 0.9505]])
    xyz = c @ M.T / np.array([0.95047, 1.0, 1.08883])
    f = np.where(xyz > 0.008856, np.cbrt(xyz), 7.787 * xyz + 16 / 116)
    return np.stack([116 * f[..., 1] - 16, 500 * (f[..., 0] - f[..., 1]), 200 * (f[..., 1] - f[..., 2])], -1)


def separate(rgba):
    """Farbauszug: Ink-Index je Pixel (-1 = durchsichtig)."""
    a = rgba[..., 3]
    vis = a > 0
    lab = srgb_to_lab(rgba[..., :3].astype(np.float64))
    protos, owner = [], []
    for i, n in enumerate(NAMES):
        for p in INKS[n]:
            protos.append(p)
            owner.append(i)
    for p in AMBIG:
        protos.append(p)
        owner.append(-2)
    P = np.array(protos)
    owner = np.array(owner)
    ink = np.full(a.shape, -1, np.int32)
    ys, xs = np.nonzero(vis)
    d = ((lab[ys, xs][:, None, :] - P[None]) ** 2).sum(-1)
    ink[ys, xs] = owner[d.argmin(1)]
    # Mischtöne aus den Nachbarn auffüllen (Mehrheit der eindeutigen Nachbarn, bis nichts mehr offen ist)
    n = len(NAMES)
    for _ in range(40):
        open_ = ink == -2
        if not open_.any():
            break
        counts = np.zeros((n,) + a.shape, np.int16)
        pad = np.pad(ink, 1, constant_values=-1)
        for dy in range(3):
            for dx in range(3):
                win = pad[dy:dy + a.shape[0], dx:dx + a.shape[1]]
                for k in range(n):
                    counts[k] += win == k
        best = counts.argmax(0)
        ok = open_ & (counts.max(0) > 0)
        ink[ok] = best[ok]
    ink[ink == -2] = NAMES.index("fur_dark")
    # 3x3-Mehrheit (zweimal), Augen/Nase/Mund ("dark") bleiben unverändert
    dark = NAMES.index("dark")
    for _ in range(2):
        counts = np.zeros((n,) + a.shape, np.int16)
        pad = np.pad(ink, 1, constant_values=-1)
        for dy in range(3):
            for dx in range(3):
                win = pad[dy:dy + a.shape[0], dx:dx + a.shape[1]]
                for k in range(n):
                    counts[k] += win == k
        best = counts.argmax(0)
        cur = np.take_along_axis(counts, np.clip(ink, 0, None)[None], 0)[0]
        change = vis & (ink >= 0) & (ink != dark) & (cur < counts.max(0))
        ink[change] = best[change]
    return ink


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


# Augen im Dreiviertelbild (Rahmenkoordinaten x, y; Halbachsen rx, ry), abgelesen an der 4-fach vergrößerten
# Zelle nach dem Farbauszug (scripts/build_badger.py --heads schreibt die Ansicht)
TURN_EYES = [(192.0, 107.5, 7.0, 7.5), (232.5, 104.0, 5.5, 7.0)]


def close_eyes(rgba):
    """Blinzeln: Augen mit der Farbe des Augenstreifs übermalen (häufigste Plakatfarbe in einem Ring um das Auge),
    Lidbogen in Augenfarbe. Arbeitet 4-fach vergrößert und verkleinert mit Nearest (bleibt in Plakatfarben)."""
    ss = 4
    im = Image.fromarray(rgba, "RGBA")
    big = im.resize((im.width * ss, im.height * ss), Image.NEAREST)
    dr = ImageDraw.Draw(big)
    yy, xx = np.mgrid[0:rgba.shape[0], 0:rgba.shape[1]]
    for ex, ey, rx, ry in TURN_EYES:
        d = ((xx - ex) / (rx + 3)) ** 2 + ((yy - ey) / (ry + 3)) ** 2
        ring = (d > 1.0) & (d < 1.9) & (rgba[..., 3] > 200)
        cols, n = np.unique(rgba[ring][:, :3], axis=0, return_counts=True)
        stripe = tuple(int(v) for v in cols[n.argmax()])
        box = [(ex - rx - 1.5) * ss, (ey - ry - 1.5) * ss, (ex + rx + 1.5) * ss, (ey + ry + 1.5) * ss]
        dr.ellipse(box, fill=stripe + (255,))
        arc = [(ex - rx - 1) * ss, (ey - ry * 0.8) * ss, (ex + rx + 1) * ss, (ey + ry * 0.8) * ss]
        dr.arc(arc, start=20, end=160, fill=INK_RGB["dark"] + (255,), width=int(2.4 * ss))
    return np.asarray(big.resize(im.size, Image.NEAREST))


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


def main(heads=False):
    raw = np.asarray(Image.open(ROOT / "assets/raw/walk.png").convert("RGBA"))
    ink = separate(raw)
    pal = np.array([INK_RGB[n] for n in NAMES], np.uint8)
    im = raw.copy()
    im[..., :3] = np.where((ink >= 0)[..., None], pal[np.clip(ink, 0, None)], 0)
    Image.fromarray(im, "RGBA").save(ROOT / "assets/walk_inks.png")
    share = {n: round(float((ink == i).sum() / max(1, (ink >= 0).sum())), 4) for i, n in enumerate(NAMES)}

    lay = json.loads((ROOT / "assets/ref/layout.json").read_text())
    frames, meta = [], []
    blink = None
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
        meta.append({"name": c["name"], "sole_ai": sole, "top_ai": top, "height_ai": sole - top + 1,
                     "contact_ai": contact, "nose_x_ai": int(np.nonzero(up.any(0))[0].max()),
                     "cx_ai": round(float(xs.mean()), 1)})
        if c["name"] == "turn":
            blink = close_eyes(canvas)
        if heads:
            hd = Image.fromarray(canvas[40:200], "RGBA")
            hd = hd.resize((hd.width * 4, hd.height * 4), Image.NEAREST)
            bgc = Image.new("RGBA", hd.size, (90, 100, 140, 255))
            bgc.alpha_composite(hd)
            d = ImageDraw.Draw(bgc)
            for gx in range(0, w, 10):
                d.line([(gx * 4, 0), (gx * 4, 6 if gx % 50 else 16)], fill=(255, 255, 255, 255))
            for gy in range(0, 160, 10):
                d.line([(0, gy * 4), (6 if (gy + 40) % 50 else 16, gy * 4)], fill=(255, 255, 255, 255))
            bgc.save(ROOT / f"assets/ref/head_{c['name']}.png")
    frames.append(blink)
    meta.append(dict(meta[-1], name="blink"))

    info = {"frames": len(frames), "top_ai": TOP, "names": [m["name"] for m in meta], "scale_world": SCALE,
            "inks": INK_RGB, "ink_share": share}
    for name, z, key in (("badger_far.png", ZOOM_FAR, "_far"), ("badger_close.png", ZOOM_CLOSE, "_close")):
        sc = SCALE * z
        fw, fh = round(CELL_W * sc), round((TOP + BOT) * sc)
        sheet = np.zeros((fh, fw * len(frames), 4), np.uint8)
        for i, fr in enumerate(frames):
            sheet[:, i * fw:(i + 1) * fw] = downscale(fr, (fw, fh))
        img = Image.fromarray(sheet, "RGBA")
        for d in OUTS:
            d.mkdir(parents=True, exist_ok=True)
            img.save(d / name)
        info.update({"frame_w" + key: fw, "frame_h" + key: fh, "scale" + key: sc, "zoom" + key: z,
                     "sole_y" + key: round(TOP * fh / (TOP + BOT), 3), "px_per_ai" + key: fh / (TOP + BOT)})
        print("ok", name, img.size, "frame", fw, fh)
    info["measure"] = meta
    for d in OUTS:
        (d / "badger.json").write_text(json.dumps(info, indent=1))
    for m in meta:
        print(f'{m["name"]:7s} h {m["height_ai"]}  Kontakt {m["contact_ai"]}  Nase {m["nose_x_ai"]}  cx {m["cx_ai"]}')
    print("Anteile:", share)


if __name__ == "__main__":
    import sys
    main(heads="--heads" in sys.argv)
