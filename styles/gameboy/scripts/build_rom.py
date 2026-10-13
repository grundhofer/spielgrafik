"""Baut den "ROM-Inhalt" der Handheld-Demo: Kacheln (2 Bit je Pixel), Hintergrundkarte, Kachelanimationen,
Schrift und Rahmen fürs Window, Sprite-Kacheln und Metasprites. Schreibt demo/rom/rom.json und Vorschaubilder
nach assets/. Prüft dabei die Hardwaregrenzen (4 Töne, 256 Hintergrundkacheln, 384 Kacheln VRAM, Sprite-Töne
je Palette, 8x16-Paare).

  .venv/bin/python styles/gameboy/scripts/build_rom.py
"""
import json
import os
import pathlib
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(__file__))
import badger  # noqa: E402
import font8  # noqa: E402
import pix  # noqa: E402
import scene  # noqa: E402

ROOT = pathlib.Path(__file__).resolve().parent.parent
OUT = ROOT / "demo" / "rom" / "rom.json"
ASSETS = ROOT / "assets"

BGP = 0b11100100      # Farbe n -> Ton n
OBP0 = 0b11100000     # Farbe 1 -> Ton 0, 2 -> 2, 3 -> 3 (Dachs)
OBP1 = 0b11100100     # Farbe 1 -> Ton 1, 2 -> 2, 3 -> 3 (Rauch, Möwe)
OBP0_MAP = {0: 1, 2: 2, 3: 3}
OBP1_MAP = {1: 1, 2: 2, 3: 3}

MAP_ROWS = 13         # Kachelzeilen der Szene (y 0-103)
CLOUD_ROWS = (1, 2)   # Kachelzeilen mit eigenem Scroll (256 px breit sichtbar)
PRIORITY = ["lantern", "beam", "stars", "water"]
WATER_MIN = 0.2
TEXT_SLOTS = 36       # 2 Textzeilen x 18 Zeichen (Seite und Auswahl je 2 Zeilen mit Leerzeile dazwischen)
CHARS = (" ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyzÄÖÜäöüß0123456789.,!?:;-'\"()>")


def tile_bytes(t):
    """8x8 Farbnummern -> 16 Byte im 2bpp-Format (je Zeile: Bit 0, Bit 1; linkes Pixel = höchstes Bit)."""
    out = bytearray()
    for row in t:
        lo = hi = 0
        for x, v in enumerate(row):
            lo |= (int(v) & 1) << (7 - x)
            hi |= ((int(v) >> 1) & 1) << (7 - x)
        out += bytes([lo, hi])
    return bytes(out)


def visible_cells():
    cells = []
    for r in range(MAP_ROWS):
        cols = 32 if r in CLOUD_ROWS else 20
        cells += [(r, c) for c in range(cols)]
    return cells


def cut(img, r, c):
    return img[r * 8:(r + 1) * 8, c * 8:(c + 1) * 8]


# ------------------------------------------------------------------ Hintergrund

