#!/usr/bin/env python3
"""Dachs-Sprites in 1 Bit aus dem KI-Figurenblatt (gpt-image, über die Blender-Posen gezeichnet).

Das Blatt hat 8 Laufbilder (oben) und 4 Stehbilder (unten); das Modell zeichnet viel feiner als verlangt
(Kunstpixel ≈ 2,4 Bildpixel, Figur ≈ 113 statt 56 Kunstpixel hoch) und die untere Reihe 14 % größer.
Deshalb je Reihe ein eigener Maßstab auf FIG_H Zielpixel und je Zielpixel gemessen statt abgetastet
(MODE "majority", verwendet): deckend ab 50 % Alpha, nur die größte Fläche; je Bildpixel 5×5-Mittel
(löscht das Schachbrett des Modells) auf die Stufen 0/4/8/12/16, je Zielpixel die häufigste Stufe →
Bayer-Muster im Sprite-Raster (das Muster wandert mit der Figur). MODE "structure" (erster Versuch, zu dunkel):
dicke schwarze/weiße Flächen per Öffnen 3×3 und Schwellen.
Dann der Kopf als festes Teil (assemble): Stehbild 1 mit Korrekturen (HEAD_FIX, CAP_SHINE) in alle Bilder
gesetzt, Blinzeln und Sprechen als Kopfvarianten. Zuletzt der Kontrastrand: jeder durchsichtige
Nachbarpixel eines deckenden Pixels wird zur Gegenfarbe (an Schwarz ein Papierpixel, an Weiß ein Tintenpixel),
damit die Figur vor hellem wie dunklem Grund steht.

Ausrichtung: Grundlinie = unterste deckende Zeile der Reihe (Füße), waagrecht der Ursprung der Blender-Pose
(Zellmitte). Ausgabe: demo/art/badger_walk.png (8 Bilder nebeneinander), badger_idle.png (4 Bilder),
badger.json (Bildgröße, Ursprung, gemessene Füße je Bild).

    .venv/bin/python styles/einbit-pixel/scripts/build_badger.py
"""
import json, pathlib, sys

import numpy as np
from PIL import Image

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import onebit as ob  # noqa: E402

ROOT = pathlib.Path(__file__).resolve().parents[1]
FIG_H = 62                 # Zielhöhe der Figur (Mütze bis Sohle) in Pixeln
FW, FH = 56, FIG_H + 4     # Bildgröße je Sprite (mit Rand)
OX, OY = 28, FIG_H + 2     # Ursprung im Sprite: Mitte zwischen den Füßen, Unterkante der Sohle
ROWS = [  # (y0, y1, Anzahl, Grundlinie im Blatt, Figurenhöhe im Blatt)
    (60, 500, 8, 420, 274),
    (520, 1000, 4, 891, 312),
]
INK, PAPER, CLEAR = 0, 255, None
WHITE_MIN, BLACK_MIN = 0.45, 0.5   # Anteil dicker weißer bzw. schwarzer Fläche je Zielpixel
MODE = "majority"          # "majority": häufigste Stufe je Zielpixel; "structure": Öffnen + Schwellen
PAD = 200                  # Rand, damit Quellrechtecke über den Blattrand reichen dürfen


