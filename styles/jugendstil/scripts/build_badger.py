#!/usr/bin/env python3
"""Bögen des Dachs-Kuriers aus dem KI-Laufbogen (gpt-image, 2x5 Figuren nach dem Blender-Layout), als flache
Plakatfigur mit gleich starker Kontur.

    .venv/bin/python styles/jugendstil/scripts/build_badger.py [--heads]

Aufbau nach styles/art-deco/scripts/build_badger.py (Zellen, Ausrichtung an der Sohle, Verkleinern mit
vormultipliziertem Alpha, Farbauszug in CIELAB). Für den Jugendstil anders:
  1. Farbauszug in 12 Druckfarben: Kontur, Fell, Grün, Rot, Braun, Paket, Creme (teils mit Schattenton), Gold.
     Das Bildmodell malte die Figur als Bilderbuchfigur mit leichter Fellstruktur, Strickmuster und weichen
     Verläufen; Fell und Schal werden je eine einzige Fläche, Mischtöne an Teilgrenzen werden aus den Nachbarn
     aufgefüllt, danach zweimal 3x3-Mehrheit (Kontur ausgenommen). Pixel mit Alpha < 128 gehören nicht zur Figur.
  2. Kontur nachziehen: Die KI-Kontur ist etwa 5 KI-px stark, im Spiel wäre sie damit halb so stark wie die
     Linien des Plakats (4 px bei Faktor 1). Konturpixel großer Linienzüge (Fläche >= MIN_LINE) werden um
     KEY_GROW px aufgedickt (Kreisscheibe), auch nach außen über den Umriss; Auge, Nase und Mund (kleine
     Flecken) bleiben unverändert.
  3. Zwei Bögen in Zielgröße: Totale (Faktor SCALE * ZOOM_FAR) und Nahaufnahme (SCALE * ZOOM_CLOSE).
  4. Gleichmäßiger Kopf: Bei festem Standfuß rückte der Kopf je Bildwechsel 15-29 KI-px vor (walk_1 hat den
     Kopf 6 px weiter vorn als die übrigen Posen). Der Oberkörper jedes Laufbilds wird deshalb leicht geschert
     (HEAD_SHIFT, ab der Hüfte linear bis zur Augenhöhe, darüber konstant, ganze Pixel je Zeile); die Füße bleiben,
     wo sie sind. Ergebnis: 21-22 KI-px Kopfvorschub je Bildwechsel.
  5. Auge mit Glanzpunkt: Jedes Auge (Lage aus EYES, auf den dunkelsten Fleck nachgeführt) bekommt einen
     cremefarbenen Glanzpunkt; nur so ist das geschlossene Lid beim Blinzeln zu sehen.
  6. Idle aus Teilen: Atmen = Oberkörper ab der Hüfte um BREATH KI-px gestreckt (ganze Zeilen), drei Stufen der
     Drehpose (turn, turn_b1, turn_b2), Blinzeln in jeder Stufe (blink, blink_b1, blink_b2).

Eingang: assets/raw/walk.png, assets/ref/layout.json (Zellen 307x512), assets/layout.json (Maßstäbe)
Ausgang (assets/ und demo/art/): walk_inks.png, badger_far.png, badger_close.png, badger.json
Weltmaßstab: SCALE Pixel des Plakatbildes je KI-Pixel.
"""
import json, pathlib, sys
import numpy as np
from PIL import Image, ImageDraw

ROOT = pathlib.Path(__file__).resolve().parents[1]
OUTS = [ROOT / "assets", ROOT / "demo/art"]
SCALE = 0.44            # ~420 KI-px Figur -> ~185 Plakatpixel (Mitte des Kais, Tür ~300 px weiter hinten)
CELL_W = 307
TOP, BOT = 450, 8       # Rahmen über / unter der Sohle (KI-Pixel)
KEY_GROW = 2.0          # Aufdicken der Kontur (KI-px, Radius)
MIN_LINE = 400          # Konturflecken ab dieser Größe gelten als Linienzug
HIP = 120               # Hüfthöhe über der Sohle (KI-px): darunter bleibt die Figur bei Scherung und Atmen fest
# Scherung des Oberkörpers je Laufbild (KI-px an der Nase, + = nach vorn). Herleitung: Kopfposition je Bild =
# Vorschub-Summe (choreo.ADV) + Nase in der Zelle; Abweichung von gleichmäßigen 169/8 KI-px je Bild, gerundet.
# Vorher 29, 15, 22, 23, 20, 19, 23, 18 KI-px Kopfvorschub je Wechsel, danach 21-22.
HEAD_SHIFT = {"walk_0": 3, "walk_1": -5, "walk_2": 1, "walk_3": 0, "walk_4": -1, "walk_5": 0, "walk_6": 2,
              "walk_7": 0}
