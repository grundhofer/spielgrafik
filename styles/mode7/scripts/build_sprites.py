"""Baut den Sprite-Atlas (CGRAM-Index je Pixel, 0 = durchsichtig) aus den Blender-Rohbildern und Code.

Aufruf:
  blender -b --factory-startup -P styles/mode7/blender/render_sprites.py -- \
      --spec styles/mode7/blender/sprites_spec.json --out <tmp>/spr
  .venv/bin/python styles/mode7/scripts/build_sprites.py <tmp>/spr

Je Größenstufe ein eigenes Bild aus Blender (vorgezeichnete Stufen, kein Skalieren zur Laufzeit). Verkleinern
nach Material: je Zielpixel (4×4 Rohpixel) gewinnt das Material mit den meisten Rohpixeln (Augen, Nase und
Messing zählen mehrfach, damit sie nicht verschwinden), die Normale wird nur über dieses Material gemittelt.
Schattierung: Licht von oben links vorn, Stufen aus der Tonleiter des Materials in der OBJ-Palette.
Außenkontur in der Konturfarbe der Palette. Möwen, Bojen, Rauch, Lichtschein und Schatten zeichnet der Code.
Ausgabe: demo/art/obj_atlas.png (L8), demo/data/sprites.json, assets/sprites_sheet.png
"""
import json
import math
import pathlib
import sys

import numpy as np
from PIL import Image

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import palette as P            # noqa: E402
from m7lib import STYLE        # noqa: E402

RAW = pathlib.Path(sys.argv[1])
SPEC = json.loads((STYLE / "blender/sprites_spec.json").read_text())
MATNUM = SPEC["materials"]
NUMMAT = {v: k for k, v in MATNUM.items()}
o = P.obj_idx


def srgb(c):
    return np.where(c <= 0.0031308, c * 12.92, 1.055 * np.power(np.maximum(c, 0), 1 / 2.4) - 0.055)


def lin(c):
    return np.where(c <= 0.04045, c / 12.92, np.power((c + 0.055) / 1.055, 2.4))


ID_LUT = np.array([round(float(srgb(np.array(k * 8 / 255.0))) * 255) for k in range(32)])

# Material -> Tonleiter (dunkel -> hell) je Blatt-Gruppe
B = lambda c: o("badger", c)          # noqa: E731
TONES_BADGER = {
    "FurDark": [B("outline"), B("fur_d1"), B("fur_d2")],
    "FurLight": [B("fur_d2"), B("fur_l1"), B("fur_l2")],
    "Shirt": [B("fur_l1"), B("fur_l2"), B("fur_l2")],
    "Cap": [B("green1"), B("green2"), B("green3")],
    "Vest": [B("green1"), B("green2"), B("green3")],
    "Brass": [B("tan1"), B("tan2")],
    "Scarf": [B("red1"), B("red2"), B("red3")],
    "Satchel": [B("brown1"), B("brown2"), B("brown2")],
    "Parcel": [B("brown2"), B("tan1"), B("tan2")],
    "Nose": [B("outline")],
    "Eye": [B("outline")],
}
Bo = lambda c: o("boat", c)           # noqa: E731
TONES_BOAT = {
    "WhitePaint": [Bo("white1"), Bo("white2"), Bo("white3")],
    "RedPaint": [Bo("red1"), Bo("red2"), Bo("red3")],
    "Wood": [Bo("wood1"), Bo("wood2"), Bo("wood3")],
    "WoodDark": [Bo("dark1"), Bo("dark2"), Bo("wood1")],
    "Metal": [Bo("dark1"), Bo("metal")],
    "Rope": [Bo("wood2"), Bo("rope")],
    "Glass": [Bo("glass")],
}
C = lambda c: o("cottage", c)         # noqa: E731
TONES_COTTAGE = {
    "Stone": [C("stone1"), C("stone2"), C("stone3")],
    "StoneDark": [C("sdark1"), C("stone1"), C("stone2")],
    "Roof": [C("roof1"), C("roof2"), C("roof3")],
    "WoodDark": [C("wood1"), C("wood1"), C("wood2")],
    "Wood": [C("wood1"), C("wood2"), C("wood2")],
    "WhitePaint": [C("stone3"), C("white")],
    "RedPaint": [C("red")],
    "Glass": [C("win0"), C("win1")],
}
Pr = lambda c: o("props", c)          # noqa: E731
TONES_PROPS = {
    "StoneDark": [Pr("outline"), Pr("stone")],
    "WoodDark": [Pr("wood1"), Pr("wood1"), Pr("wood2")],
    "Wood": [Pr("wood1"), Pr("wood2"), Pr("wood3")],
    "Metal": [Pr("outline"), Pr("metal1"), Pr("metal2")],
    "Glass": [Pr("glass0"), Pr("glass1")],
    "Rope": [Pr("wood2"), Pr("wood3")],
}
GROUPS = {
    "badger": (TONES_BADGER, B("outline")),
    "boat": (TONES_BOAT, Bo("outline")),
    "cottage": (TONES_COTTAGE, C("outline")),
    "props": (TONES_PROPS, Pr("outline")),
}
SHEET_GROUP = {"badger_walk": "badger", "badger_turn": "badger", "badger_idle": "badger", "badger_wave": "badger",
               "boat_a": "boat", "boat_b": "boat", "cottage": "cottage", "lantern": "props", "barrels": "props",
               "crates": "props"}
