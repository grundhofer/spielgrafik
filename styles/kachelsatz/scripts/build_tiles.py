#!/usr/bin/env python3
"""Baut den Kachelsatz des Eintrags kachelsatz aus dem KI-Kachelblatt.

    .venv/bin/python styles/kachelsatz/scripts/build_tiles.py

1. KI-Blatt (assets/raw/tiles.png) auf das echte Raster bringen (24 Kunstpixel je KI-Kachel, Mehrheitsfarbe je Zelle).
2. Je Material eine nahtlose 16x16-Füllkachel (Min-Cut) plus Varianten mit gemeinsamem Rand.
3. Je Ebene 15 Übergangskacheln (Corner-Terrain gegen 'leer', 16. Fall = leer) aus Geometrie + Füllkachel:
   sand (Land über Wasser, Schaum animiert), grass (über Sand), stone (Kai mit Mauer), jetty (Steg).
   Wasser: eine Füllkachel mit 16 Animationsbildern.
4. Atlanten nach assets/tiles/ und demo/tiles/, Beschreibung tiles.json (Ecken-Bits, Bilder, Dauer).
"""
import json, pathlib, sys

import numpy as np
from PIL import Image

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from autotile import T, EXT, N, IN_TILE, shape, distances, pnoise, ext, shifted, bits  # noqa: E402
from materials import load_sheet, make_periodic, make_periodic_best, seam_error, blend_variant  # noqa: E402

ENTRY = HERE.parent
OUT_A = ENTRY / "assets" / "tiles"
OUT_D = ENTRY / "demo" / "tiles"


def hexc(h, a=255):
    h = h.lstrip("#")
    return np.array([int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16), a], np.uint8)


def rgba(pal_rgb, idx):
    out = np.zeros(idx.shape + (4,), np.uint8)
    out[..., :3] = pal_rgb[idx]
    out[..., 3] = 255
    return out


# ---------------------------------------------------------------- Füllkacheln
sheet = load_sheet(ENTRY / "assets" / "raw" / "tiles.png")
report = {}


def fill(name, base_cands, var_cols, seed, fixed=None):
    """Grundkachel: unter den Kandidaten-Spalten die mit dem kleinsten Nahtfehler (oder fester Ausschnitt
    fixed = (Spalte, x0, y0, Überlappung)). Varianten: eigene Mitte aus anderen KI-Kacheln, Rand von der
    Grundkachel (passen damit an jede Kante)."""
    pal, tiles = sheet[name]
    if fixed:
        c, x0, y0, ov = fixed
        t = make_periodic(tiles[c], pal, T, ov, x0, y0)
        (err, base, cut), base_col = (seam_error(t, pal), t, (x0, y0, ov)), c
    else:
        cands = [(make_periodic_best(tiles[c], pal), c) for c in base_cands]
        (err, base, cut), base_col = min(cands, key=lambda b: b[0][0])
    vs = []
    for k, c in enumerate(v for v in var_cols if v != base_col):
        vs.append(blend_variant(base, make_periodic_best(tiles[c], pal)[1], seed + k))
    report[name] = {"seam_ratio": round(float(err), 2), "base_col": base_col, "cut": cut,
                    "variant_cols": [v for v in var_cols if v != base_col]}
    return pal, base, vs


G_PAL, G0, G_VAR = fill("grass", [0, 1, 3, 4, 5, 7], [3, 2, 6, 5], 10)
S_PAL, S0, S_VAR = fill("sand", [0, 1, 2, 3, 4, 5, 7], [6, 3], 20)
W_PAL, W0, _ = fill("water", [0], [], 30, fixed=(0, 2, 2, 4))  # Suche wählte ein zu gleichförmiges Strichmuster
C_PAL, C0, C_VAR = fill("cobble", list(range(8)), [4, 1], 40)
P_PAL, _ = sheet["planks"]


