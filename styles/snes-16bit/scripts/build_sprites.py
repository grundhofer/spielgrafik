#!/usr/bin/env python3
"""Sprites (OBJ) für snes-16bit: Dachs-Kurier, Rauch, Möwe, Paket -> demo/art/sprites.png + sprites.json.

    .venv/bin/python styles/snes-16bit/scripts/build_sprites.py [--preview out.png]

Dachs (OBJ-Palette 0, 15 Farben, 32×32-Sprite):
  * Körper: KI-Stehbild (build_badger.py, materialtreu verkleinert) mit Nacharbeit am Kopf (Auge mit
    Glanzpunkt, Nase), für alle Bilder derselbe Körper -> nichts flimmert zwischen den Bildern.
  * Laufen: 6 Bilder (Kontakt, Stand, Durchgang je Bein) mit gezeichneten Beinen. Der Standfuß wandert im
    Sprite genau um den Vorschub des Bildes zurück (STEP), dadurch steht er in der Welt still. Hüfte 1 px
    höher im Durchgang (Auf und Ab).
  * Stehen = KI-Stehbild; Blinzeln = Stehbild mit geschlossenem Auge; Sprechen = Stehbild + Mund und
    Gestik-Arm aus dem KI-Sprechbild (nur diese Pixel, sonst flimmert der Körper).
Rauch (OBJ-Palette 1, 4 Töne), Möwe (OBJ-Palette 2), Paket (OBJ-Palette 0, Farben des Dachses): von Hand
gesetzte Pixelmuster unten im Skript.
"""
import argparse, json, pathlib, sys
import numpy as np
from PIL import Image

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from build_badger import build, MATERIALS  # noqa: E402
from sneslib import c5  # noqa: E402

STYLE = HERE.parent
ART = STYLE / 'demo/art'
CELL = 32

# Laufzyklus: Vorschub je Bildwechsel (px) und Fußstellungen (Mitte des Fußes in Sprite-Spalten)
STEP = [3, 2, 2, 3, 2, 2]                 # 7 px je Schritt, 14 px je Zyklus, 6 Bilder bei 15 Bildern/s
HIP_X = 15                                # Hüftmitte
# je Bild: (Fuß A x, Hub A, Fuß B x, Hub B, Körperhub); Standfuß wandert um STEP zurück
LEGS = [
    (19, 0, 12, 0, 0),    # 0 Kontakt: A vorn aufgesetzt, B hinten
    (16, 0, 14, 2, 0),    # 1 A trägt, B schwingt (2 px angehoben)
    (14, 0, 17, 1, 1),    # 2 Durchgang: A trägt, B vor A, Körper 1 px höher
    (12, 0, 19, 0, 0),    # 3 Kontakt: B vorn aufgesetzt, A hinten
    (14, 2, 16, 0, 0),    # 4 B trägt, A schwingt
    (17, 1, 14, 0, 1),    # 5 Durchgang
]
BODY_ROWS = 27            # Zeilen 0..26 vom Körper (mit Bauch), darunter gezeichnete Beine (Zeilen 27..30, Sohle = Kontur in Zeile 30)


def find(pmat, mat):
    return [i for i in range(len(pmat)) if pmat[i] == MATERIALS.index(mat)]


def head_fix(b, P):
    """Nacharbeit am Kopf (Koordinaten im Stehbild, von Hand gesetzt, siehe Vorschau): weißer Stirnstreif
    unter der Mütze (Zeile 6), darunter der dunkle Augenstreif mit Pupille (Konturfarbe) und hellem Lidpunkt
    dahinter, sonst ist das Auge im dunklen Fell nicht zu sehen."""
    b = b.copy()
    b[6, 14:20] = P['hell']
    b[6, 16] = P['hell2']
    b[7, 11:20] = P['fell']
    b[7, 17] = P['dunkel']
    b[7, 18] = P['hell2']
    return b


FACE_BOX = (6, 13, 12, 26)          # Zeilen 6..12, Spalten 12..25 (Auge, Lid)
TALK_BOX = (9, 22, 16, 28)          # Zeilen 9..21, Spalten 16..27 (Mund, erhobene Pfote)


def compose(base, src, box, dark):
    y0, y1, x0, x1 = box
    diff = np.zeros(base.shape, bool)
    diff[y0:y1, x0:x1] = base[y0:y1, x0:x1] != src[y0:y1, x0:x1]
    pad = np.pad(diff, 1)
    grown = diff | pad[:-2, 1:-1] | pad[2:, 1:-1] | pad[1:-1, :-2] | pad[1:-1, 2:]
    win = np.zeros(base.shape, bool)
    win[y0:y1, x0:x1] = True
    out = base.copy()
    m = grown & win
    out[m] = src[m]
    return outline(out, dark)


