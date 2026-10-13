#!/usr/bin/env python3
"""Spieldaten der 8-Bit-Konsole für die Godot-Demo bauen: demo/rom/rom.json.

Inhalt (wie ein Steckmodul mit Bankumschaltung, 1-KB-Bänke zu 64 Kacheln):
  Bänke  0- 3  Hintergrund-Satz X: Himmel und Dach (Kachelzeilen 0-7) und Kai (16-21), höchstens 256 Kacheln
  Bänke  4- 5  Wasserstreifen (Kachelzeilen 8-15), feste Kacheln (Kachelnummern 128-255)
  Bänke  6-21  Wasserstreifen, animierte Kacheln (Nummern 0-127), 8 Phasen zu je 2 KB
  Bänke 22-23  Schrift und Fensterrahmen (Nummern 0-127)
  Bänke 24-25  Titelschrift: dieselben Glyphen 1 px tiefer gesetzt (Nummern 128-255 im Fensterbereich)
  Bänke 26-29  Sprites (Musterspeicher $1000, 256 Kacheln, 8x16-Modus)
Die Demo schaltet die Hintergrundbänke an den Zeilen 64, 128 und 168 um (Zeilen-Interrupt eines Mappers)
und wechselt für das Wasser jede Phase die 2-KB-Bank. Namenstabelle, Attributtabelle (gepackte Bytes),
Paletten-RAM und die Metasprites stehen ebenfalls im JSON.
"""
import json, pathlib, sys
import numpy as np
from PIL import Image, ImageDraw, ImageFont

HERE = pathlib.Path(__file__).resolve().parent
ENTRY = HERE.parent
sys.path.insert(0, str(HERE))
import neslib, badger_px  # noqa: E402

BANK_X, BANK_WS, BANK_WA, BANK_FONT, BANK_TITLE, BANK_SPR = 0, 4, 6, 22, 24, 26
NBANKS = 30
WALK = ["contact_a", "pass_a", "contact_b", "pass_b"]


def tiles_of(img, rows, cols=range(32)):
    return {(ty, tx): img[ty * 8:ty * 8 + 8, tx * 8:tx * 8 + 8] for ty in rows for tx in cols}


class Bank:
    def __init__(self):
        self.chr = np.zeros((NBANKS * 64, 8, 8), np.uint8)

    def put(self, bank, idx, px):
        self.chr[bank * 64 + idx] = px


