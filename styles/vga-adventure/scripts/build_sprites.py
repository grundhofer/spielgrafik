#!/usr/bin/env python3
"""Figur, Paket, Inventar-Symbole und Oberflächenfarben in die gemeinsame 256er-Palette bringen.

    .venv/bin/python styles/vga-adventure/scripts/build_sprites.py [--preview DIR]

Voraussetzung: build_bg.py ist gelaufen (demo/art/palette.json existiert).
Belegt die Paletteneinträge 0..11 (Oberfläche) und 12..39 (Figur 12..29, Inventar 30..39) und schreibt:
  demo/art/badger_walk.png, badger_stand.png  Streifen mit gleich großen Zellen, Anker in sprites.json
                                              (Stehen: stehen, sprechen x2, blinzeln, Übergangsbild Laufen -> Stehen)
  demo/art/parcel.png                         Paket auf dem Kai (aus Figurenfarben gepixelt, mit Schattenzeile)
Alle Farben liegen auf dem 6-Bit-Raster des VGA-DAC (build_bg.vga6).
  demo/art/items.png                          4 Inventar-Symbole 26x17 nebeneinander
  assets/*.png                                dieselben Dateien als Arbeitskopie
"""
import argparse, json, pathlib, shutil, sys
import numpy as np
from PIL import Image

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from pixgrid import kmeans, nearest, oklab  # noqa: E402
import build_badger  # noqa: E402
from build_bg import vga6  # noqa: E402

STYLE = HERE.parent
ART = STYLE / 'demo/art'
ASSETS = STYLE / 'assets'

UI_COLORS = {            # Index: (Name, Farbe)
    0: ('schwarz', (0, 0, 0)),
    1: ('feld', (16, 12, 36)),
    2: ('rahmen', (88, 64, 148)),
    3: ('verb', (104, 116, 192)),
    4: ('verb_hell', (252, 220, 100)),
    5: ('satz', (148, 216, 236)),
    6: ('sprechtext', (252, 176, 76)),
    7: ('weiss', (255, 255, 255)),
    8: ('grau', (150, 150, 170)),
    9: ('pfeil', (64, 48, 112)),
    10: ('satz_klick', (255, 255, 255)),
    11: ('kontur', (36, 20, 24)),
}
SPRITE0, SPRITE_N = 12, 18
ITEM0, ITEM_N = 30, 10


# Laufzyklus aus den 6 KI-Bildern: Kontakt (0) - Durchgang (2) - Aufwärts (3) - Ausgreifen (5). Die Bilder 1 und 4
# zeigen fast dieselbe Beinstellung wie 0 und ließen die Füße schlurfen; sie werden nicht verwendet.
WALK_ORDER = [0, 2, 3, 5]
# Vorschub des Körpers je Bildwechsel (px), aus der Lage des Standfußes in den Bildern gemessen
# (Mitte des Standfußes: 19,5 -> 16 -> 13 -> 11,5 -> 10, d. h. 3,5 / 3 / 1,5 / 1,5 px), ganzzahlig gerundet
WALK_STEP_PX = [3, 3, 2, 2]
# Auf und Ab beim Gehen: Die KI-Bilder haben alle dieselbe Kopfhöhe (Kopfoberkante in jedem Laufbild gleich, der Gang
# wirkte steif). Im Bild "Aufwärts" (Zyklusbild WALK_UP) werden Kopf, Rumpf und Oberschenkel um 1 px angehoben und
# die Zeile WALK_UP_ROW verdoppelt (Beine 1 px länger); Unterschenkel und Füße bleiben, der Standfuß steht weiter.
# Die Laufzellen sind dafür 1 px höher (41) als die Stehzellen.
WALK_UP = 2
WALK_UP_ROW = 33
# Übergang Laufen -> Stehen: Die KI hat Lauf- und Stehbilder mit verschieden gezeichnetem Rumpf und Paket gemalt;
# beim direkten Wechsel sprangen Rumpf, Paket und das hintere Bein gleichzeitig. Ein Übergangsbild (Rumpf aus dem
# letzten Laufbild, Beine aus dem Stehbild) teilt den Wechsel in zwei kleinere Schritte (erst Beine, dann Rumpf).
TRANSITION_FROM = 0          # Zyklusbild, auf dem der Dachs anhält (Kontakt)
# Paket am Kai: Lage in der Szene (muss zu main.gd passen, das sie aus sprites.json liest)
PARCEL_POS = (149, 138)