def outline(idx, dark):
    pad = np.pad(idx, 1, constant_values=-1)
    edge = (idx >= 0) & ((pad[:-2, 1:-1] < 0) | (pad[2:, 1:-1] < 0) | (pad[1:-1, :-2] < 0) | (pad[1:-1, 2:] < 0))
    out = idx.copy()
    out[edge] = dark
    return out


def leg_pixels(hip_x, foot_x, lift, top, width=4):
    """Pixel eines Beins von der Hüfte (Zeile top) bis zum Fuß (Zeile 30-lift); Fuß 5 px mit Zehe nach vorn."""
    px = set()
    bottom = 30 - lift
    n = max(1, bottom - top)
    for r in range(top, bottom + 1):
        f = (r - top) / n
        cx = hip_x + (foot_x - hip_x) * f
        x0 = int(round(cx - width / 2))
        for x in range(x0, x0 + width):
            px.add((r, x))
    fx0 = int(round(foot_x - 2))
    for x in range(fx0, fx0 + 5):
        px.add((bottom, x))
    return px


def walk_frame(body, P, k):
    fa, la, fb, lb, up = LEGS[k]
    out = np.full((CELL, CELL), -1)
    # Körper (Zeilen 0..BODY_ROWS-1), im Durchgang 1 px höher
    out[0:BODY_ROWS - up] = body[up:BODY_ROWS]
    top = BODY_ROWS - 1 - up
    # Hinteres Bein (B in Bildern 0-2 und A in 3-5 ist hinten im Bild?): das fernere Bein ist B, dunkler
    far = leg_pixels(HIP_X - 1, fb, lb, top)
    near = leg_pixels(HIP_X + 1, fa, la, top)
    for r, x in far:
        if 0 <= x < CELL and out[r, x] < 0:
            out[r, x] = P['fell_far']
    # Kontur zwischen fernem und nahem Bein
    near_m = np.zeros((CELL, CELL), bool)
    for r, x in near:
        near_m[r, x] = True
    ring = np.zeros_like(near_m)
    ring[1:] |= near_m[:-1]; ring[:-1] |= near_m[1:]; ring[:, 1:] |= near_m[:, :-1]; ring[:, :-1] |= near_m[:, 1:]
    ring &= ~near_m
    for r, x in zip(*np.nonzero(ring)):
        if r >= BODY_ROWS - up and out[r, x] == P['fell_far']:
            out[r, x] = P['dunkel']
    for r, x in near:
        if out[r, x] < 0 or r >= BODY_ROWS - up or out[r, x] == P['fell_far']:
            out[r, x] = P['fell']
    return outline(out, P['dunkel'])


# ---------------------------------------------------------------- Rauch, Möwe, Paket
SMOKE = [
    [".HH.",
     "HHBB",
     "HBBS",
     ".SS."],
    [".HHH..",
     "HHHBB.",
     "HHBBBS",
     ".BBBSS",
     "..SSS."],
    ["..HHH...",
     ".HHHBBB.",
     "HHHBBBBS",
     "HHBBBBBS",
     ".BBBBBSS",
     "..BBSSS.",
     "...SS..."],
    ["...HH.....",
     ".HHHBB.HH.",
     "HHBBBBHBBS",
     ".HBBB.BBBS",
     "..BBBBBBS.",
     ".BBS.BSS..",
     "..SS..S..."],
    ["...H......",
     ".H.HB..H..",
     "HB.BB.BB.S",
     "..BB...BS.",
     ".B..BB.S..",
     "..S...S..."],
]
GULL = [
    ["D.......D",
     ".WD...DW.",
     "..WWOWW..",
     "....G...."],
    [".........",
     "..WWOWW..",
     ".WG.G.GW.",
     "D.......D"],
]
PARCEL = [
    ".OOOOOOOOOO.",
    "OLLLLLSLLLLO",
    "OLLLLLSLLLLO",
    "OSSSSSSSSSSO",
    "OTTTTTSTTTTO",
    "OTTTTTSTTTTO",
    "OTTTTTSTTTTO",
    ".OOOOOOOOOO.",
]
GREEN = ['6b8439', '4a6329', '31421c']                       # Mütze/Weste hell, mittel, dunkel
SMOKE_PAL = ['b8b0c8', '8c84a4', '645c84', '4c4470']          # OBJ-Palette 1: hell .. dunkel
GULL_PAL = ['f0f0f0', '9c9cb8', '303048', 'e09040']           # OBJ-Palette 2: weiß, grau, dunkel, Schnabel