WEIGHT = {"Eye": 4.0, "Nose": 3.0, "Brass": 1.5, "Glass": 2.0, "Metal": 1.6, "Rope": 1.3}
THIN = {"Metal", "Rope", "WoodDark"}     # dünne Teile (Pfahl, Mast, Takelage) brauchen weniger Abdeckung
LIGHT = np.array([-0.55, 0.55, 0.62])
LIGHT /= np.linalg.norm(LIGHT)
NO_OUTLINE_MATS = {"Glass"}


def load_raw(tag):
    a = np.asarray(Image.open(RAW / f"{tag}_id.png").convert("RGBA")).astype(int)
    n = np.asarray(Image.open(RAW / f"{tag}_nrm.png").convert("RGBA"))
    if n.dtype != np.uint8:
        n = n.astype(np.float64) / 65535.0
    else:
        n = n.astype(np.float64) / 255.0
    # 16-Bit-PNG liest Pillow als RGBA mit 8 Bit; daher nochmals direkt lesen
    nimg = Image.open(RAW / f"{tag}_nrm.png")
    arr = np.asarray(nimg)
    if arr.dtype == np.uint16 or arr.max() > 255:
        n = arr.astype(np.float64) / 65535.0
    mat = np.abs(a[..., 0:1] - ID_LUT[None, None, :]).argmin(axis=2)
    alpha = a[..., 3] > 127
    mat = np.where(alpha, mat, 0)
    nl = lin(n[..., :3])
    # Kameraraum der Shader-Knoten: +Z zeigt in die Szene; kodiert wurde -nz, also z = zur Kamera
    nrm = np.stack([(nl[..., 0] - 0.5) * 2, (nl[..., 1] - 0.5) * 2, (nl[..., 2] - 0.5) * 2], axis=-1)
    return mat, nrm


def downsample(mat, nrm, ss, tones, outline, small):
    h, w = mat.shape[0] // ss, mat.shape[1] // ss
    out = np.zeros((h, w), np.uint8)
    mats = np.zeros((h, w), np.int32)
    for y in range(h):
        for x in range(w):
            bm = mat[y * ss:(y + 1) * ss, x * ss:(x + 1) * ss].ravel()
            bn = nrm[y * ss:(y + 1) * ss, x * ss:(x + 1) * ss].reshape(-1, 3)
            opaque = bm > 0
            cov = opaque.mean()
            if cov == 0:
                continue
            vals, cnt = np.unique(bm[opaque], return_counts=True)
            score = [c * WEIGHT.get(NUMMAT[v], 1.0) for v, c in zip(vals, cnt)]
            m = int(vals[int(np.argmax(score))])
            name = NUMMAT[m]
            need = 0.25 if name in THIN or name in WEIGHT else 0.45
            if cov < need:
                continue
            nn = bn[bm == m].mean(axis=0)
            nn /= max(1e-6, np.linalg.norm(nn))
            lam = max(0.0, float(nn @ LIGHT))
            s = 0.18 + 0.82 * lam
            tl = tones[name]
            k = min(len(tl) - 1, int(s * len(tl)))
            out[y, x] = tl[k]
            mats[y, x] = m
    # Außenkontur: deckende Pixel mit durchsichtigem 4er-Nachbarn
    if not small:
        op = out > 0
        pad = np.pad(op, 1)
        edge = op & ~(pad[:-2, 1:-1] & pad[2:, 1:-1] & pad[1:-1, :-2] & pad[1:-1, 2:])
        for y, x in zip(*np.nonzero(edge)):
            if NUMMAT.get(int(mats[y, x])) in NO_OUTLINE_MATS:
                continue
            # dünne Teile (Arm, Mast, Pfahl; höchstens 2 px breit) behalten ihre Farbe, sonst verschwinden sie
            # als dunkler Strich in der Kontur
            thin_x = not pad[y + 1, x] and (not pad[y + 1, x + 2] or not pad[y + 1, x + 3 if x + 3 < pad.shape[1] else x + 2])
            thin_y = not pad[y, x + 1] and (not pad[y + 2, x + 1] or not pad[min(y + 3, pad.shape[0] - 1), x + 1])
            if thin_x or thin_y:
                continue
            out[y, x] = outline
    return out, mats