def main():
    a = np.asarray(Image.open(ROOT / "assets" / "raw" / "badger.png").convert("RGBA")).astype(np.float64)
    alpha = a[..., 3] >= 128
    L = (a[..., :3] @ [0.299, 0.587, 0.114]) / 255
    blk = ob.opening(alpha & (L < 0.4), 3)
    wht = ob.opening(alpha & (L > 0.6), 3)
    Lm = ob.box_mean(np.where(alpha, L, 0), 5) / np.maximum(ob.box_mean(alpha.astype(float), 5), 1e-6)
    # Stufe je Bildpixel: Mittel über 5×5 (löscht das Schachbrett des Modells), auf 0/4/8/12/16
    lab = np.where(alpha, np.clip(((Lm - 0.1) / 0.8 * 4).round(), 0, 4), -1).astype(int)
    sheets, meta = [], {"frame": [FW, FH], "origin": [OX, OY], "fig_h": FIG_H, "rows": []}
    for (y0, y1, n, base, fig_h) in ROWS:
        s = FIG_H / fig_h                     # Zielpixel je Bildpixel
        cw = 1536 / n
        frames = []
        for i in range(n):
            cx = cw * (i + 0.5)
            # Quellrechteck, das genau auf das FW×FH-Raster fällt
            sx0, sy0 = cx - OX / s, base + 1 - OY / s
            sx1, sy1 = sx0 + FW / s, sy0 + FH / s
            box = tuple(int(round(v)) + PAD for v in (sx0, sy0, sx1, sy1))
            crop = lambda m: np.pad(m, PAD)[box[1]:box[3], box[0]:box[2]]
            ca = ob.cell_mean(crop(alpha), FW, FH)
            opaque = largest_component(ca >= 0.5)
            if MODE == "majority":
                covs = np.stack([ob.cell_mean(crop(lab == k), FW, FH) for k in range(5)], -1)
                lev = np.array([0, 4, 8, 12, 16])[covs.argmax(-1)]
            else:
                cb = ob.cell_mean(crop(blk), FW, FH) / np.maximum(ca, 1e-6)
                cwt = ob.cell_mean(crop(wht), FW, FH) / np.maximum(ca, 1e-6)
                tone = ob.cell_mean(crop(Lm * alpha), FW, FH) / np.maximum(ca, 1e-6)
                lev = np.array([4, 8, 12])[np.clip(((tone - 0.25) / 0.25).round().astype(int), 0, 2)]
                lev = np.where(cwt >= WHITE_MIN, 16, lev)
                lev = np.where((cb >= BLACK_MIN) & (cwt < WHITE_MIN), 0, lev)
            px = np.where(ob.render(lev, ob.BAYER), PAPER, INK).astype(np.uint8)
            frames.append((opaque, px))
        sheets.append(frames)
        meta["rows"].append({"scale": s, "frames": n})
    sheets, meta["head"] = assemble(sheets)
    out = ROOT / "demo" / "art"
    out.mkdir(parents=True, exist_ok=True)
    for name, frames in (("badger_walk", sheets[0]), ("badger_idle", sheets[1])):
        strip = np.concatenate(frames, axis=1)
        Image.fromarray(strip, "RGBA").save(out / f"{name}.png")
        Image.fromarray(strip, "RGBA").save(ROOT / "assets" / f"{name}.png")
    meta["feet"] = {"walk": [feet(f) for f in sheets[0]], "idle": [feet(f) for f in sheets[1]]}
    (out / "badger.json").write_text(json.dumps(meta, indent=1))
    for k, v in meta["feet"].items():
        print(k, v)


# Kopf als festes Teil (aus Stehbild 1 des Modells): Korrekturen in Sprite-Koordinaten.
HEAD_ROWS = (0, 15)          # Zeilen, die vollständig vom Kopfteil ersetzt werden
HEAD_COLS = (14, 52)
HEAD_FIX = [  # (x, y, Wert) – Mützenband als durchgehende helle Linie, Auge freigestellt
    *[(x, 7, PAPER) for x in range(29, 37)],
    (36, 10, INK), (34, 10, INK), (33, 11, INK), (35, 11, PAPER), (34, 11, INK), (36, 11, INK),
]
CAP_SHINE = [(3, 4, 9), (4, 2, 3)]     # (Zeile, von, bis) relativ zum ersten schwarzen Pixel der Zeile
EYE = (35, 11)
MOUTH = [(32, 15), (33, 15), (34, 15), (33, 16), (34, 16)]      # geöffneter Mund (Tinte)

# Paket als festes Teil (wie der Kopf): Das Modell zeichnete einen weißen Kasten mit Schnurkreuz, über den der
# schwarze Unterarm schräg läuft; auf 62 px zerfiel das in zwei weiße Flecken (S-Form). Deshalb: im Bereich
# PARCEL_ERASE alle Papierpixel zu Tinte (Fell), dann ein von Hand gesetzter Kasten (Vorderseite mit
# Schnurkreuz, Deckel, rechte Seite) unter dem Unterarm; die Papierlinie oben links ist die Unterkante des
# Unterarms, die schwarze Kerbe oben rechts die Pfote. Koordinaten für Stehbild 0, je Bild um den Versatz des
# Kopfteils verschoben. '#' Tinte, '.' Papier, ' ' unverändert.
PARCEL_ERASE = (22, 34, 37, 47)
PARCEL_AT = (21, 32)
PARCEL_ART = """
  .
   .
    .
     .
      .  #
  #######  #
 #....#...##
#....#....#.#
###########.#
#....#....#.#
#....#....#.#
#....#....#.#
#....#....##
###########
"""
# 1-px-Papierlinie zwischen den Beinen je Laufbild (x, y im Sprite), von Hand aus den Fußläufen gesetzt:
# setzt die Lücke zwischen den Füßen nach oben bis in den Schritt fort bzw. trennt im Durchgang das
# gehobene Bein vom Standbein. Nur Tintenpixel innerhalb der Figur werden zu Papier.
LEG_LINES = {
    0: [(30, 55), (30, 56), (30, 57)],
    1: [(28, 56), (28, 57), (28, 61), (28, 62)],
    2: [(26, 55), (26, 56), (26, 57), (26, 58)],
    3: [(31, 56), (31, 57), (31, 58), (31, 59)],
    4: [(29, 56), (29, 57), (31, 62)],
    5: [(28, 55), (28, 56), (28, 60), (28, 61), (28, 62)],
    6: [(25, 56), (25, 57), (25, 58)],
    7: [(31, 56), (31, 57), (31, 58), (31, 59)],
}