def hexrgb(h):
    """Hex -> RGB, auf das 5-Bit-Raster gerundet (wie jeder CGRAM-Eintrag)."""
    return [int(v) for v in c5(np.array([int(h[i:i + 2], 16) for i in (0, 2, 4)]))]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--preview')
    a = ap.parse_args()
    cells, pal, pmat = build(sheet=2)
    pal = [list(map(int, c)) for c in pal]
    P = {
        'dunkel': find(pmat, 'dunkel')[0],
        'fell': 2,
        'fell_far': 1,
        'hell': find(pmat, 'hell')[0],
        'hell2': find(pmat, 'hell')[1],
    }
    # Fell: Index 2 ist der Grundton; Index 1 (ungenutzter heller Fellton) wird zum Ton des ferneren Beins
    pal[1] = list(map(int, c5(np.array([47, 36, 41]))))
    for i, h in zip(find(pmat, 'gruen'), GREEN):
        pal[i] = hexrgb(h)
    stand = cells[0][1]
    # Blinzeln und Sprechen aus Teilen: Körper aus dem Stehbild, vom KI-Bild nur die Pixel, die sich in einem
    # Fenster um Gesicht bzw. Mund und Gestik-Arm unterscheiden (1 px erweitert). Die übrigen, verstreuten
    # Unterschiede der KI-Bilder würden den Körper flimmern lassen.
    blink = compose(stand, cells[1][1], FACE_BOX, P['dunkel'])
    talk = compose(stand, cells[2][1], TALK_BOX, P['dunkel'])
    walk = [walk_frame(stand, P, k) for k in range(6)]
    frames = walk + [stand, blink, talk]
    names = [f'walk{k}' for k in range(6)] + ['stand', 'blink', 'talk']

    # Atlas: Reihe 0 Dachs (32×32), Reihe 1 Rauch/Möwe/Paket (16×16-Zellen)
    W = CELL * len(frames)
    atlas = np.zeros((CELL + 16, W, 4), np.uint8)
    meta = {'cell': CELL, 'frames': {}, 'small': {}}
    for i, f in enumerate(frames):
        m = f >= 0
        sub = atlas[0:CELL, i * CELL:(i + 1) * CELL]
        sub[m, :3] = np.array(pal)[f[m]]
        sub[m, 3] = 255
        meta['frames'][names[i]] = [i * CELL, 0, CELL, CELL]

    def put(pattern, x0, cmap, key):
        h, w = len(pattern), len(pattern[0])
        for r, row in enumerate(pattern):
            for c, ch in enumerate(row):
                if ch in cmap:
                    atlas[CELL + r, x0 + c, :3] = cmap[ch]
                    atlas[CELL + r, x0 + c, 3] = 255
        meta['small'][key] = [x0, CELL, w, h]

    x = 0
    sp = [hexrgb(h) for h in SMOKE_PAL]
    for i, pat in enumerate(SMOKE):
        put(pat, x, {'H': sp[0], 'B': sp[1], 'S': sp[2]}, f'smoke{i}'); x += 16
        put(pat, x, {'H': sp[1], 'B': sp[2], 'S': sp[3]}, f'smoke{i}_old'); x += 16
    gp = [hexrgb(h) for h in GULL_PAL]
    for i, pat in enumerate(GULL):
        put(pat, x, {'W': gp[0], 'G': gp[1], 'D': gp[2], 'O': gp[3]}, f'gull{i}'); x += 16
    pidx = find(pmat, 'paket')
    lidx = find(pmat, 'leder')
    put(PARCEL, x, {'O': pal[P['dunkel']], 'L': pal[pidx[0]], 'T': pal[pidx[1]], 'S': pal[lidx[1]]}, 'parcel'); x += 16

    meta['walk'] = {'fps': 15, 'step_px': STEP, 'legs': LEGS, 'feet_row': 29}
    meta['obj_palettes'] = {
        '0': ['%02x%02x%02x' % tuple(c) for c in pal],
        '1': ['%02x%02x%02x' % tuple(hexrgb(h)) for h in SMOKE_PAL],
        '2': ['%02x%02x%02x' % tuple(hexrgb(h)) for h in GULL_PAL],
    }
    ART.mkdir(parents=True, exist_ok=True)
    Image.fromarray(atlas, 'RGBA').save(ART / 'sprites.png')
    Image.fromarray(atlas, 'RGBA').save(STYLE / 'assets/sprites.png')
    (ART / 'sprites.json').write_text(json.dumps(meta, indent=1))
    print('sprites.png', atlas.shape[1], 'x', atlas.shape[0], '| Dachs-Palette', len(pal), 'Farben')
    if a.preview:
        bg = Image.new('RGBA', (atlas.shape[1], atlas.shape[0]), (56, 60, 130, 255))
        bg.alpha_composite(Image.fromarray(atlas))
        bg.resize((bg.width * 6, bg.height * 6), Image.NEAREST).save(a.preview)


if __name__ == '__main__':
    main()
