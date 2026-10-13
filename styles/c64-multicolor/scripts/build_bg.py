#!/usr/bin/env python3
"""KI-Hintergrund -> Multicolor-Bitmap 160x144 nach den Regeln des Videochips.

Ablauf:
  1. Ausschnitt des KI-Bildes (volle Breite, 691 Zeilen ab y=150) auf 160x144 Doppelpixel: je Zielpixel die
     häufigste Palettenfarbe (Oklab) im Quellblock (Rand des Blocks ausgelassen).
  2. Retusche: Schornsteinaufsatz weg (Platz für Rauch-Sprites), Laterne mit 2 Doppelpixel breitem Glas,
     Leuchtfeuer als eigene Pixelgruppen (Lampe und Glas), Sterne.
  3. Rasterzeilen-Tabelle: Hintergrundfarbe ($D021) je Zeile. Himmel als Balken mit verzahnten Übergängen
     (A B A B), Wasser blau, Kai nach häufigster Farbe der Zeile.
  4. Himmel säubern: Bandfarben werden zu Hintergrund (Bitpaar 00), Wolken (Läufe >= 3 Pixel in fremder Farbe)
     bleiben, Dither-Krümel aus dem KI-Bild verschwinden.
  5. Zellregel: je 4x8-Zelle höchstens 3 eigene Farben neben der Zeilen-Hintergrundfarbe. Reservierte Gruppen
     (Wasserglitzern a/b, Leuchtfeuer-Lampe und -Glas, Laternenglas, Sterne) belegen je einen Platz, dessen Farbe die Demo jedes
     Bild neu setzt (Farbzyklus im Bildschirm- bzw. Farbspeicher). Für die übrigen Farben wird die Kombination
     mit dem kleinsten Oklab-Fehler gewählt (erschöpfend).
  6. Ausgabe: assets/bg_build.npz (Bitpaare, Bildschirm-/Farbspeicher, Rastertabelle, Animationsliste) und
     assets/bg_preview.png (320x144, Doppelpixel, Glitzern in Phase 0).
"""
import itertools, json, sys

import numpy as np
from PIL import Image

sys.path.insert(0, str(__import__("pathlib").Path(__file__).parent))
from c64lib import *  # noqa

SRC = ROOT / "assets/raw/bg.png"
Y0, SRC_H = 150, 691          # Quellausschnitt (volle Breite 1536)
W, H = 160, 144                # Doppelpixel x Zeilen (18 Zellzeilen)
HORIZON = 58                   # erste Wasserzeile (hellblaue Horizontlinie)
QUAY = 128                     # erste Kaizeile
BG_PENALTY = 3.0               # Zellregel: Pixel nur ungern auf die Zeilen-Hintergrundfarbe abbilden (Löcher)

# Gruppen (reservierte Plätze)
G_NONE, G_GLIT_A, G_GLIT_B, G_LAMP, G_LANTERN, G_STAR, G_GLASS = 0, 1, 2, 3, 4, 5, 6
GROUP_NAMES = {G_GLIT_A: "glitter_a", G_GLIT_B: "glitter_b", G_LAMP: "lamp", G_LANTERN: "lantern", G_STAR: "star",
               G_GLASS: "lamp_glass"}
STARS = [(4, 1), (27, 3), (52, 1), (66, 4), (83, 2), (97, 7), (112, 3), (126, 1), (138, 5), (90, 12), (118, 10),
         (9, 6), (36, 12)]
BOATS = [(48, 74, 84, 112), (90, 112, 98, 109)]     # x0, x1, y0, y1: kein Glitzern auf den Booten


def reduce_source():
    im = np.asarray(Image.open(SRC).convert("RGB")).astype(np.float64)
    crop = im[Y0:Y0 + SRC_H]
    q = nearest(crop.reshape(-1, 3)).reshape(crop.shape[:2])
    ys = np.linspace(0, crop.shape[0], H + 1).astype(int)
    xs = np.linspace(0, crop.shape[1], W + 1).astype(int)
    out = np.zeros((H, W), int)
    for j in range(H):
        for i in range(W):
            b = q[ys[j] + 1:ys[j + 1] - 1, xs[i] + 2:xs[i + 1] - 2]
            out[j, i] = np.bincount(b.ravel(), minlength=16).argmax()
    return out


