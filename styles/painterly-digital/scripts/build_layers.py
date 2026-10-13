#!/usr/bin/env python3
"""Zerlegt das gemalte Hauptbild (assets/raw/master.png, agy) in Parallax-Ebenen für die Godot-Demo.

Weil agy nach dem ersten Bild nur noch „429 quota exhausted“ meldete, entstehen die Ebenen nicht als eigene
KI-Bilder, sondern aus dem einen Gemälde:
  1. Grobe Polygone (Bildkoordinaten des Rohbilds 1264x848) um Hafen-Ebene und Landzunge.
  2. Clean Plate (Himmel + Meer ohne Objekte): Bereiche unter den Polygonen zeilenweise zwischen den
     Randfarben links und rechts interpoliert (Himmel und Meer sind waagerecht gebändert; die Horizontlinie
     bleibt scharf, weil jede Zeile für sich gefüllt wird) plus leichte Pinseltextur aus der Nachbarschaft.
  3. Alpha je Ebene: Differenz zwischen Gemälde und Clean Plate (weiche Schwelle) innerhalb des Polygons,
     vereinigt mit dem um 5 px geschrumpften Polygon (Kern), Löcher gefüllt, 0,6 px weichgezeichnet.
     Im Bereich von Booten und Steg (BOATS_BOX) gilt stattdessen nur die Vereinigung eng nachgezeichneter
     Formen; Laterne, Arm, Strebe und Pfahl sind eigene, überabgetastete und leicht weiche Formen.
  (Die Vordergrund-Silhouetten entstehen in build_fx.py.)
Alles wird mit Faktor SCALE (Lanczos) auf Spielgröße gebracht. Ausgabe: assets/layers/*.png und Kopie nach
demo/art/. Ein zweiter Lauf erzeugt bitgleiche Dateien.
"""
import json, pathlib, shutil
import numpy as np
from PIL import Image, ImageDraw, ImageFilter

S = pathlib.Path(__file__).resolve().parent.parent
RAW = S / "assets" / "raw" / "master.png"
OUT = S / "assets" / "layers"
ART = S / "demo" / "art"
SCALE = 1.15
Y_OFF = 85           # Bildschirm-y = SCALE * y_roh - Y_OFF (Fenster 720 px hoch)