# Augenmitte je Bild (Rahmenkoordinaten, Sohle in Zeile TOP), an den Kopfansichten (--heads) abgelesen; wird auf
# die Mitte des dunkelsten Flecks (Kreisscheibe r = 5) im Umkreis von 4 px nachgeführt
EYES = {"walk_0": (215, 102), "walk_1": (221, 102), "walk_2": (217, 104), "walk_3": (217, 104),
        "walk_4": (207, 103), "walk_5": (214, 110), "walk_6": (218, 108), "walk_7": (214, 111),
        "stand": (217, 105), "turn": (172, 105)}
GLINT = (2.4, -2.4, 3.0)  # Glanzpunkt: Versatz zur Augenmitte (x, y) und Radius in KI-px
BREATH = (2, 4)           # Atemstufen: Streckung des Oberkörpers am Scheitel (KI-px)

# Druckfarben: Name -> Lab-Vorlagen (Mittel einer k-means-Einteilung des Rohbogens, k = 22, Seed 7)
INKS = {
    "key":         [(5.2, 0.9, 4.3), (8.6, 0.8, 7.1), (11.4, -0.2, 9.6)],
    "fur":         [(23.0, 3.5, 7.4), (24.4, 3.7, 7.5), (26.4, 4.1, 7.8), (27.8, 4.0, 8.3)],
    "green_dark":  [(22.9, -3.3, 14.4)],
    "green":       [(32.4, -5.8, 17.6), (36.9, -6.2, 19.6)],
    "red":         [(39.5, 41.6, 31.3), (33.6, 34.2, 25.2)],
    "brown_dark":  [(19.8, 8.6, 16.7)],
    "brown":       [(26.7, 15.4, 20.5), (34.3, 17.4, 25.5)],
    "parcel_dark": [(48.6, 5.7, 21.6)],
    "parcel":      [(63.8, 14.2, 38.1)],
    "gold":        [(70.0, 12.0, 62.0)],
    "cream_dark":  [(69.0, 2.7, 19.0)],
    "cream":       [(88.3, 3.4, 22.8), (93.8, -0.2, 15.5)],
}
# Mischtöne zwischen Kontur und Fläche bzw. an Teilgrenzen: werden aus den Nachbarn aufgefüllt
AMBIG = [(16.7, 1.7, 9.5), (11.2, 9.1, 10.5)]
# Druckfarben (sRGB), an die Farben des Plakats angelehnt: Kontur wie die Schlüsselplatte des Hintergrunds,
# Grün wie Tür und Laternenpfahl, Rot wie das Dach, Gold wie im Rahmen
INK_RGB = {
    "key": (33, 31, 14), "fur": (74, 63, 52),
    "green_dark": (60, 66, 40), "green": (90, 95, 58),
    "red": (154, 66, 42),
    "brown_dark": (78, 47, 28), "brown": (116, 74, 44),
    "parcel_dark": (156, 116, 72), "parcel": (204, 152, 86),
    "gold": (214, 160, 66),
    "cream_dark": (198, 178, 140), "cream": (240, 220, 182),
}
NAMES = list(INKS)


def srgb_to_lab(c):
    c = c / 255.0
    c = np.where(c > 0.04045, ((c + 0.055) / 1.055) ** 2.4, c / 12.92)
    M = np.array([[0.4124, 0.3576, 0.1805], [0.2126, 0.7152, 0.0722], [0.0193, 0.1192, 0.9505]])
    xyz = c @ M.T / np.array([0.95047, 1.0, 1.08883])
    f = np.where(xyz > 0.008856, np.cbrt(xyz), 7.787 * xyz + 16 / 116)
    return np.stack([116 * f[..., 1] - 16, 500 * (f[..., 0] - f[..., 1]), 200 * (f[..., 1] - f[..., 2])], -1)


def neighbour_counts(ink, n):
    h, w = ink.shape
    counts = np.zeros((n, h, w), np.int16)
    pad = np.pad(ink, 1, constant_values=-1)
    for dy in range(3):
        for dx in range(3):
            win = pad[dy:dy + h, dx:dx + w]
            for k in range(n):
                counts[k] += win == k
    return counts


