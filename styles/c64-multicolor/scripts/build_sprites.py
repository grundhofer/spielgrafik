#!/usr/bin/env python3
"""Sprites für die Demo: Dachs-Kurier (aus scripts/badger_sprites.txt), Möwe, Rauch, Leuchtfeuer-Strahl.

Jede Figur wird in Hardware-Sprites (24x21) zerlegt:
  Dachs je Bild: schwarzes Hires-Sprite oben/unten (Kontur), hellrotes und oranges Hires-Sprite (Schal, Paket/Tasche),
  Multicolor-Sprite oben/unten (Weiß und Dunkelgrau = gemeinsame Farben $D025/$D026, Grün = eigene Farbe).
Prüft die Multicolor-Regel (je Spaltenpaar nur eine der Farben W/F/G) und dass jede Hires-Ebene in 21 Zeilen passt.

Ausgabe: assets/sprites.json (Formen als 21 Zeilen à 24 Werte, Metasprites je Bild) und assets/sprites_preview.png.
"""
import json, pathlib, sys

import numpy as np
from PIL import Image

sys.path.insert(0, str(pathlib.Path(__file__).parent))
from c64lib import *  # noqa

SRC = ROOT / "scripts/badger_sprites.txt"
MC0, MC1 = WHITE, DGREY          # $D025, $D026: gemeinsame Multicolor-Farben aller Sprites
BADGER_GREEN = GREEN
SCARF = LRED                     # Schal: Hellrot statt Rot (#68372B liest sich neben Paket und Steg als Braun),
                                 # Vergleich in assets/scarf_compare.png (scripts/scarf_compare.py)


def parse():
    sec, cur = {}, None
    for raw in SRC.read_text().splitlines():
        line = raw.rstrip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("["):
            cur = line.strip("[]")
            sec[cur] = []
            continue
        body = line.split(":", 1)[1] if cur in ("blink", "swing") else line
        if len(body) != 24:
            raise SystemExit(f"[{cur}] Zeile mit {len(body)} statt 24 Zeichen: {line}")
        sec[cur].append(line)
    return sec


def compose(sec, legs, blink=False, swing=False):
    up = [r.ljust(24, ".") for r in sec["upper"]]
    for key, on in (("blink", blink), ("swing", swing)):
        for r in sec[key] if on else []:
            n, row = r.split(":", 1)
            up[int(n)] = row.ljust(24, ".")
    lg = [r.ljust(24, ".") for r in sec["legs:" + legs]]
    off = 42 - len(lg) - len(up)
    grid = [["."] * 24 for _ in range(42)]
    for i, r in enumerate(up):
        if 0 <= i + off < 42:
            grid[i + off] = list(r)
    for i, r in enumerate(lg):
        grid[42 - len(lg) + i] = list(r)
    return grid


def split(grid, name):
    """Ein 42x24-Bild in Hardware-Sprites zerlegen. Rückgabe: Liste von (Form, dy, Farbe, mc)."""
    g = np.array(grid)
    errs = []
    parts = []
    for half, y0 in (("oben", 0), ("unten", 21)):
        sub = g[y0:y0 + 21]
        ov = (sub == "K").astype(int)
        mc = np.zeros((21, 24), int)
        for y in range(21):
            for p in range(12):
                vals = {c for c in sub[y, 2 * p:2 * p + 2] if c in "WFG"}
                if len(vals) > 1:
                    errs.append(f"{name} Zeile {y0 + y} Spalten {2 * p}/{2 * p + 1}: {''.join(sub[y, 2 * p:2 * p + 2])}")
                if vals:
                    v = {"W": 1, "G": 2, "F": 3}[vals.pop()]
                    mc[y, 2 * p:2 * p + 2] = v
        if ov.any():
            parts.append(("K" + half, ov, y0, BLACK, False))
        if mc.any():
            parts.append(("M" + half, mc, y0, BADGER_GREEN, True))
    for ch, col in (("R", SCARF), ("P", ORANGE)):
        ys = np.flatnonzero((g == ch).any(1))
        if not len(ys):
            continue
        y0 = int(ys[0])
        if ys[-1] - y0 >= 21:
            errs.append(f"{name}: Ebene {ch} über {ys[-1] - y0 + 1} Zeilen (höchstens 21)")
        shp = np.zeros((21, 24), int)
        shp[:min(21, 42 - y0)] = (g[y0:y0 + 21] == ch).astype(int)
        parts.append((ch, shp, y0, col, False))
    return parts, errs


def text_shape(rows, mc=False):
    rows = [r.ljust(24, ".") for r in rows] + ["." * 24] * (21 - len(rows))
    m = {".": 0, "#": 1, "1": 1, "2": 2, "3": 3}
    return np.array([[m[c] for c in r] for r in rows])