# Formen je Ebene: ("poly", Punkte) oder ("line", Punkte, Breite); Rohbild-Koordinaten 1264x848.
HARBOUR = [
    ("poly", [(0, 848), (0, 588), (6, 588), (6, 553), (14, 543), (36, 541), (36, 526), (56, 520), (56, 438),
              (38, 436), (38, 427), (146, 305), (168, 304), (236, 314), (234, 294), (241, 293), (241, 276), (246, 272),
              (260, 272), (264, 277), (266, 271), (283, 270), (288, 275), (289, 293), (304, 294), (304, 314), (300, 318), (300, 346), (372, 424), (372, 438),
              (358, 441), (358, 516), (384, 516), (384, 556), (412, 556),
              (414, 540), (428, 536), (460, 536),
              (462, 572), (492, 570), (492, 524), (504, 508), (585, 503), (614, 504), (622, 514), (636, 506),
              (652, 506), (654, 518), (690, 512), (706, 512), (706, 546), (712, 544), (768, 532), (800, 532),
              (806, 546), (800, 572), (805, 592), (1074, 590), (1074, 558), (1106, 558), (1106, 590),
              (1264, 588), (1264, 848)]),
    ("hard", [(396.5, 444.5), (398.5, 443.6), (443.5, 443.6), (444.5, 440.5), (446.5, 438.6), (449.5, 438.6),
              (451.5, 440.5), (452.5, 443.6), (458.2, 443.8), (459.6, 445.2), (459.6, 451.2), (458, 452.2),
              (399, 452.6), (396.5, 451.6)]),                                         # Laternenarm (eng am Holz)
    ("hardline", [(408, 480.5), (431, 454)], 4),                                      # Strebe
    ("tight", [(398.2, 432.4), (411.6, 432.4), (411.6, 436.2), (407.8, 437.2), (407.8, 556), (399.4, 556),
               (399.4, 437.2), (398.2, 436.2)], 0.0),                                 # Pfahl (ohne hellen Lichtrand)
    ("hard", [(443, 452), (454, 452), (454, 461), (457, 463), (461, 468), (462, 473), (458, 474), (458, 492),
              (461, 493), (461, 497), (456, 500), (440, 500), (435, 497), (435, 493), (438, 492), (438, 474),
              (434, 473), (435, 468), (439, 463), (443, 461)], 1.0),                  # Laterne
]
HEADLAND = [
    ("poly", [(838, 492), (838, 446), (848, 428), (876, 422), (902, 438), (912, 442), (948, 403), (972, 384),
              (998, 364), (1028, 348), (1042, 346), (1042, 300), (1045, 241), (1089, 241), (1092, 300), (1096, 342), (1128, 333), (1164, 311),
              (1198, 309), (1238, 293), (1264, 283), (1264, 492)]),
    ("hard", [(1066, 187), (1069, 196), (1078, 204), (1082, 208), (1082, 211), (1079, 212), (1079, 225),
              (1083, 226), (1083, 233), (1081, 235), (1087, 237), (1087, 243), (1047, 243), (1047, 237),
              (1050, 235), (1050, 226), (1054, 225), (1054, 212), (1051, 211), (1051, 208), (1055, 204),
              (1063, 196)]),                                                          # Laternenhaus
]
# Boote, Steg, Pfosten und Mast: Im Gemälde sind Holz und dunkles Wasser fast gleich hell und gleich getönt;
# die Differenzmaske nahm dort Dunst über dem Ruderboot, Stufen um die Pfosten, einen Streifen neben dem Mast und
# Wasserflecken mit, die beim Schwenk mit 1,0 über das Plate-Wasser (~0,6) glitten. Innerhalb von BOATS_BOX gilt
# deshalb nur die Vereinigung dieser eng nachgezeichneten Formen (an 6-7-fachen Lupenbildern mit 5-px-Raster
# abgelesen); das Wasser dazwischen kommt aus der Clean Plate.
BOATS_BOX = (466, 455, 812, 600)
BOATS = [
    ("poly", [(495.5, 535.5), (500, 532.5), (503.8, 526), (504.5, 524.2), (514, 523.8), (514.6, 530), (518, 530),
              (545, 523.2), (565, 519.4), (585, 515.2), (605.5, 512.4), (606.6, 509), (612.8, 508.8), (613.4, 515.6),
              (618.4, 519.4), (618.8, 533), (600, 548), (530, 565), (507.4, 553.7), (502, 548.2),
              (497.8, 541)]),                                                         # Ruderboot
    ("poly", [(466, 579.6), (484, 573.2), (499, 570.8), (507.6, 569.6), (507.6, 553), (519, 551), (560, 546),
              (618.8, 529.4), (628, 527.4), (634.8, 526), (643.4, 524), (660, 524), (680, 524.8), (694.4, 525.6),
              (694.4, 536.4), (667, 548.6), (640, 561.4), (620, 571.4), (600, 580), (583, 587), (565, 590),
              (466, 592)]),                                                           # Steg
    ("poly", [(634.8, 512.6), (643, 512.2), (643.4, 526), (634.8, 526)]),             # Pfosten
    ("poly", [(694.4, 517), (702.8, 517), (703.2, 562), (694.2, 562)]),
    ("poly", [(628.6, 544.4), (638.6, 544.4), (638.6, 600), (628.6, 600)]),
    ("poly", [(655.8, 535), (665.6, 535), (665.6, 582), (655.8, 582)]),
    ("poly", [(580.8, 563), (590, 563), (590, 600), (580.8, 600)]),
    ("poly", [(685, 552), (693.6, 552), (694, 560), (685, 560)]),
    ("line", [(665.6, 560.5), (669, 564.5), (673.5, 566.8), (678, 566), (681, 563)], 2.5),   # Festmacher
    ("poly", [(682.6, 553), (693.6, 552.4), (695.8, 555.6), (704.3, 551.4), (718.6, 548.6), (732.9, 544.3),
              (747, 538.2), (761.4, 533.4), (775.7, 534.6), (798.6, 537.8), (799.4, 547), (796.4, 560),
              (792.9, 566), (776, 578.6), (762, 588.6), (758, 600), (694, 600), (680, 568)]),   # Mastboot
    ("poly", [(727.2, 464), (731.8, 464), (732.6, 548), (726.4, 548)]),               # Mast (4-5 px)
    ("poly", [(466, 587.5), (500, 588.5), (540, 592.5), (600, 596.5), (645, 595.5), (720, 596.5), (780, 597),
              (812, 595.5), (812, 601), (466, 601)]),                                 # Oberkante des Kais
]
GLOWS = [(448, 472, 46), (1066, 216, 30)]   # Lichthöfe im Gemälde (Laterne, Leuchtfeuer): aus der Clean Plate entfernen
# Taue des Mastboots: im Gemälde zu dünn und kontrastarm für die Differenzmaske. Sie werden aus der Clean Plate
# entfernt und als glatte Linien neu in die Hafen-Ebene gezeichnet (Start, Ende, Durchhang in px).
# Lage zeilenweise an den dunklen Pixeln des Gemäldes gemessen (Taue gehen bei y ~500 vom Mast ab).
ROPES = [((726.5, 499), (703, 552), 1.5), ((732.5, 499), (746, 540), 1.0)]
ROPE_PATHS = [[(727, 497), (725, 505), (722, 515), (718.5, 525), (713.5, 535), (708, 545), (703, 553)],
              [(732, 497), (734, 505), (736, 515), (739, 525), (743, 535), (747, 542)]]