def separate(rgba):
    """Farbauszug: Druckfarben-Index je Pixel (-1 = durchsichtig)."""
    a = rgba[..., 3]
    vis = a >= 128
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
    # halbdurchsichtige Randpixel des Umrisses (Alpha 128..199) sind Kontur; schwächere gehören nicht zur Figur
    ink[vis & (a < 200)] = NAMES.index("key")
    n = len(NAMES)
    for _ in range(40):
        open_ = ink == -2
        if not open_.any():
            break
        counts = neighbour_counts(ink, n)
        best = counts.argmax(0)
        ok = open_ & (counts.max(0) > 0)
        ink[ok] = best[ok]
    ink[ink == -2] = NAMES.index("key")
    key = NAMES.index("key")
    for _ in range(2):
        counts = neighbour_counts(ink, n)
        best = counts.argmax(0)
        cur = np.take_along_axis(counts, np.clip(ink, 0, None)[None], 0)[0]
        change = vis & (ink >= 0) & (ink != key) & (best != key) & (cur < counts.max(0))
        ink[change] = best[change]
    return ink


def components(b):
    h, w = b.shape
    lab = np.zeros((h, w), np.int32)
    sizes = [0]
    cur = 0
    for y0, x0 in zip(*np.nonzero(b)):
        if lab[y0, x0]:
            continue
        cur += 1
        st = [(y0, x0)]
        lab[y0, x0] = cur
        n = 0
        while st:
            y, x = st.pop()
            n += 1
            for yy, xx in ((y + 1, x), (y - 1, x), (y, x + 1), (y, x - 1)):
                if 0 <= yy < h and 0 <= xx < w and b[yy, xx] and not lab[yy, xx]:
                    lab[yy, xx] = cur
                    st.append((yy, xx))
        sizes.append(n)
    return lab, np.array(sizes)


def dilate(b, r):
    out = b.copy()
    ri = int(np.ceil(r))
    for dy in range(-ri, ri + 1):
        for dx in range(-ri, ri + 1):
            if dx * dx + dy * dy <= r * r + 0.01 and (dx or dy):
                sh = np.zeros_like(b)
                ys = slice(max(0, dy), b.shape[0] + min(0, dy))
                yd = slice(max(0, -dy), b.shape[0] + min(0, -dy))
                xs = slice(max(0, dx), b.shape[1] + min(0, dx))
                xd = slice(max(0, -dx), b.shape[1] + min(0, -dx))
                sh[ys, xs] = b[yd, xd]
                out |= sh
    return out


def largest_component(b):
    lab, sizes = components(b)
    return lab == int(sizes[1:].argmax() + 1)


def ink_sheet(raw):
    ink = separate(raw)
    key = NAMES.index("key")
    lab, sizes = components(ink == key)
    lines = (ink == key) & (sizes[lab] >= MIN_LINE)
    grown = dilate(lines, KEY_GROW)
    # nach außen nur in der Nähe der Figur (nicht in Nachbarzellen hinein: Zellen haben breite Lücken)
    ink[grown] = key
    pal = np.array([INK_RGB[n] for n in NAMES], np.uint8)
    out = np.zeros(raw.shape, np.uint8)
    vis = ink >= 0
    out[..., :3] = np.where(vis[..., None], pal[np.clip(ink, 0, None)], 0)
    out[..., 3] = np.where(vis, 255, 0)
    return out, ink


def find_eye(canvas, guess):
    """Augenmitte: die Stelle im Umkreis von 4 px um guess, an der eine Kreisscheibe (r = 5) die meisten
    Konturpixel deckt (bei Gleichstand die nächste)."""
    key = np.all(canvas[..., :3] == INK_RGB["key"], -1) & (canvas[..., 3] > 0)
    gx, gy = guess
    yy, xx = np.mgrid[-5:6, -5:6]
    disk = xx * xx + yy * yy <= 25
    best = None
    for dy in range(-4, 5):
        for dx in range(-4, 5):
            cx, cy = gx + dx, gy + dy
            sc = int(key[cy - 5:cy + 6, cx - 5:cx + 6][disk].sum())
            k = (-sc, dx * dx + dy * dy)
            if best is None or k < best[0]:
                best = (k, cx, cy)
    return best[1], best[2]