def build_bg(chrb):
    d = np.load(ENTRY / "assets" / "bg_build.npz")
    ph = d["phases"]                      # 8 x 176 x 256, Farbnummern 0-3
    attr = d["attr"]
    nt = np.zeros((30, 32), np.int32)
    # Satz X: Zeilen 0-7 und 16-21
    xset = {bytes(16): 0}
    for (ty, tx), t in tiles_of(ph[0], list(range(0, 8)) + list(range(16, 22))).items():
        key = neslib.tile_bytes(t)
        if key not in xset:
            xset[key] = len(xset)
        nt[ty, tx] = xset[key]
    if len(xset) > 256:
        raise SystemExit(f"Satz X: {len(xset)} Kacheln > 256")
    for key, i in xset.items():
        chrb.put(BANK_X + i // 64, i % 64, neslib.bytes_tile(key))
    # Wasserstreifen: feste Kacheln ab 128, animierte Folgen ab 0
    stat, anim = {}, {(bytes(16),) * 8: 0}
    for ty in range(8, 16):
        for tx in range(32):
            seq = tuple(neslib.tile_bytes(ph[k, ty * 8:ty * 8 + 8, tx * 8:tx * 8 + 8]) for k in range(8))
            if len(set(seq)) == 1:
                if seq[0] not in stat:
                    stat[seq[0]] = 128 + len(stat)
                nt[ty, tx] = stat[seq[0]]
            else:
                if seq not in anim:
                    anim[seq] = len(anim)
                nt[ty, tx] = anim[seq]
    if len(stat) > 128 or len(anim) > 128:
        raise SystemExit(f"Wasserstreifen: {len(stat)} feste, {len(anim)} animierte Kacheln (je höchstens 128)")
    for key, i in stat.items():
        j = i - 128
        chrb.put(BANK_WS + j // 64, j % 64, neslib.bytes_tile(key))
    for seq, i in anim.items():
        for k in range(8):
            chrb.put(BANK_WA + 2 * k + i // 64, i % 64, neslib.bytes_tile(seq[k]))
    # Attributtabelle: 8x8 Bytes, je Byte 4 Blöcke (links oben, rechts oben, links unten, rechts unten)
    blocks = np.full((16, 16), 2, np.int32)            # Textfenster und Rand: Palette 2 (enthält Weiß)
    blocks[:11] = attr
    at = []
    for ay in range(8):
        for ax in range(8):
            tl, tr = blocks[2 * ay, 2 * ax], blocks[2 * ay, 2 * ax + 1]
            bl, br = blocks[2 * ay + 1, 2 * ax], blocks[2 * ay + 1, 2 * ax + 1]
            at.append(int(tl | (tr << 2) | (bl << 4) | (br << 6)))
    stats = {"set_x": len(xset), "water_static": len(stat), "water_anim": len(anim),
             "scene_tiles_total": len(xset) + len(stat) + len(anim) * 8}
    return nt, at, [int(c) for p in d["pals"] for c in p], stats, d


# --------------------------------------------------------------------------------------------- Schrift
FONT_CHARS = [chr(c) for c in range(32, 127)] + list("ÄÖÜäöüß") + ["▶", "▼"]
BOX = {"tl": 112, "tr": 113, "bl": 114, "br": 115, "h_top": 116, "h_bot": 117, "v_l": 118, "v_r": 119,
       "t_l": 120, "t_r": 121}


def build_font(chrb):
    f = ImageFont.truetype(str(ENTRY / "demo" / "fonts" / "PressStart2P-Regular.ttf"), 8)
    glyph, title = {}, {}
    for i, ch in enumerate(FONT_CHARS):
        im = Image.new("L", (8, 8), 0)
        dr = ImageDraw.Draw(im)
        dr.fontmode = "1"
        dr.text((0, 0), ch, font=f, fill=255)
        px = (np.asarray(im) > 127).astype(np.uint8) * 3        # Farbe 3 = Weiß (Palette 2)
        chrb.put(BANK_FONT + i // 64, i % 64, px)
        glyph[ch] = i
        # Titelschrift für den Ortsnamen im oberen Rahmen: 1 px tiefer, damit über dem Titel Schwarz steht.
        # Glyphen mit Unterlänge (Zeile 7 belegt: , _ g j p q y) fehlen dort; main.gd nimmt dann die normale.
        if not px[7].any():
            sh = np.zeros_like(px)
            sh[1:] = px[:7]
            chrb.put(BANK_TITLE + i // 64, i % 64, sh)
            title[ch] = 128 + i
    # Fensterrahmen: eine 2 px breite weiße Linie, 2 px vom Kachelrand, runde Ecken
    def tile(rows):
        return np.array([[3 if c == "#" else 0 for c in r] for r in rows], np.uint8)
    h_top = tile(["........", "........", "########", "########", "........", "........", "........", "........"])
    h_bot = h_top[::-1]
    v_l = h_top.T.copy()
    v_r = v_l[:, ::-1]
    tl = tile(["........", "........", "....####", "...#####", "..##....", "..##....", "..##....", "..##...."])
    tr = tl[:, ::-1]
    bl = tl[::-1]
    br = bl[:, ::-1]
    # Titel im oberen Rahmen: Linie endet mit einem Abstand
    t_l = tile(["........", "........", "######..", "######..", "........", "........", "........", "........"])
    t_r = t_l[:, ::-1]
    for name, px in (("tl", tl), ("tr", tr), ("bl", bl), ("br", br), ("h_top", h_top), ("h_bot", h_bot),
                     ("v_l", v_l), ("v_r", v_r), ("t_l", t_l), ("t_r", t_r)):
        i = BOX[name]
        chrb.put(BANK_FONT + i // 64, i % 64, px)
    return glyph, title


# --------------------------------------------------------------------------------------------- Sprites
class SprSheet:
    """Musterspeicher $1000 im 8x16-Modus: Paare (oben, unten) ab Kachel 0."""

    def __init__(self, chrb):
        self.chrb = chrb
        self.n = 0
        self.index = {}

    def add(self, px16):
        """px16: 16x8 Farbnummern 0-3 -> OAM-Kachelbyte (ungerade = Tabelle $1000)."""
        key = px16.tobytes()
        if key in self.index:
            return self.index[key]
        top, bot = 2 * self.n, 2 * self.n + 1
        for t, rows in ((top, px16[:8]), (bot, px16[8:])):
            self.chrb.put(BANK_SPR + t // 64, t % 64, rows)
        self.n += 1
        if self.n > 128:
            raise SystemExit("Sprite-Musterspeicher voll")
        self.index[key] = top | 1
        return top | 1


def cut(grid, x0, y0):
    """16x8-Ausschnitt aus einem Farbnummernfeld (außerhalb = 0)."""
    out = np.zeros((16, 8), np.uint8)
    h, w = grid.shape
    for y in range(16):
        for x in range(8):
            yy, xx = y0 + y, x0 + x
            if 0 <= yy < h and 0 <= xx < w:
                out[y, x] = grid[yy, xx]
    return out


def metasprite(sheet, grid, pal, ox=0, oy=0, cols=None, rows=None, skip_empty=True):
    """Feld (H x W, Farbnummern) in 8x16-Sprites zerlegen -> Liste [dx, dy, kachel, attribut]."""
    h, w = grid.shape
    out = []
    for y0 in (rows if rows is not None else range(0, h, 16)):
        for x0 in (cols if cols is not None else range(0, w, 8)):
            t = cut(grid, x0, y0)
            if skip_empty and not t.any():
                continue
            out.append([x0 + ox, y0 + oy, sheet.add(t), pal])
    return out


def grid_from(rows, mapping):
    h, w = len(rows), max(len(r) for r in rows)
    g = np.zeros((h, w), np.uint8)
    for y, r in enumerate(rows):
        for x, ch in enumerate(r):
            g[y, x] = mapping.get(ch, 0)
    return g


def build_sprites(chrb, bgd):
    sheet = SprSheet(chrb)
    spr = {}
    # Dachs 16x24: Auflage (Palette 2), Kopf (Palette 0), Körper (Palette 1), Beine (Palette 3), je 8x16-Sprites.
    # Kopfreihe beginnt 4 Zeilen über der Figur (Zeilen -4..11), die übrigen bei Zeile 12 (12..27).
    # Kopf, Körper und Auflage werden im Durchgang um bob = 1 px angehoben, die Beine nicht.
    kmap_head = {"K": 1, "W": 2, "G": 3}
    kmap_body = {"K": 1, "R": 2, "G": 3}
    kmap_over = {c: i + 1 for i, c in enumerate(badger_px.OVERLAY)}       # b 1, o 2, c 3
    kmap_legs = {"K": 1, "g": 2}
    S = badger_px.SPLIT
    frames = {}
    for name in badger_px.POSES:
        for blink in (False, True):
            if blink and name != "stand":
                continue
            bob = badger_px.POSES[name]["bob"]
            up = badger_px.upper(name, blink)                           # Zeilen 0-19
            head_rows = ["." * 16] * 4 + up[:S]                          # Zeilen -4..11
            body_rows = up[S:] + ["." * 16] * (16 - (len(up) - S))       # Zeilen 12..27
            leg_rows = badger_px.legs(name)[S:] + ["." * 16] * 4         # Zeilen 12..27
            ms = []
            # Reihenfolge = OAM-Reihenfolge: Auflage zuerst (liegt vorn), Kopf, Körper, Beine zuletzt (hinten)
            ms += metasprite(sheet, grid_from(body_rows, kmap_over), 2, 0, S - bob)
            ms += metasprite(sheet, grid_from(head_rows, kmap_head), 0, 0, -4 - bob)
            ms += metasprite(sheet, grid_from(body_rows, kmap_body), 1, 0, S - bob)
            ms += metasprite(sheet, grid_from(leg_rows, kmap_legs), 3, 0, S)
            frames[name + ("_blink" if blink else "")] = ms
    spr["badger"] = frames
    spr["badger_size"] = [badger_px.W, badger_px.H]

    # Leuchtturm aus dem KI-Bild (Systemfarben je Pixel, -1 = durchsichtig)
    lh = bgd["lighthouse"]
    box = bgd["lh_box"]                      # y0, y1, x0, x1 der Leinwand
    white = np.isin(lh, [0x20, 0x30, 0x37, 0x36])
    grey = np.isin(lh, [0x10, 0x00, 0x2D])
    dark = np.isin(lh, [0x0F, 0x0C, 0x08, 0x0D])
    red = np.isin(lh, [0x06, 0x16, 0x17, 0x26])
    dred = np.isin(lh, [0x07])
    tower = np.zeros(lh.shape, np.uint8)      # Palette 3: 1 Schwarz, 2 Grau $00, 3 Weiß $30
    tower[dark] = 1
    tower[grey] = 2
    tower[white] = 3
    tower[red | dred] = 1                     # unter dem Band schwarz, das Band liegt als Sprite davor
    # Lampenglas (Leinwandzeilen 25-27, Spalten 220-222; im KI-Bild gelb, beim Ausschneiden als Himmel
    # verworfen): im Turm dunkel, das Licht kommt als eigenes Sprite (an/aus)
    hole = np.zeros(lh.shape, bool)
    hole[9:12, 3:10] = True
    tower[hole & (tower == 0)] = 1
    band = np.zeros(lh.shape, np.uint8)       # Palette 1: 1 Schwarz, 2 Rot $16
    band[red] = 2
    band[dred] = 1
    # OAM-Reihenfolge: Band vor dem Turm
    spr["lighthouse"] = metasprite(sheet, band, 1, rows=range(24, 48, 16)) + metasprite(sheet, tower, 3)
    spr["lighthouse_pos"] = [int(box[2]), int(box[0])]
    # Leuchtfeuer: an / aus (Palette 2: 1 Braun, 2 Orange, 3 Hellgelb)
    ly, lx = 10, 5                            # Mitte des Lampenglases im Ausschnitt
    on = grid_from(["........", "........", "...3....", "..333...", ".33333..", "..333...", "...3....",
                    "........"] + ["........"] * 8, {"3": 3})
    on[1, 3] = on[7, 3] = 2
    on[4, 0] = on[4, 6] = 2
    off = grid_from(["........", "........", "........", "..222...", "..222...", "..222...", "........",
                     "........"] + ["........"] * 8, {"2": 2})
    ray = grid_from(["........"] * 3 + ["22.2.2.2", "33333333", "22.2.2.2"] + ["........"] * 10,
                    {"2": 2, "3": 3})
    spr["lamp_on"] = [[0, 0, sheet.add(on), 2]]
    spr["lamp_off"] = [[0, 0, sheet.add(off), 2]]
    spr["lamp_ray"] = sheet.add(ray)
    spr["lamp_pos"] = [int(box[2] + lx - 3), int(box[0] + ly - 4)]   # Sternmitte (Zeile 4, Spalte 3) auf die Lampe

    # Fensterlicht des Hauses: Scheiben aus dem KI-Bild (orange) -> Hellgelb mit orangem unterem Rand
    sf = bgd["sysfull"]
    wy0, wy1, wx0, wx1 = [int(v) for v in bgd["win_box"]]
    pane = np.isin(sf[wy0:wy1, wx0:wx1], [0x27, 0x37, 0x38, 0x28, 0x26])
    win_states = {}
    for name, (c_main, c_low) in {"bright": (3, 2), "dim": (2, 2)}.items():
        g = np.zeros(pane.shape, np.uint8)
        g[pane] = c_main
        low = pane & ~np.roll(pane, -1, axis=0)
        g[low] = c_low
        win_states[name] = metasprite(sheet, g, 2)
    spr["window"] = win_states
    spr["window_pos"] = [wx0, wy0]

    # Laternenglas: 3 Zustände (Flackern)
    ly0, ly1, lx0, lx1 = [int(v) for v in bgd["lan_box"]]
    glass = np.isin(sf[ly0:ly1, lx0:lx1], [0x27, 0x37, 0x38, 0x28, 0x26])
    lan = {}
    for name, fill in {"hi": 3, "mid": 2, "lo": 1}.items():
        g = np.zeros(glass.shape, np.uint8)
        g[glass] = fill
        if name == "hi":
            ys, xs = np.nonzero(glass)
            g[ys.max(), glass[ys.max()].nonzero()[0]] = 2
        lan[name] = metasprite(sheet, g, 2)
    spr["lantern"] = lan
    spr["lantern_pos"] = [lx0, ly0]

    # Rauch (Palette 3: 2 Grau, 3 Weiß), drei Größen
    puffs = {
        "s": ["........", "........", "...22...", "..2332..", "..2222..", "...22...", "........", "........"],
        "m": ["........", "..222...", ".23322..", ".233322.", ".222222.", "..2222..", "........", "........"],
        "l": [".2222...", "233322..", "2333322.", "2223222.", "2222222.", ".22222..", "........", "........"],
    }
    spr["smoke"] = {k: sheet.add(grid_from([r[:8] for r in v] + ["........"] * 8, {"1": 1, "2": 2, "3": 3}))
                    for k, v in puffs.items()}
    # Möwe (Palette 3: 1 Schwarz, 3 Weiß), zwei Flügelstellungen
    gull = {
        "up": ["........", "3.....3.", "33...33.", ".33.33..", "..313...", "...1....", "........", "........"],
        "down": ["........", "........", "........", ".33133..", "33.1.33.", "3.....3.", "........",
                 "........"],
    }
    spr["gull"] = {k: sheet.add(grid_from(v + ["........"] * 8, {"1": 1, "3": 3})) for k, v in gull.items()}
    # Paket am Kai (Palette 2: 1 Braun, 2 Orange, 3 Hellgelb)
    parcel = ["........"] * 8 + ["........", ".222222.", ".223322.", "11111111", ".221222.", ".221222.",
                                 ".111111.", "........"]
    parcel[9] = ".222122."
    spr["parcel"] = sheet.add(grid_from(parcel, {"1": 1, "2": 2, "3": 3}))
    spr["sprite_tiles_used"] = sheet.n * 2
    return spr


def main():
    chrb = Bank()
    nt, at, bgpal, stats, bgd = build_bg(chrb)
    glyph, title = build_font(chrb)
    spr = build_sprites(chrb, bgd)
    # Paletten-RAM: 4 Hintergrund- und 4 Sprite-Paletten, Eintrag 0 jeder Palette = Grundfarbe Schwarz
    pal = []
    for i in range(4):
        pal += [neslib.BLACK] + bgpal[3 * i:3 * i + 3]
    sprpal = [[0x0F, 0x30, 0x0A], [0x0F, 0x16, 0x0A], [0x07, 0x27, 0x38], [0x0F, 0x00, 0x30]]
    for p in sprpal:
        pal += [neslib.BLACK] + p
    chr_hex = []
    for b in range(NBANKS):
        raw = b"".join(neslib.tile_bytes(chrb.chr[b * 64 + i]) for i in range(64))
        chr_hex.append(raw.hex())
    rom = {
        "_comment": "Erzeugt von scripts/build_rom.py. CHR in 1-KB-Bänken (2-Bit-Planarformat, 16 Byte je Kachel).",
        "syspal": neslib.SYSPAL_HEX,
        "chr": chr_hex,
        "banks": {"x": BANK_X, "water_static": BANK_WS, "water_anim": BANK_WA, "font": BANK_FONT,
                  "title": BANK_TITLE, "sprites": BANK_SPR, "water_phases": 8},
        "nametable": nt.tolist(),
        "attributes": at,
        "palette": pal,
        "font": {ch: i for ch, i in glyph.items()},
        "title_font": title,
        "box": BOX,
        "sprites": spr,
        "stats": stats,
    }
    out = ENTRY / "demo" / "rom" / "rom.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(rom, ensure_ascii=False, separators=(",", ":")))
    print(f"{out}: {out.stat().st_size // 1024} KB; Hintergrund {stats}; Sprite-Kacheln {spr['sprite_tiles_used']}")


if __name__ == "__main__":
    main()