HEAD_FADE = (466, 492)             # Landzunge unten weich in den Dunst auslaufen lassen


def poly_mask(shape, shapes, grow=0, kinds=("poly", "line", "hard", "hardline")):
    m = Image.new("L", (shape[1], shape[0]), 0)
    d = ImageDraw.Draw(m)
    for sh in shapes:
        if sh[0] not in kinds:
            continue
        if sh[0] in ("poly", "hard"):
            d.polygon(sh[1], fill=255)
        else:
            d.line(sh[1], fill=255, width=sh[2], joint="curve")
    if grow > 0:
        m = m.filter(ImageFilter.MaxFilter(2 * grow + 1))
    elif grow < 0:
        m = m.filter(ImageFilter.MinFilter(-2 * grow + 1))
    return np.asarray(m) > 127


def rowfill(img, mask, rng):
    """Maskierte Spannen jeder Zeile linear zwischen den Randfarben (Mittel über 4 px) füllen."""
    out = img.copy()
    h, w, _ = img.shape
    for y in range(h):
        row = mask[y]
        if not row.any():
            continue
        x = 0
        while x < w:
            if not row[x]:
                x += 1
                continue
            x0 = x
            while x < w and row[x]:
                x += 1
            x1 = x                                   # Spanne [x0, x1)
            left = img[y, max(0, x0 - 4):x0].mean(0) if x0 > 0 else None
            right = img[y, x1:min(w, x1 + 4)].mean(0) if x1 < w else None
            if left is None and right is None:      # ganze Zeile verdeckt (unter dem Kai): Zeile darüber
                out[y] = out[y - 1]
                continue
            if left is None:
                left = right
            if right is None:
                right = left
            t = (np.arange(x0, x1) - x0 + 0.5) / max(1, x1 - x0)
            out[y, x0:x1] = left[None] * (1 - t[:, None]) + right[None] * t[:, None]
    return out