def add_glint(rgba, eye):
    """cremefarbener Glanzpunkt oben vorn im Auge (vierfach überabgetastet gezeichnet, dann Mehrheit)."""
    ss = 4
    ex, ey = eye
    ox, oy, r = GLINT
    im = Image.fromarray(rgba, "RGBA")
    big = im.resize((im.width * ss, im.height * ss), Image.NEAREST)
    cx, cy = (ex + 0.5 + ox) * ss, (ey + 0.5 + oy) * ss
    ImageDraw.Draw(big).ellipse([cx - r * ss, cy - r * ss, cx + r * ss, cy + r * ss], fill=INK_RGB["cream"] + (255,))
    return np.asarray(big.resize(im.size, Image.NEAREST)).copy()


def close_eyes(rgba, eye):
    """Blinzeln: Auge samt Glanzpunkt mit der häufigsten Druckfarbe eines Rings darum übermalen, Lidbogen in
    Konturfarbe."""
    ss = 4
    im = Image.fromarray(rgba, "RGBA")
    big = im.resize((im.width * ss, im.height * ss), Image.NEAREST)
    dr = ImageDraw.Draw(big)
    yy, xx = np.mgrid[0:rgba.shape[0], 0:rgba.shape[1]]
    ex, ey = eye[0] + 0.5, eye[1] + 0.5
    rx = ry = 6.0
    d = ((xx + 0.5 - ex) / (rx + 3)) ** 2 + ((yy + 0.5 - ey) / (ry + 3)) ** 2
    ring = (d > 1.0) & (d < 1.9) & (rgba[..., 3] > 200)
    cols, n = np.unique(rgba[ring][:, :3], axis=0, return_counts=True)
    stripe = tuple(int(v) for v in cols[n.argmax()])
    box = [(ex - rx - 1.5) * ss, (ey - ry - 1.5) * ss, (ex + rx + 1.5) * ss, (ey + ry + 1.5) * ss]
    dr.ellipse(box, fill=stripe + (255,))
    arc = [(ex - rx - 1) * ss, (ey - ry * 0.8) * ss, (ex + rx + 1) * ss, (ey + ry * 0.8) * ss]
    dr.arc(arc, start=20, end=160, fill=INK_RGB["key"] + (255,), width=int(2.6 * ss))
    return np.asarray(big.resize(im.size, Image.NEAREST)).copy()


def shear_upper(canvas, shift, eye_y):
    """Oberkörper scheren: Zeilen über der Hüfte (TOP - HIP) linear bis zur Augenzeile um 0..shift px
    verschieben, darüber um shift; ganze Pixel je Zeile, die Füße bleiben fest."""
    if not shift:
        return canvas
    out = canvas.copy()
    hip = TOP - HIP
    for y in range(hip):
        f = min(1.0, (hip - y) / max(1.0, hip - eye_y))
        k = int(round(shift * f))
        if k:
            out[y] = np.roll(canvas[y], k, axis=0)
            if k > 0:
                out[y, :k] = 0
            else:
                out[y, k:] = 0
    return out