# ---------------------------------------------------------------------------------------------
# Sprites aus Code
# ---------------------------------------------------------------------------------------------
def draw_gull(span, phase):
    """Möwe von vorn/seitlich, Flügelschlag in 4 Phasen (0 oben, 1 Mitte, 2 unten, 3 Mitte)."""
    w = span + 2
    h = max(5, span // 2 + 3)
    img = np.zeros((h, w), np.uint8)
    cx = w // 2
    cy = h // 2
    lift = [-(span // 4), 0, span // 5, 0][phase]
    white, grey, out = Pr("white2"), Pr("white1"), Pr("outline")
    half = span // 2
    for side in (-1, 1):
        for k in range(1, half + 1):
            x = cx + side * k
            t = k / half
            # Flügel: innen gerade, außen zum Schlagwinkel
            y = cy + int(round(lift * (t ** 1.3))) - (1 if k < half * 0.4 and phase == 0 else 0)
            if 0 <= x < w and 0 <= y < h:
                img[y, x] = white if t < 0.7 else (grey if t < 0.9 else out)
                if span >= 12 and t < 0.6 and 0 <= y + 1 < h:
                    img[y + 1, x] = grey
    for dy in (0, 1):
        for dx in (-1, 0):
            if 0 <= cy + dy < h:
                img[cy + dy, cx + dx] = white
    if span >= 10:
        img[cy, cx + 1] = Pr("wood3")       # Schnabel
    return img


def draw_buoy(px_h):
    """Spitztonne: roter Kegel, weißes Band, Licht oben (Palettenanimation)."""
    h = px_h + 2
    w = max(4, int(round(px_h * 0.62)))
    if w % 2:
        w += 1
    img = np.zeros((h, w), np.uint8)
    body0 = 2
    for y in range(body0, h):
        t = (y - body0) / max(1, h - body0 - 1)
        half = max(0.6, (w / 2) * (0.35 + 0.65 * t))
        for x in range(w):
            if abs(x + 0.5 - w / 2) <= half:
                band = 0.45 < t < 0.62
                col = Pr("white2") if band else Pr("red2")
                if x + 0.5 > w / 2 + half * 0.25:
                    col = Pr("white1") if band else Pr("red1")
                img[y, x] = col
    img[0, w // 2 - 1:w // 2 + 1] = Pr("light")
    img[1, w // 2 - 1:w // 2 + 1] = Pr("metal1")
    # Kontur unten (Wasserlinie)
    img[h - 1, :] = np.where(img[h - 1, :] > 0, Pr("outline"), 0)
    return img


def disc(r, cols, light=True):
    s = 2 * r + 1
    img = np.zeros((s, s), np.uint8)
    for y in range(s):
        for x in range(s):
            dx, dy = x - r, y - r
            d = math.hypot(dx, dy)
            if d <= r + 0.3:
                if light:
                    k = 2 if (dx + dy) < -r * 0.5 else (1 if (dx + dy) < r * 0.4 else 0)
                else:
                    k = 2 if d < r * 0.4 else (1 if d < r * 0.75 else 0)
                img[y, x] = cols[k]
    return img


def ellipse(w, h, col):
    img = np.zeros((h, w), np.uint8)
    for y in range(h):
        for x in range(w):
            if ((x + 0.5 - w / 2) / (w / 2)) ** 2 + ((y + 0.5 - h / 2) / (h / 2)) ** 2 <= 1.0:
                img[y, x] = col
    return img


# ---------------------------------------------------------------------------------------------
def main():
    index = json.loads((RAW / "index.json").read_text())
    frames = []      # (sheet, step, frame, roll, img, anchor, marks, ppm)
    for rec in index:
        sh = rec["sheet"]
        tag = f"{sh}_s{rec['step']}_f{rec['frame']}" + (f"_r{rec['roll']}" if any(
            r["sheet"] == sh and r["roll"] > 0 for r in index) else "")
        tones, outline = GROUPS[SHEET_GROUP[sh]]
        mat, nrm = load_raw(tag)
        ss = rec["ss"]
        small = mat.shape[0] // ss < 14
        img, _ = downsample(mat, nrm, ss, tones, outline, small)
        anchor = [rec["ground"][0] / ss, rec["ground"][1] / ss]
        marks = {k: [v[0] / ss, v[1] / ss] for k, v in rec["marks"].items()}
        frames.append((sh, rec["step"], rec["frame"], rec["roll"], img, anchor, marks, rec["ppm"]))
    # Code-Sprites: (Blatt, Stufe, Bild, 0, Bild, Anker, {}, ppm)
    for si, span in enumerate([17, 13, 10, 7]):
        for ph in range(4):
            g = draw_gull(span, ph)
            frames.append(("gull", si, ph, 0, g, [g.shape[1] / 2, g.shape[0] / 2], {}, span / 1.1))
    for si, ppm in enumerate([13, 10, 7.7, 6, 4.6]):
        b = draw_buoy(int(round(0.9 * ppm)))
        frames.append(("buoy", si, 0, 0, b, [b.shape[1] / 2, b.shape[0] - 0.5], {"light": [b.shape[1] / 2, 0.5]}, ppm))
    for si, r in enumerate([1, 2, 3, 4, 5, 6]):
        d = disc(r, [o("smoke", "s1"), o("smoke", "s2"), o("smoke", "s3")])
        frames.append(("smoke", si, 0, 0, d, [r + 0.5, r + 0.5], {}, r))
    for si, r in enumerate([7, 5, 4, 3]):
        d = disc(r, [o("glow", "g1"), o("glow", "g2"), o("glow", "g3")], light=False)
        frames.append(("glow", si, 0, 0, d, [r + 0.5, r + 0.5], {}, r))
    for si, ppm in enumerate([38, 30, 24, 19, 15, 12]):
        e = ellipse(max(4, int(round(0.62 * ppm))), max(2, int(round(0.16 * ppm))), o("shade", "k"))
        frames.append(("shadow", si, 0, 0, e, [e.shape[1] / 2, e.shape[0] / 2], {}, ppm))

    # Zuschneiden und packen (Regale)
    packed = []
    for (sh, st, fr, ro, img, anc, marks, ppm) in frames:
        ys, xs = np.nonzero(img)
        if len(ys) == 0:
            y0 = x0 = 0
            crop = np.zeros((1, 1), np.uint8)
        else:
            y0, y1, x0, x1 = ys.min(), ys.max() + 1, xs.min(), xs.max() + 1
            crop = img[y0:y1, x0:x1]
        packed.append(dict(sheet=sh, step=st, frame=fr, roll=ro, img=crop,
                           anchor=[anc[0] - x0, anc[1] - y0],
                           marks={k: [v[0] - x0, v[1] - y0] for k, v in marks.items()}, ppm=ppm))
    AW = 512
    order = sorted(range(len(packed)), key=lambda i: -packed[i]["img"].shape[0])
    x = y = rowh = 0
    for i in order:
        h, w = packed[i]["img"].shape
        if x + w > AW:
            x, y, rowh = 0, y + rowh + 1, 0
        packed[i]["rect"] = [x, y, w, h]
        x += w + 1
        rowh = max(rowh, h)
    AH = y + rowh + 1
    atlas = np.zeros((AH, AW), np.uint8)
    for p in packed:
        x, y, w, h = p["rect"]
        atlas[y:y + h, x:x + w] = p["img"]
    Image.fromarray(atlas, "L").save(STYLE / "demo/art/obj_atlas.png")
    data = {}
    for p in packed:
        sh = data.setdefault(p["sheet"], {"steps": {}})
        st = sh["steps"].setdefault(str(p["step"]), {"ppm": p["ppm"], "frames": []})
        st["frames"].append({"frame": p["frame"], "roll": p["roll"], "rect": p["rect"],
                             "anchor": [round(v, 2) for v in p["anchor"]],
                             "marks": {k: [round(a, 2) for a in v] for k, v in p["marks"].items()}})
    for sh in data.values():
        for st in sh["steps"].values():
            st["frames"].sort(key=lambda f: (f["frame"], f["roll"]))
    (STYLE / "demo/data/sprites.json").write_text(json.dumps(data, indent=1))
    tab = P.write_cgram()
    lut = np.array([P.rgb8(c) for c in tab], np.uint8)
    # Vorschau: Atlas ×3 auf dunklem und hellem Grund
    rgb = lut[atlas]
    for name, bg in (("dark", (24, 22, 40)), ("light", (200, 200, 190))):
        im = np.where((atlas > 0)[..., None], rgb, np.array(bg, np.uint8))
        Image.fromarray(im.astype(np.uint8)).resize((AW * 3, AH * 3), Image.NEAREST).save(
            STYLE / f"assets/sprites_sheet_{name}.png")
    print(f"{len(packed)} Bilder, Atlas {AW}×{AH}")
    for k, sh in data.items():
        print(k, {s: (v["ppm"], len(v["frames"]), v["frames"][0]["rect"][2:]) for s, v in sh["steps"].items()})


if __name__ == "__main__":
    main()