def harmonic(img, mask, iters=(1500, 400, 150, 60)):
    """Laplace-Füllung (glatte Interpolation aus allen Richtungen) über eine Bildpyramide.
    img enthält in den maskierten Pixeln bereits eine Startschätzung."""
    def down(a, m):
        h, w = a.shape[:2]
        h2, w2 = (h + 1) // 2, (w + 1) // 2
        ap = np.zeros((h2 * 2, w2 * 2, a.shape[2]), np.float32); ap[:h, :w] = a
        mp = np.ones((h2 * 2, w2 * 2), bool); mp[:h, :w] = m
        known = (~mp).astype(np.float32)
        s = (ap * known[..., None]).reshape(h2, 2, w2, 2, -1).sum((1, 3))
        c = known.reshape(h2, 2, w2, 2).sum((1, 3))
        a2 = np.where(c[..., None] > 0, s / np.maximum(c, 1)[..., None], ap.reshape(h2, 2, w2, 2, -1).mean((1, 3)))
        return a2, c == 0

    def relax(a, m, n):
        for _ in range(n):
            nb = np.zeros_like(a)
            nb[1:] += a[:-1]; nb[:-1] += a[1:]; nb[:, 1:] += a[:, :-1]; nb[:, :-1] += a[:, 1:]
            cnt = np.full(m.shape, 4.0, np.float32)
            cnt[0] -= 1; cnt[-1] -= 1; cnt[:, 0] -= 1; cnt[:, -1] -= 1
            a = np.where(m[..., None], nb / cnt[..., None], a)
        return a

    levels = [(img.astype(np.float32), mask)]
    for _ in range(len(iters) - 1):
        levels.append(down(*levels[-1]))
    a = None
    for (lv, m), n in zip(reversed(levels), iters):
        if a is not None:
            up = np.repeat(np.repeat(a, 2, 0), 2, 1)[:lv.shape[0], :lv.shape[1]]
            lv = np.where(m[..., None], up, lv)
        a = relax(lv, m, n)
    return a