def breathe(canvas, amount, top):
    """Atmen: Oberkörper ab der Hüfte nach oben strecken, am Scheitel um amount Zeilen (ganze Zeilen)."""
    if not amount:
        return canvas
    hip = TOP - HIP
    out = np.zeros_like(canvas)
    out[hip:] = canvas[hip:]
    span = hip - top
    for y in range(hip):
        src = hip - (hip - y) * span / (span + amount)
        sy = int(round(src))
        if 0 <= sy < hip:
            out[y] = canvas[sy]
    return out


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
    lay_scale = json.loads((ROOT / "assets/layout.json").read_text())
    zooms = {"far": lay_scale["shots"][0]["zoom"], "close": lay_scale["shots"][1]["zoom"]}
    raw = np.asarray(Image.open(ROOT / "assets/raw/walk.png").convert("RGBA"))
    im, ink = ink_sheet(raw)
    Image.fromarray(im, "RGBA").save(ROOT / "assets/walk_inks.png")
    vis = ink >= 0
    share = {n: round(float((ink == i).sum() / max(1, vis.sum())), 4) for i, n in enumerate(NAMES)}

    lay = json.loads((ROOT / "assets/ref/layout.json").read_text())
    frames, meta = [], []
    turn = None
    for c in lay["cells"]:
        x, y, w, h = c["x"], c["y"], c["w"], c["h"]
        sub = im[y:y + h, x:x + w].copy()
        core = largest_component(sub[..., 3] >= 128)
        keep = dilate(core, 1)
        sub[..., 3] = (sub[..., 3] * keep).astype(np.uint8)
        ys, xs = np.nonzero(core)
        sole, top = int(ys.max()), int(ys.min())
        canvas = np.zeros((TOP + BOT, w, 4), np.uint8)
        y0 = sole - TOP
        sy0, sy1 = max(0, y0), min(h, sole + BOT)
        canvas[sy0 - y0:sy1 - y0] = sub[sy0:sy1]
        eye = find_eye(canvas, EYES[c["name"]])
        canvas = add_glint(canvas, eye)
        shift = HEAD_SHIFT.get(c["name"], 0)
        canvas = shear_upper(canvas, shift, eye[1])
        eye = (eye[0] + shift, eye[1])
        al = canvas[..., 3] >= 128
        cys, cxs = np.nonzero(al)
        ctop = int(cys.min())
        up = al[ctop:ctop + (TOP - ctop) // 4]
        frames.append(canvas)
        meta.append({"name": c["name"], "sole_ai": sole, "top_ai": top, "height_ai": sole - top + 1,
                     "nose_x_ai": int(np.nonzero(up.any(0))[0].max()), "cx_ai": round(float(cxs.mean()), 1),
                     "eye_ai": [int(eye[0]), int(eye[1])], "head_shift_ai": shift})
        if c["name"] == "turn":
            turn = (canvas, eye, ctop)
        if heads:
            hd = Image.fromarray(canvas[0:200], "RGBA")
            hd = hd.resize((hd.width * 4, hd.height * 4), Image.NEAREST)
            bgc = Image.new("RGBA", hd.size, (90, 100, 140, 255))
            bgc.alpha_composite(hd)
            d = ImageDraw.Draw(bgc)
            for gx in range(0, w, 10):
                d.line([(gx * 4, 0), (gx * 4, 6 if gx % 50 else 16)], fill=(255, 255, 255, 255))
            for gy in range(0, 200, 10):
                d.line([(0, gy * 4), (6 if gy % 50 else 16, gy * 4)], fill=(255, 255, 255, 255))
            (ROOT / "assets/ref").mkdir(exist_ok=True)
            bgc.save(ROOT / f"assets/ref/head_{c['name']}.png")
    # Idle aus Teilen: Atemstufen der Drehpose und Blinzeln in jeder Stufe
    tc, teye, ttop = turn
    tmeta = next(m for m in meta if m["name"] == "turn")
    blink0 = close_eyes(tc, teye)
    for i, amt in enumerate(BREATH, 1):
        frames.append(breathe(tc, amt, ttop))
        meta.append(dict(tmeta, name=f"turn_b{i}", breath_ai=amt))
    frames.append(blink0)
    meta.append(dict(tmeta, name="blink", breath_ai=0))
    for i, amt in enumerate(BREATH, 1):
        frames.append(breathe(blink0, amt, ttop))
        meta.append(dict(tmeta, name=f"blink_b{i}", breath_ai=amt))

    info = {"frames": len(frames), "top_ai": TOP, "names": [m["name"] for m in meta], "scale_world": SCALE,
            "key_grow_ai": KEY_GROW, "inks": INK_RGB, "ink_share": share}
    for name, key in (("badger_far.png", "far"), ("badger_close.png", "close")):
        z = zooms[key]
        sc = SCALE * z
        fw, fh = round(CELL_W * sc), round((TOP + BOT) * sc)
        sheet = np.zeros((fh, fw * len(frames), 4), np.uint8)
        for i, fr in enumerate(frames):
            sheet[:, i * fw:(i + 1) * fw] = downscale(fr, (fw, fh))
        img = Image.fromarray(sheet, "RGBA")
        for d in OUTS:
            d.mkdir(parents=True, exist_ok=True)
            img.save(d / name)
        info.update({"frame_w_" + key: fw, "frame_h_" + key: fh, "scale_" + key: sc, "zoom_" + key: z,
                     "sole_y_" + key: round(TOP * fh / (TOP + BOT), 3), "px_per_ai_" + key: fh / (TOP + BOT)})
        print("ok", name, img.size, "frame", fw, fh)
    info["measure"] = meta
    for d in OUTS:
        (d / "badger.json").write_text(json.dumps(info, indent=1))
    for m in meta:
        print(f'{m["name"]:7s} h {m["height_ai"]}  Nase {m["nose_x_ai"]}  cx {m["cx_ai"]}')
    print("Anteile:", share)


if __name__ == "__main__":
    main(heads="--heads" in sys.argv)