def build_bg():
    base = scene.draw()
    assert base.min() >= 0 and base.max() <= 3
    cells = visible_cells()
    states = {}
    for ch, n in scene.CHANNELS.items():
        states[ch] = [scene.draw({ch: s}) for s in range(n)]
    # Berührt eine Kachel mehrere Animationen, gewinnt die erste in PRIORITY; die übrigen bleiben in dieser
    # Kachel auf Zustand 0 stehen (so machen es die Originale: eine Kachel hat nur eine Animationsfolge).
    owner, frozen = {}, {}
    for ch in PRIORITY:
        imgs = states[ch]
        for cell in cells:
            ref = cut(base, *cell)
            if any(not np.array_equal(cut(im, *cell), ref) for im in imgs[1:]):
                if cell in owner:
                    frozen.setdefault(ch, []).append(cell)
                    continue
                owner[cell] = ch
    # Wasser nur dort animieren, wo mindestens WATER_MIN der Kachel sichtbares Wasser ist; schmale Reste an
    # Booten, Masten und Felsen bleiben stehen (spart Kacheln und Kopierzeit im VBlank)
    scene.PROBE["fill"] = 1
    pa = scene.draw()
    scene.PROBE["fill"] = 2
    pb = scene.draw()
    scene.PROBE["fill"] = None
    vis = pa != pb
    for cell, ch in list(owner.items()):
        r, c = cell
        if ch == "water" and vis[r * 8:r * 8 + 8, c * 8:c * 8 + 8].mean() < WATER_MIN:
            del owner[cell]
            frozen.setdefault("water", []).append(cell)
    # Schlüssel je Position: statisch = Kachelbytes, animiert = (Kanal, Bytes je Zustand)
    keys = {}
    for cell in cells:
        ch = owner.get(cell)
        if ch is None:
            keys[cell] = ("static", tile_bytes(cut(base, *cell)))
        else:
            keys[cell] = (ch, tuple(tile_bytes(cut(im, *cell)) for im in states[ch]))
    uniq = []
    index = {}
    for cell in cells:
        k = keys[cell]
        if k not in index:
            index[k] = len(uniq)
            uniq.append(k)
    # Kartenzellen außerhalb der Szene (unter dem Window, rechts außerhalb): einfarbig dunkle Kachel
    dark = ("static", tile_bytes(np.full((8, 8), 3, np.int8)))
    if dark not in index:
        index[dark] = len(uniq)
        uniq.append(dark)
    bg_map = [[index[dark]] * 32 for _ in range(32)]
    for cell in cells:
        r, c = cell
        bg_map[r][c] = index[keys[cell]]
    # unsichtbare Kartenzellen: Kachel des Himmels links oben wiederverwenden
    return base, uniq, bg_map, owner, frozen


# ------------------------------------------------------------------ Schrift und Rahmen

def glyph_tiles():
    """Eigene 8x8-Schrift (scripts/font8.py, CC0) plus Pfeile ▼ und ▶."""
    g = font8.glyphs()
    missing = [ch for ch in CHARS + "▼▶" if ch not in g]
    if missing:
        raise SystemExit(f"Schrift: Zeichen fehlen {missing}")
    return {ch: g[ch] for ch in CHARS + "▼▶"}


BORDER = {
    "tl": """
00000000
00333333
03322222
03200000
03200000
03200000
03200000
03200000""",
    "t": """
00000000
33333333
22222222
00000000
00000000
00000000
00000000
00000000""",
    "tr": """
00000000
33333300
22222330
00000230
00000230
00000230
00000230
00000230""",
    "l": """
03200000
03200000
03200000
03200000
03200000
03200000
03200000
03200000""",
    "r": """
00000230
00000230
00000230
00000230
00000230
00000230
00000230
00000230""",
    "bl": """
03200000
03200000
03200000
03200000
03322222
00333333
00000000
00000000""",
    "b": """
00000000
00000000
00000000
00000000
22222222
33333333
00000000
00000000""",
    "b_more": """
00000000
00000000
03333300
00333000
22232222
33333333
00000000
00000000""",
    "br": """
00000230
00000230
00000230
00000230
22222330
33333300
00000000
00000000""",
}


# ------------------------------------------------------------------ Sprites

SMOKE = [  # 8x8 oben im 8x16-Sprite, Töne über OBP1 (1 hell, 2 dunkel): dunkler Rauch, oben angeleuchtet
    """
..2112..
.211122.
21112222
22122222
.222222.
..2222..
........
........""",
    """
........
...12...
..1122..
..2222..
...22...
........
........
........""",
    """
........
........
...2....
..2.2...
...2....
........
........
........""",
]