def apply_patches(q, line_bg):
    """scripts/patches.txt anwenden ("." behalten, "_" = Hintergrundfarbe der Zeile, sonst Farbnummer)."""
    name, x0, y = None, 0, 0
    for raw in (ROOT / "scripts/patches.txt").read_text().splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("@"):
            name, xs, ys = line[1:].split()
            x0, y = int(xs), int(ys)
            continue
        for i, ch in enumerate(line):
            if ch == ".":
                continue
            q[y, x0 + i] = int(line_bg[y]) if ch == "_" else int(ch, 16)
        y += 1


def runs_of(row):
    """Lauflänge je Pixel (Länge des gleichfarbigen waagerechten Laufs, zu dem es gehört)."""
    n = len(row)
    out = np.zeros(n, int)
    s = 0
    for x in range(1, n + 1):
        if x == n or row[x] != row[s]:
            out[s:x] = x - s
            s = x
    return out


def main():
    q = reduce_source()
    ai_mode = np.array([np.bincount(q[y], minlength=16).argmax() for y in range(H)])
    group = np.zeros((H, W), int)

    # --- Retusche -------------------------------------------------------------------------------
    apply_patches(q, ai_mode)
    # Laterne: Haken, Kappe, 2 px breites Glas, Boden (x 116-119, Zeilen 80-95)
    q[78:97, 115:121] = np.where(np.isin(q[78:97, 115:121], [BLACK, DGREY, YELLOW, GREY]), BLUE, q[78:97, 115:121])
    q[79:82, 117] = BLACK
    q[82:84, 116:120] = BLACK
    for y in range(84, 94):
        q[y, 116] = BLACK; q[y, 119] = BLACK
        q[y, 117:119] = YELLOW
        group[y, 117:119] = G_LANTERN
    q[94:96, 116:120] = BLACK
    q[96, 117:119] = BLACK
    # Leuchtfeuer: Lampe 2x3 Doppelpixel mittig über dem Turm, beidseits Glas (patches.txt @lighthouse)
    group[4:7, 151:153] = G_LAMP
    group[4:7, 150] = G_GLASS
    group[4:7, 153] = G_GLASS

    # --- Rastertabelle (Hintergrundfarbe je Zeile) ------------------------------------------------
    bg = ai_mode.copy()
    bg[0:2] = BLUE; bg[2] = PURPLE; bg[3] = BLUE; bg[4:17] = PURPLE
    bg[17] = LRED; bg[18] = PURPLE; bg[19] = LRED; bg[20:49] = LRED
    bg[49] = YELLOW; bg[50] = LRED; bg[51] = YELLOW; bg[52:HORIZON] = YELLOW
    bg[HORIZON] = LBLUE
    bg[HORIZON + 1:QUAY] = BLUE

    # --- Himmel säubern ---------------------------------------------------------------------------
    band = {BLUE, PURPLE, LRED, YELLOW}
    for y in range(HORIZON):
        rl = runs_of(q[y])
        for x in range(W):
            c = q[y, x]
            if group[y, x]:
                continue
            if c in band:
                cloud = c != ai_mode[y] and rl[x] >= 3 and y not in (17, 18, 19)
                if not cloud:
                    q[y, x] = bg[y]
            elif 36 <= x < 140 and rl[x] <= 2:      # einzelne Krümel im freien Himmel
                q[y, x] = bg[y]
    for x, y in STARS:
        if q[y, x] == bg[y]:
            q[y, x] = WHITE
            group[y, x] = G_STAR
    # Horizontlinie: hellblau über die ganze Breite, wo Wasser ist
    for x in range(W):
        if q[HORIZON, x] in (LBLUE, CYAN, BLUE, YELLOW):
            q[HORIZON, x] = LBLUE

    # --- Wasserglitzern ---------------------------------------------------------------------------
    boat = np.zeros((H, W), bool)
    for x0, x1, y0, y1 in BOATS:
        boat[y0:y1, x0:x1] = True
    for y in range(HORIZON + 1, QUAY):
        rl = runs_of(q[y])
        for x in range(W):
            c = q[y, x]
            near_water = any(q[y, xx] == BLUE for xx in range(max(0, x - 3), min(W, x + 4)))
            if (c in (LBLUE, CYAN, YELLOW, WHITE, LGREY) and rl[x] <= 8 and not boat[y, x] and not group[y, x]
                    and near_water and x >= 34):
                group[y, x] = G_GLIT_A if (y // 3 + x // 6) % 2 == 0 else G_GLIT_B

    # --- Zellregel --------------------------------------------------------------------------------
    lab = PAL_LAB
    pairs = np.zeros((200, W), np.uint8)
    screen = np.zeros(1000, np.uint8)
    color = np.zeros(1000, np.uint8)
    anim = []           # [Zelle, Platz (1=Bildschirm oben, 2=Bildschirm unten, 3=Farbspeicher), Gruppe]
    out = np.zeros((H, W), int)
    changed = 0
    slot_order = [3, 1, 2]
    for cy in range(H // 8):
        for cx in range(W // 4):
            ys, xs = slice(cy * 8, cy * 8 + 8), slice(cx * 4, cx * 4 + 4)
            blk, grp, lbg = q[ys, xs], group[ys, xs], bg[ys]
            groups = sorted({int(g) for g in grp.ravel() if g})
            if len(groups) > 3:
                raise SystemExit(f"Zelle {cx},{cy}: zu viele Gruppen {groups}")
            # Glitzern teilen sich einen Platz, wenn sonst Farben verloren gingen
            normal = blk[(grp == 0) & (blk != lbg[:, None])]
            ncol = len(set(normal.tolist()))
            if G_GLIT_A in groups and G_GLIT_B in groups and ncol + len(groups) > 3:
                grp = np.where(grp == G_GLIT_B, G_GLIT_A, grp)
                groups.remove(G_GLIT_B)
            free = 3 - len(groups)
            cand = sorted(set(normal.tolist()), key=lambda c: -(normal == c).sum())
            best, best_err = tuple(cand[:free]), None
            if len(cand) > free:
                best_err = 1e18
                for combo in itertools.combinations(cand[:8], free):
                    err = 0.0
                    for r in range(8):
                        allowed = [lbg[r], *combo]
                        for v, g in zip(blk[r], grp[r]):
                            if g or v == lbg[r]:
                                continue
                            d = ((lab[v] - lab[allowed]) ** 2).sum(-1)
                            d[0] *= BG_PENALTY
                            err += d.min()
                    if err < best_err:
                        best, best_err = combo, err
            # Plätze vergeben: Gruppen zuerst (Farbspeicher, dann Bildschirm oben/unten)
            slots = {}
            for g, s in zip(groups, slot_order):
                slots[("g", g)] = s
            rest = [s for s in slot_order if s not in slots.values()]
            for c, s in zip(best, rest):
                slots[("c", c)] = s
            regs = {1: 0, 2: 0, 3: 0}
            ci = cy * 40 + cx
            for key, s in slots.items():
                if key[0] == "c":
                    regs[s] = key[1]
                else:
                    gpx = blk[grp == key[1]]
                    regs[s] = int(np.bincount(gpx, minlength=16).argmax())
                    anim.append([ci, s, key[1]])
            for r in range(8):
                y = cy * 8 + r
                for i in range(4):
                    x = cx * 4 + i
                    v, g = blk[r, i], grp[r, i]
                    if g:
                        s = slots[("g", g)]
                        pairs[y, x] = s; out[y, x] = regs[s]
                        continue
                    if v == lbg[r]:
                        pairs[y, x] = 0; out[y, x] = v
                        continue
                    if ("c", v) in slots:
                        s = slots[("c", v)]
                        pairs[y, x] = s; out[y, x] = v
                        continue
                    opts = [(0, lbg[r])] + [(slots[("c", c)], c) for c in best]
                    d = [((lab[v] - lab[c]) ** 2).sum() * (BG_PENALTY if s == 0 else 1) for s, c in opts]
                    s, c = opts[int(np.argmin(d))]
                    pairs[y, x] = s; out[y, x] = c
                    changed += 1
            screen[ci] = (regs[1] << 4) | regs[2]
            color[ci] = regs[3]

    # Leuchtfeuer-/Laternen-/Sternplätze: Grundfarbe für das Vorschaubild
    np.savez_compressed(ROOT / "assets/bg_build.npz", pairs=pairs, screen=screen, color=color, raster=bg,
                        anim=np.array(anim, int), q=q, out=out, group=group)
    prev = to_rgb(np.repeat(out, 2, axis=1)).astype(np.uint8)
    Image.fromarray(prev).save(ROOT / "assets/bg_preview.png")
    stats = {"cells": 720, "pixels_changed_by_cell_rule": changed, "anim_slots": len(anim),
             "raster_changes": int((np.diff(bg) != 0).sum()),
             "colours": sorted({int(c) for c in np.unique(out)})}
    print(json.dumps(stats, ensure_ascii=False))


if __name__ == "__main__":
    main()