GULL = {
    "up": ["..#.....#..", ".#.#...#.#.", "#...#.#...#", ".....#....."],
    "mid": ["...........", ".##.....##.", "#..#.#.#..#", ".....#....."],
    "down": ["...........", "...........", ".###.#.###.", "#...#.#...#"],
}
# Rauch: Multicolor, je Zeichen ein Doppelpixel (2 = eigene Farbe). Ohne Mittelstrich, Ränder unregelmäßig,
# schräg nach rechts oben geweht (Doppelpixel sind doppelt so breit wie hoch, deshalb schmal und hoch statt
# Ellipse); wächst mit dem Alter (2, 3, 4, 4 Zeilen) und zerfällt am Ende in Fetzen. Austrittspunkt: Spalte 0-2
# der untersten Zeile; main.gd setzt die Form mit der Unterkante auf den Pfad.
SMOKE = {
    "s1": [".22.", "222."],
    "s2": ["..22", ".222", "222."],
    "s3": ["...22.", "..2222", ".2222.", "222..."],
    "s4": ["....2.2.", "..22.222", ".2.222..", "2..2...."],
}


def beam_shapes():
    """Strahl nach links als zwei aneinandergesetzte Sprites (je 24 Datenpixel, gedehnt = 48 Bildpixel).

    Am Turm schmal und dicht, nach außen breiter und immer lückiger gerastert (Durchsicht ohne Mischfarben).
    """
    shapes = []
    for k in range(2):           # k=0 links (weites Ende), k=1 rechts (am Turm)
        s = np.zeros((21, 24), int)
        for x in range(24):
            gx = k * 24 + x                       # 0 = linkes Ende, 47 = am Turm
            d = (47 - gx) / 47                    # 0 am Turm, 1 am Ende
            half = int(round(1.0 + d * 3.0))
            for dy in range(-half, half + 1):
                y = 10 + dy
                edge = abs(dy) / max(1, half)
                if d < 0.3 or (d < 0.5 and edge < 0.6):
                    on = True                                   # dichter Kern am Turm
                elif d < 0.8 and edge < 0.9:
                    on = (x + y) % 2 == 0                       # Schachbrett
                else:
                    on = (x % 2 == 0) and (y % 2 == 0) and ((x // 2 + y // 2) % 2 == 0)  # sparsam
                if on and gx > 1:
                    s[y, x] = 1
        shapes.append(s)
    return shapes


def main():
    sec = parse()
    frames = {
        "stand": compose(sec, "stand"),
        "blink": compose(sec, "stand", blink=True),
        "walk1": compose(sec, "contact"),
        "walk2": compose(sec, "pass"),
        "walk3": compose(sec, "contact", swing=True),     # zweiter Schritt: Tasche und Schal im Gegenschwung
        "walk4": compose(sec, "pass", swing=True),
    }
    shapes, meta, errors = [], {}, []

    def add(shape, mc):
        shapes.append({"mc": bool(mc), "rows": shape.tolist()})
        return len(shapes) - 1

    for name, grid in frames.items():
        parts, errs = split(grid, name)
        errors += errs
        meta[name] = [{"layer": p[0], "shape": add(p[1], p[4]), "dy": p[2], "color": p[3], "mc": p[4]}
                      for p in parts]
    gulls = {k: add(text_shape(v), False) for k, v in GULL.items()}
    smoke = {}
    for k, v in SMOKE.items():
        rows = []
        for r in v:
            rr = ""
            for c in r:
                rr += c * 2 if c != "." else ".."
            rows.append(rr[:24])
        smoke[k] = add(text_shape(rows), True)
    beam = [add(s, False) for s in beam_shapes()]
    out = {"mc0": MC0, "mc1": MC1, "shapes": shapes, "badger": meta, "gull": gulls, "smoke": smoke, "beam": beam,
           "badger_frames": {k: ["".join(r) for r in g] for k, g in frames.items()}}
    (ROOT / "assets/sprites.json").write_text(json.dumps(out))
    # Vorschau: Bilder nebeneinander auf Hellblau, 6-fach
    order = list(frames)
    S = 6
    prev = Image.new("RGB", ((26 * len(order)) * S, 44 * S), tuple(PAL[LBLUE]))
    pix = prev.load()
    for n, name in enumerate(order):
        canvas = np.full((42, 24), -1)
        for p in sorted(meta[name], key=lambda p: {"K": 0, "R": 1, "P": 2, "M": 3}[p["layer"][0]], reverse=True):
            shp = np.array(shapes[p["shape"]]["rows"])
            for y in range(21):
                for x in range(24):
                    v = shp[y, x]
                    if not v or p["dy"] + y >= 42:
                        continue
                    c = p["color"] if not p["mc"] else {1: MC0, 2: p["color"], 3: MC1}[v]
                    canvas[p["dy"] + y, x] = c
        for y in range(42):
            for x in range(24):
                if canvas[y, x] < 0:
                    continue
                for dy in range(S):
                    for dx in range(S):
                        pix[(n * 26 + 1 + x) * S + dx, (1 + y) * S + dy] = tuple(PAL[canvas[y, x]])
    prev.save(ROOT / "assets/sprites_preview.png")
    print(f"{len(shapes)} Formen, Dachsbilder: {', '.join(order)}")
    if errors:
        print("REGELVERSTÖSSE:\n  " + "\n  ".join(errors))
        sys.exit(1)


if __name__ == "__main__":
    main()