def planks_texture():
    """Steg: Bretter quer (Stoß bei x = 8, also an den Stegkanten), drei Bretter je 16 px (5/5/6 inkl. Fuge).
    Holz aus den KI-Brettern (Innenteil), Nägel nahe den Enden."""
    pal, tiles = sheet["planks"]
    lab_l = np.array([0.299 * c[0] + 0.587 * c[1] + 0.114 * c[2] for c in pal])
    dark = int(np.argmin(lab_l))
    src = tiles[2]
    rows = []
    # Holzzeilen aus dem KI-Brett: Zeilen, deren Mehrheit nicht die Fugenfarbe ist
    wood_rows = [y for y in range(3, 21) if (src[y, 4:20] == dark).mean() < 0.3]
    heights = [4, 4, 5]
    k = 0
    for h in heights:
        for i in range(h):
            r = src[wood_rows[(k + i) % len(wood_rows)], 4:20].copy()
            ok = r[r != dark]
            r[r == dark] = np.bincount(ok).argmax() if ok.size else 3
            rows.append(r)
        k += h + 1
        rows.append(np.full(16, dark))
    tex = np.array(rows)[:16]
    tex = np.roll(tex, 8, axis=1)  # Brettende bei x = 8
    nail = int(np.argmax([int(c[2]) - int(c[0]) for c in pal]))  # bläulichgrau
    y = 0
    for h in heights:
        tex[y + h // 2, 9] = nail
        tex[y + h // 2, 6] = nail
        y += h + 1
    end = int(np.argsort(lab_l)[1])
    tex[:, 8][tex[:, 8] != dark] = end   # Hirnholz am Brettanfang
    return pal, tex


J_PAL, J0 = planks_texture()


# ---------------------------------------------------------------- Ebenen
FOAM_D = [1.0, 1.6, 2.2, 2.8, 2.2, 1.6]    # Abstand der Schaumlinie je Bild (px)
FOAM_DUR = 0.2
WATER_FRAMES = 16
WATER_DUR = 0.1
NOISE_EDGE = pnoise(101, cell=4)
NOISE_FINE = pnoise(102, cell=2)
NOISE_FOAM = pnoise(103, cell=2)


def lum(c):
    return 0.299 * c[0] + 0.587 * c[1] + 0.114 * c[2]


def darker(pal, idx, steps=1):
    order = np.argsort([lum(c) for c in pal])
    rank = np.empty(len(pal), int)
    rank[order] = np.arange(len(pal))
    return order[np.clip(rank[idx] - steps, 0, len(pal) - 1)]


def organic(cfg, r_cvx, r_ccv, amp, seed_noise):
    ins = shape(cfg, r_cvx, r_ccv)
    s = distances(ins)
    e = ext(amp * seed_noise)
    land = s > e if cfg not in (0, 15) else ins
    return land, distances(land)


def sand_tile(cfg, frame):
    land, s = organic(cfg, 8.0, 7.0, 1.8, 0.6 * NOISE_EDGE + 0.4 * NOISE_FINE)
    out = np.zeros((N, N, 4), np.uint8)
    tex = ext(S0)
    col = rgba(S_PAL, tex)
    damp = rgba(S_PAL, darker(S_PAL, tex, 1))
    out[land] = col[land]
    m = land & (s < 2.0)
    out[m] = damp[m]
    wet = land & (s < 1.0)
    out[wet] = hexc("b39674")
    # Wasserseite: helles Flachwasser, Schaumlinie (animiert)
    d = -s
    water = ~land
    shallow = water & (d < 4.5)
    out[shallow] = hexc("8fe0e0", 70)
    shallow2 = water & (d < 2.0)
    out[shallow2] = hexc("b5f0ea", 110)
    D = FOAM_D[frame]
    nf = ext(NOISE_FOAM)
    foam = water & (np.abs(d - D) < 0.55) & (nf > 0.18)
    out[foam] = hexc("f4fbf6")
    foam2 = water & (np.abs(d - (D + 1.0)) < 0.5) & (nf > 0.62)
    out[foam2] = hexc("d7f3ef", 200)
    return out[IN_TILE]


def grass_tile(cfg):
    land, s = organic(cfg, 7.0, 6.0, 2.2, 0.5 * NOISE_FINE + 0.5 * pnoise(104, cell=2))
    out = np.zeros((N, N, 4), np.uint8)
    col = rgba(G_PAL, ext(G0))
    out[land] = col[land]
    below_free = land & ~shifted(land, 0, -1)          # Pixel darunter ist kein Gras
    out[below_free] = rgba(G_PAL, np.full(land.shape, int(np.argmin([lum(c) for c in G_PAL]))))[below_free]
    above_free = land & ~shifted(land, 0, 1) & (ext(NOISE_FINE) > 0.45)
    light = int(np.argsort([lum(c) for c in G_PAL])[-3])
    out[above_free] = rgba(G_PAL, np.full(land.shape, light))[above_free]
    shadow = ~land & shifted(land, 0, 1)                # direkt unter einer Graskante
    out[shadow] = hexc("5a4126", 90)
    return out[IN_TILE]


WALL_H = 8


def stone_tile(cfg):
    ins = shape(cfg, 0.0, 0.0)
    s = distances(ins)
    out = np.zeros((N, N, 4), np.uint8)
    out[ins] = rgba(C_PAL, ext(C0))[ins]
    order = np.argsort([lum(c) for c in C_PAL])
    # Bordsteine (Abdeckung) entlang aller Kanten, Fugen alle 5 px
    kerb = ins & (s < 1.0)
    xs = (np.arange(N) - EXT) % T
    jx = (xs[None, :] % 5 == 0) | (xs[:, None] % 5 == 0)
    kc = np.where(jx, order[1], order[-2])
    out[kerb] = rgba(C_PAL, np.broadcast_to(kc, ins.shape))[kerb]
    # Mauer nach Süden: Pixel außen, über dem in <= WALL_H px Kai liegt (Tiefe = Abstand zur Kante)
    depth = np.zeros(ins.shape, int)
    for k in range(WALL_H, 0, -1):
        hit = ~ins & shifted(ins, 0, k)
        depth[hit] = k
    wall = depth > 0
    brick_row = np.clip((depth - 1) // 3, 0, 2)  # Quaderreihen zu 3 px (2 Stein + 1 Fuge)
    mortar = (depth == 3) | (depth == 6)
    xg = np.broadcast_to((np.arange(N) - EXT) % T, ins.shape)
    vjoint = ((xg + 4 * brick_row) % 8 == 0)
    wc = np.choose(brick_row, [order[3], order[2], order[1]])
    wc = np.where(vjoint | mortar, order[0], wc)
    out[wall] = rgba(C_PAL, wc)[wall]
    algae = wall & (depth == 7) & (ext(NOISE_FINE) > 0.5)
    out[algae] = hexc("3f5b3c")
    base = wall & (depth == WALL_H)
    out[base] = hexc("24363a")
    # Wasserlinie unter der Mauer
    under = ~ins & ~wall & shifted(ins, 0, WALL_H + 1)
    out[under & (ext(NOISE_FOAM) > 0.35)] = hexc("e6f6f2", 210)
    out[under & (ext(NOISE_FOAM) <= 0.35)] = hexc("0b2633", 90)
    # Abbruchkante an den übrigen Seiten (Nord, Ost, West): dunkle Linie
    edge = ~ins & ~wall & ~under & (shifted(ins, 1, 0) | shifted(ins, -1, 0) | shifted(ins, 0, -1))
    out[edge] = hexc("17222c", 190)
    return out[IN_TILE]


def jetty_tile(cfg):
    ins = shape(cfg, 0.0, 0.0)
    out = np.zeros((N, N, 4), np.uint8)
    out[ins] = rgba(J_PAL, ext(J0))[ins]
    order = np.argsort([lum(c) for c in J_PAL])
    # Schatten auf dem Wasser (Licht von oben links)
    sh = ~ins & (shifted(ins, 2, 2) | shifted(ins, 1, 2) | shifted(ins, 2, 1))
    out[sh] = hexc("06202c", 95)
    # Stirnseite der Bretter nach Süden (2 px), darunter Pfähle an den Enden
    depth = np.zeros(ins.shape, int)
    for k in (2, 1):
        depth[~ins & shifted(ins, 0, k)] = k
    face = depth > 0
    out[face] = rgba(J_PAL, np.full(ins.shape, order[1]))[face]
    out[face & (depth == 2)] = rgba(J_PAL, np.full(ins.shape, order[0]))[face & (depth == 2)]
    # Pfahlköpfe an den Seiten: je 16 px einer, knapp außerhalb der Kante
    xg = np.broadcast_to((np.arange(N) - EXT) % T, ins.shape)
    yg = np.broadcast_to(((np.arange(N) - EXT) % T)[:, None], ins.shape)
    side = ~ins & ~face & (shifted(ins, 1, 0) | shifted(ins, -1, 0))
    side2 = ~ins & ~face & (shifted(ins, 2, 0) | shifted(ins, -2, 0))
    post = (side | side2) & ((yg == 11) | (yg == 12))
    edge = ~ins & ~face & (shifted(ins, 1, 0) | shifted(ins, -1, 0) | shifted(ins, 0, -1))
    out[edge] = hexc("1a120e", 200)
    out[post] = rgba(J_PAL, np.full(ins.shape, order[1]))[post]
    out[post & side2] = rgba(J_PAL, np.full(ins.shape, order[0]))[post & side2]
    # Pfähle unter der Stegspitze (Süden): unter der Stirnseite, an den Enden
    legs = ~ins & ~face & shifted(ins, 0, 3) & (shifted(ins, 0, 3) & ~(shifted(ins, -2, 3) & shifted(ins, 2, 3)))
    for k in range(3, 7):
        leg = ~ins & shifted(ins, 0, k) & ~(shifted(ins, -2, k) & shifted(ins, 2, k))
        out[leg] = rgba(J_PAL, np.full(ins.shape, order[1 if k < 6 else 0]))[leg]
    return out[IN_TILE]


def water_frames():
    """16 Bilder aus der KI-Wasserkachel: Grund bleibt stehen, die hellen Kräuselstriche schwingen zeilenweise
    um +-1 px hin und her (Phase je Zeilenpaar, periodisch in 16 px) und blitzen versetzt auf."""
    order = np.argsort([lum(c) for c in W_PAL])
    rank = np.empty(len(W_PAL), int)
    rank[order] = np.arange(len(W_PAL))
    hi = rank[W0] >= 3
    body = W0.copy()
    for y, x in zip(*np.nonzero(hi)):
        nb = [W0[(y + dy) % T, (x + dx) % T] for dy, dx in ((0, 1), (0, -1), (1, 0), (-1, 0), (1, 1), (-1, -1))]
        nb = [v for v in nb if rank[v] < 3] or [order[1]]
        body[y, x] = max(set(nb), key=nb.count)
    nz = pnoise(105, cell=2)
    frames = []
    for f in range(WATER_FRAMES):
        t = body.copy()
        for y in range(T):
            ph = 2 * np.pi * (f / WATER_FRAMES + 2 * (y // 2) / T)
            off = int(np.round(1.2 * np.sin(ph)))
            row_hi = np.roll(hi[y], off)
            row_c = np.roll(W0[y], off)
            t[y, row_hi] = row_c[row_hi]
        # Aufblitzen: ein Teil der Striche wird für einige Bilder eine Stufe heller
        tw = ((nz + f / WATER_FRAMES) % 1.0) < 0.22
        up = (rank[t] >= 3) & tw
        t[up] = order[np.minimum(rank[t[up]] + 1, len(W_PAL) - 1)]
        frames.append(rgba(W_PAL, t))
    return frames


# ---------------------------------------------------------------- Atlanten
def save(img, name):
    for d in (OUT_A, OUT_D):
        d.mkdir(parents=True, exist_ok=True)
        Image.fromarray(img).save(d / name)


def layer_atlas(name, render, frames=1, full_variants=(), var_render=None):
    """Zeile r: Konfiguration r+1 (1..15), Spalten: Animationsbilder. Danach volle Varianten."""
    rows = 15 + len(full_variants)
    img = np.zeros((rows * T, frames * T, 4), np.uint8)
    tiles = []
    for cfg in range(1, 16):
        r = cfg - 1
        for f in range(frames):
            img[r * T:(r + 1) * T, f * T:(f + 1) * T] = render(cfg, f) if frames > 1 else render(cfg)
        prob = 0.4 if (cfg == 15 and full_variants) else 1.0
        tiles.append({"atlas": [0, r], "corners": bits(cfg), "variant": 0, "frames": frames, "probability": prob})
    for k, v in enumerate(full_variants):
        r = 15 + k
        for f in range(frames):
            img[r * T:(r + 1) * T, f * T:(f + 1) * T] = var_render(v, f)
        tiles.append({"atlas": [0, r], "corners": [1, 1, 1, 1], "variant": k + 1, "frames": frames,
                      "probability": round(0.6 / len(full_variants), 4)})
    save(img, name + ".png")
    return img, tiles


def full_variant_sand(v, f):
    return rgba(S_PAL, v)


def full_variant_grass(v, f=0):
    return rgba(G_PAL, v)


def full_variant_cobble(v, f=0):
    return rgba(C_PAL, v)


def main():
    desc = {"tile_size": T, "layers": {}}
    _, t = layer_atlas("sand", sand_tile, frames=len(FOAM_D), full_variants=S_VAR, var_render=full_variant_sand)
    desc["layers"]["sand"] = {"texture": "sand.png", "frame_duration": FOAM_DUR, "tiles": t,
                              "covers": ["S", "G", "C"]}
    _, t = layer_atlas("grass", grass_tile, full_variants=G_VAR, var_render=full_variant_grass)
    desc["layers"]["grass"] = {"texture": "grass.png", "tiles": t, "covers": ["G"]}
    _, t = layer_atlas("stone", stone_tile, full_variants=C_VAR, var_render=full_variant_cobble)
    desc["layers"]["stone"] = {"texture": "stone.png", "tiles": t, "covers": ["C"]}
    _, t = layer_atlas("jetty", jetty_tile)
    desc["layers"]["jetty"] = {"texture": "jetty.png", "tiles": t, "covers": ["J"]}
    wf = water_frames()
    save(np.concatenate(wf, 1), "water.png")
    desc["layers"]["water"] = {"texture": "water.png", "frame_duration": WATER_DUR,
                               "tiles": [{"atlas": [0, 0], "corners": [1, 1, 1, 1], "variant": 0,
                                          "frames": WATER_FRAMES, "probability": 1.0}], "covers": ["*"]}
    desc["fills"] = report
    desc["order"] = ["water", "sand", "grass", "stone", "jetty"]
    for d in (OUT_A, OUT_D):
        (d / "tiles.json").write_text(json.dumps(desc, indent=1))
    # Füllkacheln zur Kontrolle (4x4 gekachelt)
    prev = []
    for pal, base, vs in ((G_PAL, G0, G_VAR), (S_PAL, S0, S_VAR), (W_PAL, W0, []), (C_PAL, C0, C_VAR), (J_PAL, J0, [])):
        prev.append(np.tile(rgba(pal, base), (4, 4, 1)))
    Image.fromarray(np.concatenate(prev, 1)).save(OUT_A / "fills_preview.png")
    overview()
    print(json.dumps(report))


def overview():
    """Übersicht: je Ebene die 16 Eckfälle (Index = Bits oben links 1, oben rechts 2, unten links 4, unten rechts 8)
    in einem 4x4-Raster über der jeweils darunterliegenden Fläche, Bild 0 der Animation."""
    under = {"sand": rgba(W_PAL, W0), "grass": rgba(S_PAL, S0), "stone": rgba(W_PAL, W0), "jetty": rgba(W_PAL, W0)}
    panels = []
    for name in ("sand", "grass", "stone", "jetty"):
        at = np.asarray(Image.open(OUT_A / (name + ".png")).convert("RGBA")).astype(float) / 255
        pan = np.full((4 * 18 + 2, 4 * 18 + 2, 3), 1.0)
        for cfg in range(16):
            x, y = 2 + (cfg % 4) * 18, 2 + (cfg // 4) * 18
            cell = under[name][..., :3].astype(float) / 255
            if cfg:
                t = at[(cfg - 1) * T:cfg * T, 0:T]
                cell = t[..., :3] * t[..., 3:] + cell * (1 - t[..., 3:])
            pan[y:y + T, x:x + T] = cell
        panels.append(pan)
        panels.append(np.full((pan.shape[0], 6, 3), 1.0))
    img = (np.concatenate(panels[:-1], 1) * 255 + 0.5).astype(np.uint8)
    Image.fromarray(img).resize((img.shape[1] * 4, img.shape[0] * 4), Image.NEAREST).save(OUT_A / "overview.png")


if __name__ == "__main__":
    main()