def best_offset(master, frame, rows):
    """Versatz (dx, dy), bei dem das Kopfteil am besten auf den Kopf des Bildes passt."""
    mo, mp = master
    fo, fp = frame
    best = None
    for dy in range(-3, 4):
        for dx in range(-4, 5):
            err = 0
            for y in range(rows[0], rows[1]):
                yy = y + dy
                if not 0 <= yy < FH:
                    continue
                a_o = mo[y]
                b_o = np.roll(fo[yy], -dx)
                b_p = np.roll(fp[yy], -dx)
                err += int((a_o != b_o).sum()) + int(((mp[y] != b_p) & a_o & b_o).sum())
            if best is None or err < best[0]:
                best = (err, dx, dy)
    return best[1], best[2]


def paste_head(head, frame, dx, dy):
    ho, hp = head
    fo, fp = frame[0].copy(), frame[1].copy()
    for y in range(FH):
        yy = y + dy
        if not 0 <= yy < FH:
            continue
        for x in range(HEAD_COLS[0], HEAD_COLS[1]):
            xx = x + dx
            if not 0 <= xx < FW:
                continue
            if y <= HEAD_ROWS[1]:
                fo[yy, xx] = ho[y, x]
                if ho[y, x]:
                    fp[yy, xx] = hp[y, x]
            elif ho[y, x] and y <= HEAD_ROWS[1] + 3:
                fo[yy, xx] = True
                fp[yy, xx] = hp[y, x]
    return fo, fp


def paste_parcel(frame, dx, dy):
    """Paket-Teil (PARCEL_ART) mit Versatz setzen; vorher die Paketreste des Modells im Bereich PARCEL_ERASE
    zu Tinte machen."""
    fo, fp = frame[0].copy(), frame[1].copy()
    x0, y0, x1, y1 = PARCEL_ERASE
    sub_o = fo[y0 + dy:y1 + 1 + dy, x0 + dx:x1 + 1 + dx]
    sub_p = fp[y0 + dy:y1 + 1 + dy, x0 + dx:x1 + 1 + dx]
    sub_p[sub_o & (sub_p == PAPER)] = INK
    for r, line in enumerate(PARCEL_ART.strip("\n").split("\n")):
        for k, ch in enumerate(line):
            if ch == " ":
                continue
            y, x = PARCEL_AT[1] + r + dy, PARCEL_AT[0] + k + dx
            fo[y, x] = True
            fp[y, x] = INK if ch == "#" else PAPER
    return fo, fp


def leg_line(rgba, pts):
    """Nach dem Kontrastrand anwenden (sonst macht der Rand ein Loch neben der Linie zu Tinte)."""
    rgba = rgba.copy()
    for x, y in pts:
        if rgba[y, x, 3] and rgba[y, x, 0] == INK:
            rgba[y, x, :3] = PAPER
    return rgba