GULL = [  # 16x8 in zwei 8x16-Sprites (obere Hälfte), Flügel oben / unten
    """
.3..........3...
.33........33...
..33..11..33....
...3311113312...
....3111113.....
.....33333......
................
................""",
    """
................
................
......11........
..33311113333...
.33..31113..33..
.3...33333...3..
................
................""",
]


def sprite_tiles(box, cmap):
    """16xH-Bild (Töne, -1 durchsichtig) -> Liste von 8x16-Paaren (Farbnummern), Spalte für Spalte, oben nach unten."""
    h, w = box.shape
    assert h % 16 == 0 and w % 8 == 0
    out = []
    for ry in range(0, h, 16):
        for cx in range(0, w, 8):
            blk = box[ry:ry + 16, cx:cx + 8]
            col = np.zeros((16, 8), np.int8)
            for y in range(16):
                for x in range(8):
                    v = blk[y, x]
                    if v >= 0:
                        if v not in cmap:
                            raise SystemExit(f"Sprite-Ton {v} nicht in Palette {cmap}")
                        col[y, x] = cmap[v]
            out.append(((cx, ry), col))
    return out


def build_obj():
    pairs = []          # Liste eindeutiger 8x16-Paare (Bytes)
    pidx = {}

    def add(col):
        b = tile_bytes(col[:8]) + tile_bytes(col[8:])
        if not col.any():
            return -1   # leer: kein Sprite nötig
        if b not in pidx:
            pidx[b] = len(pairs)
            pairs.append(b)
        return pidx[b]

    metas = {}

    def meta(name, box, cmap, pal):
        parts = []
        for (dx, dy), col in sprite_tiles(box, cmap):
            k = add(col)
            if k >= 0:
                parts.append([dx, dy, 2 * k, pal])
        metas[name] = parts

    walk = badger.walk_frames()
    for i, f in enumerate(walk):
        badger.check_palette(f)
        meta(f"walk{i}", f, OBP0_MAP, 0)
    for k, f in badger.stand_frames().items():
        badger.check_palette(f)
        meta(k, f, OBP0_MAP, 0)
    for i, s in enumerate(SMOKE):
        a = np.full((16, 8), -1, np.int8)
        a[:8] = pix.stamp(s)[:8, :8]
        meta(f"smoke{i}", a, OBP1_MAP, 1)
    for i, g in enumerate(GULL):
        a = np.full((16, 16), -1, np.int8)
        a[:8] = pix.stamp(g)[:8, :16]
        meta(f"gull{i}", a, OBP1_MAP, 1)
    return pairs, metas, walk


# ------------------------------------------------------------------ alles