def strip(frames, pal):
    """Gleich große Zellen (Index-Arrays, -1 = transparent) nebeneinander als RGBA-Streifen."""
    ch, cw = frames[0].shape
    out = np.zeros((ch, cw * len(frames), 4), np.uint8)
    for i, f in enumerate(frames):
        m = f >= 0
        sub = out[:, i * cw:(i + 1) * cw]
        sub[m, :3] = pal[f[m]]
        sub[m, 3] = 255
    return out


def items_icons(pal_fixed):
    """Inventar-Symbole: 2x2-Raster des KI-Bildes zerlegen, auf 26x17 verkleinern, eigene 10 Farben."""
    im = Image.open(STYLE / 'assets/raw/items.png').convert('RGBA')
    a = np.asarray(im)
    op = a[..., 3] >= 128
    H, W = op.shape
    cells = [(0, 0, W // 2, H // 2), (W // 2, 0, W, H // 2), (0, H // 2, W // 2, H), (W // 2, H // 2, W, H)]
    crops = []
    for x0, y0, x1, y1 in cells:
        sub = op[y0:y1, x0:x1]
        # nur der größte zusammenhängende Spalten-/Zeilenbereich (Splitter benachbarter Symbole weg)
        xr = max(build_badger.runs(sub.any(0), 12), key=lambda r: sub[:, r[0]:r[1]].sum())
        sub2 = sub[:, xr[0]:xr[1]]
        yr = max(build_badger.runs(sub2.any(1), 12), key=lambda r: sub2[r[0]:r[1]].sum())
        crop = im.crop((x0 + xr[0], y0 + yr[0], x0 + xr[1], y0 + yr[1]))
        ca = np.asarray(crop).copy()
        crops.append(Image.fromarray(ca))
    smalls = []
    for c in crops:
        s = min(24 / c.width, 15 / c.height)
        smalls.append(build_badger.premult_box(c, (max(1, round(c.width * s)), max(1, round(c.height * s)))))
    px = np.concatenate([sm[sm[..., 3] > 128][:, :3] for sm in smalls])
    ipal = vga6(kmeans(px, ITEM_N, iters=20, seed=4))
    icons = []
    for sm in smalls:
        al = sm[..., 3] > 128
        idx = nearest(sm[..., :3], ipal)
        out = np.zeros(sm.shape[:2] + (4,), np.uint8)
        out[al, :3] = ipal[idx[al]]
        out[al, 3] = 255
        # 1-px Kontur aus der Oberflächenpalette
        pad = np.pad(al, 1)
        edge = al & (~pad[:-2, 1:-1] | ~pad[2:, 1:-1] | ~pad[1:-1, :-2] | ~pad[1:-1, 2:])
        out[edge, :3] = vga6(UI_COLORS[11][1])
        icons.append(out)
    cw, ch = 26, 17
    sheet = np.zeros((ch, cw * 4, 4), np.uint8)
    for i, ic in enumerate(icons):
        y0 = (ch - ic.shape[0]) // 2
        x0 = i * cw + (cw - ic.shape[1]) // 2
        sheet[y0:y0 + ic.shape[0], x0:x0 + ic.shape[1]] = ic
    return sheet, ipal


def walk_with_bob(frames):
    """Laufbilder 40 -> 41 Zeilen: oben eine leere Zeile, im Bild WALK_UP stattdessen Kopf und Rumpf 1 px höher."""
    out = []
    for i, f in enumerate(frames):
        if i == WALK_UP:
            g = np.concatenate([f[:WALK_UP_ROW + 1], f[WALK_UP_ROW:WALK_UP_ROW + 1], f[WALK_UP_ROW + 1:]])
        else:
            g = np.concatenate([np.full((1, f.shape[1]), -1), f])
        out.append(g)
    return out


def transition(walk0, stand0, walk_anchor, stand_anchor, dark):
    """Übergangsbild in Stehzelle: Rumpf (Zeilen < LEG_ROW) aus dem Laufbild, am Kopf ausgerichtet, Beine aus dem
    Stehbild, danach Kontur an den neuen Rändern."""
    dx = walk_anchor - stand_anchor
    assert dx >= 0 and (walk0[:, :dx] < 0).all(), 'Laufbild ragt links aus der Stehzelle'
    leg = build_badger.LEG_ROW
    out = np.full(stand0.shape, -1)
    w = min(stand0.shape[1], walk0.shape[1] - dx)
    out[:leg, :w] = walk0[:leg, dx:dx + w]
    out[leg:] = stand0[leg:]
    return build_badger.add_outline(out, dark)


def parcel_shadow_color(meta):
    """Schatten des Pakets: der statische Hintergrund-Eintrag, der dem abgedunkelten Pflaster unter dem Paket am
    nächsten kommt (keine neue Farbe)."""
    pal = np.array([[int(h[k:k + 2], 16) for k in (0, 2, 4)] for h in meta['palette']], np.float64)
    idx = np.asarray(Image.open(ART / 'bg_index.png')).astype(int)
    x0, y0 = PARCEL_POS
    under = pal[idx[y0 + 10, x0 + 1:x0 + 14]].mean(0)
    st0, st1 = meta['ranges']['static']
    lab = oklab(pal[st0:st1])
    return pal[st0 + int(np.argmin(((lab - oklab((under * 0.5)[None])[0]) ** 2).sum(-1)))]


def parcel(pal, mat, shadow):
    """Paket auf dem Kai, 14x11: helle Oberseite in leichter Draufsicht (2 px, Schnur längs), Vorderseite aus
    Packpapier mit Schnurkreuz und schattiger Unterkante, darunter eine dunkle Schattenzeile auf dem Pflaster
    (1 px nach rechts versetzt, Licht der Laterne von links). Gleiche Töne wie das Paket unter dem Arm des Dachses.
    Erste Fassung (13x9) war ein flaches Rechteck von vorn ohne Oberseite und Schatten und wirkte aufgeklebt."""
    lab = build_badger.oklab(pal)
    M = build_badger.MATERIALS
    pk = [i for i in range(len(pal)) if mat[i] == M.index('paket')]
    br = [i for i in range(len(pal)) if mat[i] == M.index('braun')]
    hl = [i for i in range(len(pal)) if mat[i] == M.index('hell')]
    P = max(pk, key=lambda i: lab[i, 0])            # Papier
    S = min(pk, key=lambda i: lab[i, 0])            # Schattenseite
    D = min(br, key=lambda i: lab[i, 0])            # Schnur
    Lt = sorted(hl, key=lambda i: lab[i, 0])[len(hl) // 2]   # Oberkante (mittleres Hell)
    cmap = {'P': pal[P], 'S': pal[S], 'D': pal[D], 'L': pal[Lt], 'K': vga6(UI_COLORS[11][1]), 'Z': shadow}
    rows = [
        ".KKKKKKKKKKK..",
        "KLLLLLDLLLLLK.",
        "KLLLLLDLLLLLK.",
        "KPPPPPDPPPPSK.",
        "KPPPPPDPPPPSK.",
        "KDDDDDDDDDDDK.",
        "KPPPPPDPPPPSK.",
        "KPPPPPDPPPPSK.",
        "KSSSSSDSSSSSK.",
        ".KKKKKKKKKKKZ.",
        "..ZZZZZZZZZZZZ",
    ]
    out = np.zeros((len(rows), len(rows[0]), 4), np.uint8)
    for y, r in enumerate(rows):
        for x, ch in enumerate(r):
            if ch in cmap:
                out[y, x, :3] = cmap[ch]
                out[y, x, 3] = 255
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--preview')
    a = ap.parse_args()
    meta = json.loads((ART / 'palette.json').read_text())
    rows, spal, cells, smat = build_badger.build(40, outline=True)
    spal = vga6(spal)
    assert len(spal) <= SPRITE_N, f'Figur hat {len(spal)} Farben, Platz für {SPRITE_N}'
    (wcw, wch, wA), (scw, sch, sA) = cells
    dark = int(np.argmin(oklab(spal)[:, 0]))
    wframes = walk_with_bob([rows[0][i] for i in WALK_ORDER])
    walk = strip(wframes, spal)
    # Der Schal des Laufbilds ragt am Kopf ausgerichtet 1 Spalte weiter nach hinten als die Stehzelle: Stehzellen
    # links auffüllen (Anker rückt mit, die Lage im Spiel bleibt gleich)
    w0 = rows[0][WALK_ORDER[TRANSITION_FROM]]
    need = max(0, (wA - sA) - int(np.flatnonzero((w0 >= 0).any(0)).min()))
    sframes = [np.pad(f, ((0, 0), (need, 0)), constant_values=-1) for f in rows[1]]
    sA, scw = sA + need, scw + need
    trans = transition(w0, sframes[0], wA, sA, dark)
    stand_frames = sframes + [trans]
    stand = strip(stand_frames, spal)
    icons, ipal = items_icons(spal)
    par = parcel(spal, smat, parcel_shadow_color(meta))
    for name, arr in (('badger_walk', walk), ('badger_stand', stand), ('items', icons), ('parcel', par)):
        Image.fromarray(arr, 'RGBA').save(ART / f'{name}.png')
        shutil.copy2(ART / f'{name}.png', ASSETS / f'{name}.png')
    info = {'walk': {'frames': len(WALK_ORDER), 'cell': [wcw, wframes[0].shape[0]], 'anchor_x': wA,
                     'source_frames': WALK_ORDER, 'step_px': WALK_STEP_PX, 'up_frame': WALK_UP},
            'stand': {'frames': len(stand_frames), 'cell': [scw, sch], 'anchor_x': sA,
                      'transition_frame': len(stand_frames) - 1},
            'items': {'cell': [26, 17], 'count': 4},
            'parcel': {'pos': list(PARCEL_POS), 'size': [par.shape[1], par.shape[0]]}}
    (ART / 'sprites.json').write_text(json.dumps(info, indent=1))
    pal = meta['palette']
    for i, (_, c) in UI_COLORS.items():
        pal[i] = '%02x%02x%02x' % tuple(int(v) for v in vga6(c))
    for j in range(SPRITE_N):
        c = spal[j] if j < len(spal) else spal[-1]
        pal[SPRITE0 + j] = '%02x%02x%02x' % tuple(int(v) for v in c)
    for j in range(ITEM_N):
        pal[ITEM0 + j] = '%02x%02x%02x' % tuple(int(v) for v in np.round(ipal[j]))
    meta['palette'] = pal
    meta['ui_colors'] = {name: i for i, (name, _) in UI_COLORS.items()}
    meta['sprite_colors'] = [SPRITE0, SPRITE0 + SPRITE_N]
    (ART / 'palette.json').write_text(json.dumps(meta, indent=1))
    # Prüfung: jede Sprite-Farbe ist ein Paletteneintrag
    pset = {tuple(int(pal[i][k:k + 2], 16) for k in (0, 2, 4)) for i in range(256)}
    for name, arr in (('walk', walk), ('stand', stand), ('items', icons), ('parcel', par)):
        cols = {tuple(c) for c in arr[arr[..., 3] > 0][:, :3]}
        missing = cols - pset
        print(f'{name}: {arr.shape[1]}x{arr.shape[0]}, {len(cols)} Farben, außerhalb der Palette: {len(missing)}')
    off = sum(1 for h in pal for k in (0, 2, 4) if (v := int(h[k:k + 2], 16)) != int(vga6(v)))
    print(f'Palette: {off} von 768 Kanalwerten außerhalb des 6-Bit-DAC-Rasters')
    print(json.dumps(info))
    if a.preview:
        pv = pathlib.Path(a.preview)
        for name, arr in (('walk', walk), ('stand', stand), ('items', icons), ('parcel', par)):
            bg = Image.new('RGBA', (arr.shape[1], arr.shape[0]), (58, 46, 92, 255))
            bg.alpha_composite(Image.fromarray(arr, 'RGBA'))
            bg.resize((bg.width * 6, bg.height * 6), Image.NEAREST).save(pv / f'sp_{name}.png')


if __name__ == '__main__':
    main()