def assemble(sheets):
    """Kopfteil aus Stehbild 1 (korrigiert) in alle Bilder setzen, Blinzeln und Sprechen als Kopfvarianten.
    Ausgabe: Laufbilder 1–8; Stehbilder: 0 Stand, 1 Blinzeln (Körper von 0), 2 Gruß mit offenem Mund
    (Körper Modellbild 3), 3 Gruß mit geschlossenem Mund."""
    walk, idle = sheets
    ho, hp = idle[0][0].copy(), idle[0][1].copy()
    for x, y, v in HEAD_FIX:
        hp[y, x] = v
        ho[y, x] = True
    # Glanzlicht auf der Mützenkuppel (Licht von links oben): kurze Papierlinie in Zeile 3, Ansatz in Zeile 4
    for y, a, b in CAP_SHINE:
        xs = np.where(ho[y] & (hp[y] == INK))[0]
        for x in range(xs.min() + a, xs.min() + b + 1):
            hp[y, x] = PAPER
    head = (ho, hp)
    blink = (ho, hp.copy())
    blink[1][EYE[1], EYE[0]] = INK
    talk = (ho, hp.copy())
    for x, y in MOUTH:
        talk[1][y, x] = INK
    info = {"walk": [], "idle": []}
    out_walk = []
    for i, f in enumerate(walk):
        dx, dy = best_offset(head, f, (0, 12))
        fr = paste_parcel(paste_head(head, f, dx, dy), dx, dy)
        out_walk.append(fr)
        info["walk"].append([dx, dy])
    stand = paste_parcel(paste_head(head, idle[0], 0, 0), 0, 0)
    dx2, dy2 = best_offset(head, idle[2], (0, 12))
    out_idle = [stand, paste_parcel(paste_head(blink, idle[0], 0, 0), 0, 0),
                paste_parcel(paste_head(talk, idle[2], dx2, dy2), dx2, dy2),
                paste_parcel(paste_head(head, idle[2], dx2, dy2), dx2, dy2)]
    info["idle"] = [[0, 0], [0, 0], [dx2, dy2], [dx2, dy2]]
    rim = lambda fs: [contrast_rim(o, p) for o, p in fs]
    walk_rgba = [leg_line(f, LEG_LINES[i]) for i, f in enumerate(rim(out_walk))]
    return [walk_rgba, rim(out_idle)], info


def largest_component(m):
    """Nur die größte 4-zusammenhängende Fläche behalten (Schalenden der Nachbarbilder ragen herein)."""
    lab = np.zeros(m.shape, int)
    best, best_n, cur = 0, 0, 0
    for y, x in zip(*np.where(m)):
        if lab[y, x]:
            continue
        cur += 1
        stack, n = [(y, x)], 0
        lab[y, x] = cur
        while stack:
            cy, cx = stack.pop()
            n += 1
            for ny, nx in ((cy + 1, cx), (cy - 1, cx), (cy, cx + 1), (cy, cx - 1)):
                if 0 <= ny < m.shape[0] and 0 <= nx < m.shape[1] and m[ny, nx] and not lab[ny, nx]:
                    lab[ny, nx] = cur
                    stack.append((ny, nx))
        if n > best_n:
            best, best_n = cur, n
    return lab == best


def contrast_rim(opaque, px):
    """RGBA-Sprite: deckende Pixel in Tinte/Papier, außen 1 px Gegenfarbe zum Nachbarn."""
    h, w = opaque.shape
    rgba = np.zeros((h, w, 4), np.uint8)
    rgba[opaque, :3] = px[opaque, None]
    rgba[opaque, 3] = 255
    p_op = np.pad(opaque, 1)
    p_px = np.pad(px, 1).astype(int)
    rim_ink = np.zeros((h, w), bool)
    rim_paper = np.zeros((h, w), bool)
    for dy, dx in ((-1, 0), (1, 0), (0, -1), (0, 1)):
        nb_op = p_op[1 + dy:1 + dy + h, 1 + dx:1 + dx + w]
        nb_px = p_px[1 + dy:1 + dy + h, 1 + dx:1 + dx + w]
        rim_ink |= ~opaque & nb_op & (nb_px == PAPER)
        rim_paper |= ~opaque & nb_op & (nb_px == INK)
    rim_paper &= ~rim_ink            # an Weiß gewinnt die Tintenkontur
    for m, v in ((rim_ink, INK), (rim_paper, PAPER)):
        rgba[m, :3] = v
        rgba[m, 3] = 255
    return rgba


def feet(rgba):
    """Unterste deckende Zeile der Figur (ohne Rand) und die x-Spannen der Bodenpixel."""
    op = rgba[..., 3] > 0
    ys = np.where(op.any(1))[0]
    bottom = int(ys.max())
    xs = np.where(op[bottom])[0]
    return {"bottom": bottom, "x": [int(xs.min()), int(xs.max())], "top": int(ys.min())}


if __name__ == "__main__":
    main()