def main():
    base, uniq, bg_map, owner, frozen = build_bg()
    glyphs = glyph_tiles()
    border = {k: pix.stamp(v) for k, v in BORDER.items()}
    border["blank"] = np.zeros((8, 8), np.int8)
    n_scene = len(uniq)
    win_ids = {}
    win_tiles = []
    for name, t in border.items():
        win_ids[name] = n_scene + len(win_tiles)
        win_tiles.append(tile_bytes(t))
    # Textpuffer: 2 Zeilen x 18 Zeichen eigene Kacheln; beim Tippen kopiert das Spiel die Glyphe aus dem ROM
    # in die nächste Pufferkachel (die Schrift selbst liegt nicht im VRAM)
    win_ids["text0"] = n_scene + len(win_tiles)
    for i in range(TEXT_SLOTS):
        win_tiles.append(tile_bytes(np.zeros((8, 8), np.int8)))
    n_bg = n_scene + len(win_tiles)
    if n_bg > 256:
        raise SystemExit(f"Hintergrund + Window brauchen {n_bg} Kacheln, erlaubt 256")

    pairs, metas, walk = build_obj()
    n_obj = 2 * len(pairs)
    if n_obj > 128:
        raise SystemExit(f"Sprites brauchen {n_obj} Kacheln, vorgesehen 0-127")

    def bg_slot(i):
        return 256 + i if i < 128 else i

    vram = [b"\0" * 16] * 384
    anims = {}
    for i, k in enumerate(uniq):
        if k[0] == "static":
            vram[bg_slot(i)] = k[1]
        else:
            ch, frames = k
            vram[bg_slot(i)] = frames[0]
            a = anims.setdefault(ch, {"slots": [], "frames": [[] for _ in frames]})
            a["slots"].append(bg_slot(i))
            for s, fb in enumerate(frames):
                a["frames"][s].append(fb.hex())
    for i, t in enumerate(win_tiles):
        vram[bg_slot(n_scene + i)] = t
    for i, p in enumerate(pairs):
        vram[2 * i] = p[:16]
        vram[2 * i + 1] = p[16:]
    used = {"bg_scene": n_scene, "bg_window": len(win_tiles), "bg_total": n_bg, "obj": n_obj,
            "vram_total": n_bg + n_obj, "anim_slots": {k: len(v["slots"]) for k, v in anims.items()},
            "animated_cells": {ch: sum(1 for v in owner.values() if v == ch) for ch in scene.CHANNELS},
            "frozen_cells": {ch: len(v) for ch, v in frozen.items()}}
    rom = {
        "_comment": "Erzeugt von scripts/build_rom.py. Kacheln im 2bpp-Format (16 Byte je 8x8) wie im Videospeicher.",
        "bgp": BGP, "obp0": OBP0, "obp1": OBP1,
        "vram": [t.hex() for t in vram],
        "bg_map": bg_map,
        "anims": anims,
        "window": {"ids": win_ids, "text_slots": TEXT_SLOTS},
        "font": {ch: tile_bytes(g).hex() for ch, g in glyphs.items()},
        "sprites": metas,
        "walk_step_px": badger.STEP_PX,
        "badger_foot_row": badger.FOOT_ROW,
        "scene": {"feet_y": scene.FEET_Y, "chimney": list(scene.CHIMNEY_TOP), "cloud_y": [scene.CLOUD_Y0, scene.CLOUD_Y1],
                  "parcel": list(scene.PARCEL), "lamp": list(scene.LAMP)},
        "used": used,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(rom, ensure_ascii=False, separators=(",", ":")))
    # Vorschaubilder
    ASSETS.mkdir(exist_ok=True)
    pix.save_preview(base[:, :160], ASSETS / "bg_preview.png")
    pix.save_preview(base, ASSETS / "bg_map_256.png")
    sheet = np.zeros((8 * 16, 8 * 16), np.int8)
    for i in range(n_bg):
        t = vram[bg_slot(i)]
        arr = decode(t)
        sheet[(i // 16) * 8:(i // 16) * 8 + 8, (i % 16) * 8:(i % 16) * 8 + 8] = arr
    pix.save_preview(sheet, ASSETS / "tiles_bg.png", 2)
    fs = np.zeros((8 * 6, 8 * 16), np.int8)
    for i, (ch, g) in enumerate(glyphs.items()):
        fs[(i // 16) * 8:(i // 16) * 8 + 8, (i % 16) * 8:(i % 16) * 8 + 8] = g
    pix.save_preview(fs, ASSETS / "font_tiles.png", 2)
    frames = walk + list(badger.stand_frames().values())
    strip = np.full((32, 16 * len(frames)), -1, np.int8)
    for i, f in enumerate(frames):
        strip[:, i * 16:(i + 1) * 16] = f
    pix.save_preview(strip, ASSETS / "badger_frames.png", 1, transparent=(255, 0, 255))
    print(json.dumps(used, ensure_ascii=False))


def decode(b):
    a = np.zeros((8, 8), np.int8)
    for y in range(8):
        lo, hi = b[2 * y], b[2 * y + 1]
        for x in range(8):
            a[y, x] = ((lo >> (7 - x)) & 1) | (((hi >> (7 - x)) & 1) << 1)
    return a


if __name__ == "__main__":
    main()