def soft_texture(plate, mask):
    """Gefüllte Flächen bekommen ein schwaches, waagerecht gestrecktes Rauschen (Pinselspur), sonst wirken sie glatt."""
    rng = np.random.default_rng(20261010)
    h, w, _ = plate.shape
    n = rng.normal(0, 1, (h // 4 + 2, w // 16 + 2)).astype(np.float32)
    n = np.asarray(Image.fromarray(n).resize((w, h), Image.BICUBIC))
    m = np.asarray(Image.fromarray((mask * 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(3))) / 255.0
    return plate + (n * 2.2 * m)[..., None]


def fill_holes(alpha_bin, inside):
    """Durchsichtige Stellen, die von außerhalb des Polygons nicht erreichbar sind, werden deckend."""
    free = ~alpha_bin
    reach = free & ~inside
    while True:
        g = reach.copy()
        g[1:] |= reach[:-1]; g[:-1] |= reach[1:]; g[:, 1:] |= reach[:, :-1]; g[:, :-1] |= reach[:, 1:]
        g &= free
        if (g == reach).all():
            return alpha_bin | (free & ~reach)
        reach = g


def bleed(rgb, alpha, n=8):
    known = alpha > 0.5
    rgb = rgb.copy()
    for _ in range(n):
        acc = np.zeros_like(rgb); cnt = np.zeros(alpha.shape, np.float32)
        for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            k = np.roll(known, (dy, dx), (0, 1))
            acc += np.roll(rgb, (dy, dx), (0, 1)) * k[..., None]; cnt += k
        grow = (~known) & (cnt > 0)
        rgb[grow] = acc[grow] / cnt[grow][:, None]
        known |= grow
    return rgb


def to_img(rgb, alpha=None):
    a = np.clip(rgb, 0, 255).astype(np.uint8)
    if alpha is None:
        return Image.fromarray(a, "RGB")
    return Image.fromarray(np.dstack([a, (np.clip(alpha, 0, 1) * 255).astype(np.uint8)]), "RGBA")


def scaled(im):
    return im.resize((round(im.width * SCALE), round(im.height * SCALE)), Image.LANCZOS)


def hard_aa(shape, shapes, ss=4, blur=0.35):
    """Harte Formen kantengeglättet (4-fach überabgetastet, leicht weich). ("hard", pts, schrumpfen_px) schrumpft
    die Form vorher um schrumpfen_px (Lichtsaum des Gemäldes am Rand der Laterne nicht mitnehmen)."""
    acc = np.zeros((shape[0] * ss, shape[1] * ss), np.uint8)
    for sh in shapes:
        if sh[0] not in ("hard", "hardline"):
            continue
        m = Image.new("L", (shape[1] * ss, shape[0] * ss), 0)
        d = ImageDraw.Draw(m)
        if sh[0] == "hard":
            d.polygon([(x * ss + ss / 2, y * ss + ss / 2) for x, y in sh[1]], fill=255)
            if len(sh) > 2 and sh[2] > 0:
                m = m.filter(ImageFilter.MinFilter(2 * round(sh[2] * ss) + 1))
        else:
            d.line([(x * ss + ss / 2, y * ss + ss / 2) for x, y in sh[1]], fill=255, width=sh[2] * ss)
        acc = np.maximum(acc, np.asarray(m))
    m = Image.fromarray(acc)
    if blur:
        m = m.filter(ImageFilter.GaussianBlur(blur * ss))
    return np.asarray(m.resize((shape[1], shape[0]), Image.BOX)) / 255.0


def soft_aa(shape, shapes, ss=4, blur=0.45):
    """Formen 4-fach überabgetastet, leicht weichgezeichnet (blur in Ziel-px), als Alpha 0..1.
    ("poly", pts) und ("tight", pts, schrumpfen_px) als Flächen, ("line", pts, breite) als Linie."""
    m = Image.new("L", (shape[1] * ss, shape[0] * ss), 0)
    d = ImageDraw.Draw(m)
    for sh in shapes:
        pts = [(x * ss + ss / 2, y * ss + ss / 2) for x, y in sh[1]]
        if sh[0] in ("poly", "tight"):
            d.polygon(pts, fill=255)
        elif sh[0] == "line":
            d.line(pts, fill=255, width=round(sh[2] * ss), joint="curve")
    if blur:
        m = m.filter(ImageFilter.GaussianBlur(blur * ss))
    return np.asarray(m.resize((shape[1], shape[0]), Image.BOX)) / 255.0


def layer_alpha(master, plate, shapes, lo=18.0, hi=34.0, box=None, box_shapes=None):
    inside = poly_mask(master.shape, shapes, kinds=("poly", "line"))
    core = poly_mask(master.shape, shapes, grow=-5, kinds=("poly", "line"))
    hard = hard_aa(master.shape, shapes)
    near_hard = poly_mask(master.shape, shapes, grow=5, kinds=("hard", "hardline"))
    d = np.abs(master - plate).max(-1)
    a = np.clip((d - lo) / (hi - lo), 0, 1) * inside
    a[near_hard] = 0                       # Lichtschein des Gemäldes rund um Laterne/Leuchtfeuer nicht mitnehmen
    a = np.maximum(a, core.astype(np.float32))
    filled = fill_holes(a > 0.5, inside)
    a = np.where(filled & (a <= 0.5), 1.0, a)
    a = np.asarray(Image.fromarray((a * 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(0.6))) / 255.0
    a = a * inside
    if box is not None:
        x0, y0, x1, y1 = box
        a[y0:y1, x0:x1] = soft_aa(master.shape, box_shapes)[y0:y1, x0:x1]
    tight = [sh for sh in shapes if sh[0] == "tight"]
    if tight:
        a = np.maximum(a, soft_aa(master.shape, tight, blur=0.5))
    return np.maximum(a, hard)


def draw_ropes(im, ss=4):
    """Taue als leicht durchhängende, kantengeglättete Linien in die Hafen-Ebene zeichnen."""
    lay = Image.new("RGBA", (im.width * ss, im.height * ss), (0, 0, 0, 0))
    d = ImageDraw.Draw(lay)
    for (x0, y0), (x1, y1), sag in ROPES:
        pts = []
        for i in range(25):
            t = i / 24
            pts.append(((x0 + (x1 - x0) * t) * ss, (y0 + (y1 - y0) * t + sag * 4 * t * (1 - t)) * ss))
        d.line(pts, fill=(52, 56, 58, 235), width=int(1.7 * ss), joint="curve")
    lay = lay.resize(im.size, Image.LANCZOS)
    out = im.copy()
    out.alpha_composite(lay)
    return out


def horizon_row(master):
    g = np.abs(np.diff(master[380:430, 480:820].mean(-1), axis=0)).mean(1)
    return 380 + int(np.argmax(g)) + 1


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    master = np.asarray(Image.open(RAW).convert("RGB")).astype(np.float32)
    h, w, _ = master.shape
    hz = horizon_row(master)
    mh = poly_mask(master.shape, HARBOUR, grow=2)
    mk = poly_mask(master.shape, HEADLAND, grow=2)
    yy, xx = np.mgrid[0:h, 0:w]
    glow = np.zeros((h, w), bool)
    for cx, cy, r in GLOWS:
        glow |= (xx - cx) ** 2 + (yy - cy) ** 2 < r * r
    rope = poly_mask(master.shape, [("line", pth, 11) for pth in ROPE_PATHS])
    mast = poly_mask(master.shape, [("line", [(729.5, 462), (729.5, 552)], 12)])
    pole = poly_mask(master.shape, [("poly", [(395, 428), (414, 428), (414, 556), (395, 556)])], grow=2)
    hole = mh | mk | glow | rope | mast | pole
    plate = rowfill(master, hole, None)
    # Unter der Landzunge (Meereszeilen): senkrecht vom ersten freien Pixel darunter (Dunst) nach oben auffüllen
    for x in range(w):
        col = mk[:, x] & (np.arange(h) >= hz)
        if col.any():
            yb = np.flatnonzero(col).max() + 1
            if yb < h:
                plate[hz:yb, x][col[hz:yb]] = master[yb, x]
    # Wasser zwischen Steg, Booten und Kai: aus allen Richtungen glatt füllen (Meereszeilen ab 8 px unter dem
    # Horizont bis zur Kaikante), damit die Differenzmaske nur Holz und Taue findet, nicht Wasser
    band = np.zeros((h, w), bool); band[hz + 8:600] = True
    sub = slice(hz + 8 - 20, 640)
    hm = (hole & band)[sub]
    plate[sub] = harmonic(plate[sub], hm)
    plate = soft_texture(plate, hole)

    a_h = layer_alpha(master, plate, HARBOUR, box=BOATS_BOX, box_shapes=BOATS)
    a_k = layer_alpha(master, plate, HEADLAND)
    fade = np.clip((HEAD_FADE[1] - yy) / (HEAD_FADE[1] - HEAD_FADE[0]), 0, 1)
    a_k = a_k * fade

    h_rgb = bleed(master, a_h)
    # Randstreifen der harten Formen (Laterne, Arm, Strebe): im Gemälde liegt dort ein heller Lichtsaum; die
    # Farbe dort durch die dunkelste Farbe der 3x3-Nachbarschaft ersetzen
    hard_m = hard_aa(master.shape, HARBOUR) > 0.02
    inner = np.asarray(Image.fromarray((hard_aa(master.shape, HARBOUR) > 0.5).astype(np.uint8) * 255)
                       .filter(ImageFilter.MinFilter(3))) > 0
    band_m = hard_m & ~inner
    darkest = np.dstack([np.asarray(Image.fromarray(master[..., c].astype(np.uint8)).filter(ImageFilter.MinFilter(3)))
                         for c in range(3)]).astype(np.float32)
    h_rgb[band_m] = np.minimum(h_rgb[band_m], darkest[band_m])
    h_rgba = to_img(h_rgb, a_h)
    h_rgba = draw_ropes(h_rgba)
    files = {}
    files["plate"] = scaled(to_img(plate))
    files["harbour"] = scaled(h_rgba)
    files["headland"] = scaled(to_img(bleed(master, a_k), a_k))
    for k, im in files.items():
        im.save(OUT / f"{k}.png", optimize=True)
        print(k, im.size)
    meta = {"scale": SCALE, "y_off": Y_OFF, "horizon_raw": hz, "horizon_screen": round(hz * SCALE - Y_OFF, 1),
            "size_raw": [w, h], "size": list(files["plate"].size)}
    (OUT / "layers.json").write_text(json.dumps(meta, indent=1))
    print(meta)
    # Seit 12.10. nutzt die Demo die getrennt erzeugten Ebenen (build_sep_layers.py); diese Fassung bleibt nur
    # als Vergleich in assets/layers/ und wird nicht mehr nach demo/art/ kopiert.


if __name__ == "__main__":
    main()
