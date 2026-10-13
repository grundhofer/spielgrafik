#!/usr/bin/env python3
"""Hintergrund des Hafens für die 8-Bit-Konsole bauen (Kachelebene, 256x176 = Namenstabellenzeilen 0-21).

Schritte
  1. KI-Bild assets/raw/bg2.png auf sein eigenes Kunstpixelraster zurückführen (reduce_grid.py, 237x161).
  2. Auf 256 Spalten verbreitern (Felsen der Landzunge und Himmel nach rechts fortsetzen), 3 Zeilen tiefer legen,
     damit der Horizont auf einer Attributgrenze (Zeile 64) liegt; gemalten Rauch entfernen.
  3. Leuchtturm, Fensterlicht und Laternenglas ausschneiden: sie werden Sprites (eigene Paletten, Blinken);
     im Hintergrund bleibt dort eine schwarze Silhouette.
  4. Wasser (8 Animationsphasen) und Kai (Gehweg, Kante, Mauer) als regelmäßige Kachelmuster neu setzen.
  5. Attributkarte von Hand (eine Palette je 16x16-Block) und je Pixel die nächste Farbe aus Schwarz + Blockpalette.
Ausgabe: assets/bg_build.npz (Farbnummern je Phase, Attribute, Paletten, Sprite-Ausschnitte) und Vorschauen.
"""
import pathlib, sys
import numpy as np
from PIL import Image

HERE = pathlib.Path(__file__).resolve().parent
ENTRY = HERE.parent
sys.path.insert(0, str(HERE))
import neslib, reduce_grid  # noqa: E402

W, H = 256, 176          # Namenstabellenzeilen 0-21; Zeilen 0-7 liegen im unsichtbaren Rand
DY = 3                   # KI-Zeile 0 -> Konsolenzeile 3 (Horizont KI 61 -> 64)
PHASES = 8               # Wasseranimation (Bankumschaltung)

# Paletten (Systemfarbnummern), Grundfarbe für alle: Schwarz $0F
PALS = [
    [0x02, 0x21, 0x27],  # 0 Meer und Nachthimmel: Tiefblau, Hellblau (Wellen, Sterne), Orange (Abendlicht)
    [0x02, 0x03, 0x24],  # 1 Abendhimmel oben: Tiefblau, Violett, Rosa (Raster, Wolken)
    [0x00, 0x10, 0x30],  # 2 Stein und Weiß: Grau, Hellgrau, Weiß (Haus, Kai, Felsen, Textfenster)
    [0x07, 0x17, 0x27],  # 3 Holz und Abendrot: Dunkelbraun, Rostrot, Orange (Dach, Fässer, Boote, Horizont)
]

# Attributkarte: Blockzeilen 0-10 (je 16 px), 16 Spalten. Von Hand nach dem Bildinhalt gesetzt.
ATTR = [
    "0000000000000000",  #   0- 15 Nachthimmel, Sterne
    "1111111111111111",  #  16- 31 Raster Tiefblau/Violett, Wolkenanfang
    "1111111111111111",  #  32- 47 Violett, Wolken
    "3333333333333333",  #  48- 63 Raster, Abendrot, Schornstein, Dach, Felsen oben
    "3330000000000000",  #  64- 79 Dach | Meer, Felsen (Gegenlicht)
    "2220000000000000",  #  80- 95 Hauswand | Meer, Felsen, Masten
    "2220000000000000",  #  96-111 Hauswand | Meer, Boote, Steg im Gegenlicht
    "2233000000000000",  # 112-127 Hauswand, Tür | Fässer, Kisten | Boote, Steg | Tau | Laternenpfahl
    "2222222222222222",  # 128-143 Gehweg
    "2222222222222222",  # 144-159 Kante, Mauer
    "2222222222222222",  # 160-175 Mauer
]

# Schattenseite des Hauses (Spalten 49-54): wenige kurze Fugen (Zeile, von, bis)
SHADOW_JOINTS = [(89, 49, 52), (95, 51, 54), (101, 49, 51), (106, 51, 54)]

# Fässer und Kisten von Hand im Holzblock (Palette 3: d Dunkelbraun, r Rostrot, o Orange, sonst Schwarz),
# Spalten 32-63, Zeilen 112-127 (genau die beiden Attributblöcke mit Palette 3). Das KI-Bild ergab nach dem
# Abbilden nur einen gestreiften Block. (x, y, Zeilen)
BARREL = [
    "..dddddd..",
    ".dooooood.",
    ".ddoooodd.",
    "drrrrrrrrd",
    "dddddddddd",
    "rorrrrrrrd",
    "rorrrrrrrd",
    "rorrrrrrrd",
    "rorrrrrrrd",
    "dddddddddd",
    "rorrrrrrrd",
    "rorrrrrrrd",
    "dddddddddd",
    ".dddddddd.",
]
CRATE_LOW = [
    "oooooooooooo",
    "oddrrrrrrrrd",
    "orrddrrrrrrd",
    "orrrrddrrrrd",
    "orrrrrrddrrd",
    "orrrrrrrrddd",
    "orrrrrrrrrrd",
    "dddddddddddd",
]
CRATE_TOP = [
    "oooooooooo",
    "orrrrrrrrd",
    "orddddddrd",
    "orrrrrrrrd",
    "orddddddrd",
    "orrrrrrrrd",
    "dddddddddd",
]
PROPS = [(32, 114, BARREL), (42, 114, BARREL), (52, 120, CRATE_LOW), (53, 113, CRATE_TOP)]


def load_native():
    cache = ENTRY / "assets" / "raw" / "bg2_native.npy"
    src = ENTRY / "assets" / "raw" / "bg2.png"
    if cache.exists() and cache.stat().st_mtime > src.stat().st_mtime:
        return np.load(cache)
    rgb, bx, by = reduce_grid.reduce(Image.open(src), (6.5, 6.44), 96)
    np.save(cache, rgb)
    return rgb


def compose(nat):
    """KI-Raster (161x237) -> Leinwand 176x256 in RGB, Rauch entfernt, rechts verbreitert."""
    nat = nat.copy()
    # gemalter Rauch über dem Schornstein (KI-Zeilen 29-46, Spalten 9-24): Himmel derselben Zeilen 120 px weiter
    nat[29:47, 9:25] = nat[29:47, 129:145]
    can = np.zeros((H, W, 3), np.float32)
    can[DY:DY + 161, :237] = nat
    can[:DY, :237] = nat[0]
    # rechts 19 Spalten: Himmel aus wolkenfreien Spalten 117-135 (gerade Verschiebung hält das Schachbrett),
    # Felsen ab KI-Zeile 50 aus den Spalten 218-236
    ext = np.zeros((H, 19, 3), np.float32)
    ext[:DY + 50] = can[:DY + 50, 117:136]
    ext[DY + 50:DY + 82] = can[DY + 50:DY + 82, 218:237]
    ext[DY + 82:] = neslib.SYSPAL[0x02]          # Wasser (Wellen setzt Schritt 4), Kai folgt als Muster
    can[:, 237:] = ext
    return can


def to_sys(rgb):
    lab = neslib.oklab(rgb)
    C = np.hypot(lab[..., 1], lab[..., 2])
    L = lab[..., 0]
    # Grauleiter der Konsole hat nur Schwarz, $00, $10, $30: dunkle Graus nach Schwarz, mittlere auf $00 heben
    Lg = np.interp(L, [0, 0.30, 0.36, 0.55, 0.66, 0.80, 0.86, 1], [0, 0.05, 0.59, 0.59, 0.80, 0.80, 1, 1])
    lab[..., 0] = np.where(C < 0.035, Lg, L)
    return lab


def nearest_in(lab, opts):
    d = ((lab[..., None, :] - neslib.SYS_LAB[opts][None, None]) ** 2).sum(-1)
    return d.argmin(-1)


def main():
    nat = load_native()
    can = compose(nat)
    lab = to_sys(can)
    sysfull = neslib.nearest_sys(can)            # freie Zuordnung (nur für Masken und Ausschnitte)

    # --- Sprite-Ausschnitte (Systemfarben, -1 = durchsichtig) --------------------------------------------
    # Leuchtturm: KI-Spalten 216-231 (=Leinwand gleich), KI-Zeilen 13-60 -> Leinwand 16-63
    lh_box = (16, 64, 216, 232)
    lh = sysfull[lh_box[0]:lh_box[1], lh_box[2]:lh_box[3]].copy()
    sky = np.isin(lh, [0x02, 0x03, 0x27, 0x04, 0x37]) | (np.arange(lh_box[0], lh_box[1])[:, None] >= DY + 56)
    lh_mask = ~sky
    lh_mask[:DY + 18 - lh_box[0]] = False        # oberhalb der Kappe nur Himmel
    lh = np.where(lh_mask, lh, -1)
    # Fensterlicht (Haus): Scheiben gelb in der Leinwand ermitteln
    win_box = (96, 112, 32, 48)
    # Laternenglas
    lan_box = (98, 114, 216, 224)

    # --- Hintergrund-Leinwand anpassen ------------------------------------------------------------------
    work = lab.copy()
    # Leuchtturm: wird ganz als Sprite gezeichnet (Palette mit Schwarz); dahinter Himmel derselben Zeile
    # 16 px weiter links (gerade Verschiebung hält das Schachbrett), damit der Wolkenstreifen scrollen kann
    y0, y1, x0, x1 = lh_box
    ys, xs = np.nonzero(lh_mask)
    work[ys + y0, xs + x0] = work[ys + y0, xs + x0 - 16]
    sysfull_bg = sysfull.copy()
    sysfull_bg[ys + y0, xs + x0] = sysfull[ys + y0, xs + x0 - 16]

    # --- Wasser: Maske und regelmäßige Wellenzeilen ------------------------------------------------------
    rows = np.arange(H)[:, None]
    water = np.isin(sysfull, [0x02, 0x11, 0x12, 0x01, 0x21]) & (rows >= 64) & (rows <= 125)
    water &= ~((np.arange(W)[None, :] >= 200) & (rows < 96) & ~np.isin(sysfull, [0x02, 0x11]))

    # --- Kai: Gehweg, Kante, Mauer als Kachelmuster --------------------------------------------------------
    quay_top = 126
    quay = np.zeros((H, W), np.int8) - 1     # Farbnummer in Palette 2 (0 Schwarz, 1 Grau, 2 Hellgrau, 3 Weiß)
    for y in range(quay_top, H):
        for x in range(W):
            if y < 162:                       # Gehweg aus Platten 32x9 im Verband, Fugen grau
                r = (y - quay_top) % 9
                off = 16 if ((y - quay_top) // 9) % 2 else 0
                c = 2
                if r == 8 or (x + off) % 32 == 0:
                    c = 1
                if ((x % 32) * 7 + ((y - quay_top) % 18) * 13) % 37 == 0 and r != 8:
                    c = 1                     # wenige Steinpunkte
                quay[y, x] = c
            elif y == 162:
                quay[y, x] = 3                # helle Kante
            elif y < 167:                     # Stirnseite der Platten; Zeile 167 schwarz (Abstand zum Fenstertitel)
                quay[y, x] = 0 if (x + 8) % 32 == 0 else 1
            else:
                quay[y, x] = 0
    # Gegenstände, die in den Gehweg ragen (Fässer, Kisten, Tau, Pfahl), behalten ihre Pixel
    keep = (rows >= quay_top) & (rows < 132) & ~np.isin(sysfull, [0x10, 0x00, 0x2D, 0x20, 0x30, 0x0C, 0x08,
                                                                   0x02, 0x11, 0x12, 0x21, 0x37]) \
        & (sysfull != neslib.BLACK)

    # --- Attribute und Farbnummern ----------------------------------------------------------------------
    attr = np.array([[int(c) for c in row] for row in ATTR])
    ci = np.zeros((H, W), np.uint8)
    for by in range(H // 16):
        for bx in range(W // 16):
            opts = [neslib.BLACK] + PALS[attr[by, bx]]
            blk = work[by * 16:(by + 1) * 16, bx * 16:(bx + 1) * 16]
            ci[by * 16:(by + 1) * 16, bx * 16:(bx + 1) * 16] = nearest_in(blk, opts)
    pal_of = np.repeat(np.repeat(attr, 16, 0), 16, 1)
    # Gegenstände im Wasser (Palette 0: Tiefblau, Hellblau, Orange) im Gegenlicht: dunkle und mittlere Töne
    # schwarz, helles Holz orange, Weiß hellblau. Wasser in Blöcken ohne Blau wird schwarz (Schatten am Kai).
    L, A, B = work[..., 0], work[..., 1], work[..., 2]
    sky_or_water = np.isin(sysfull, [0x02, 0x03, 0x11, 0x12, 0x21, 0x24, 0x37]) | \
        ((sysfull == 0x27) & (np.arange(H)[:, None] < 64))
    obj0 = (pal_of == 0) & ~sky_or_water & (np.arange(H)[:, None] >= 56)
    warm = (A > 0.02) | (B > 0.05)
    sil = np.zeros((H, W), np.uint8)                       # 0 Schwarz
    sil[warm & (L > 0.58)] = 3                             # Orange
    sil[~warm & (L > 0.85)] = 2                            # Hellblau (weiße Kajüten)
    sil[~warm & (L > 0.60) & (L <= 0.85)] = 1              # Tiefblau (Felsen, Grau)
    # Hauskante rechts (Spalten 48-55) im Schatten: flache tiefblaue Fläche, Kanten schwarz, nur wenige
    # kurze Fugen (ein regelmäßiges Fugenraster las sich als Leiter)
    edge = np.zeros((H, W), bool)
    edge[84:112, 48:56] = True
    sil[edge] = 1                                          # Schattenseite der Hauswand: Tiefblau,
    sil[84:112, 48] = 0                                    # Hauskante und Kontur schwarz
    sil[84:112, 55] = 0
    for yy, xa, xb in SHADOW_JOINTS:
        sil[yy, xa:xb] = 0
    obj0 |= edge
    ci[obj0] = sil[obj0]
    wat_other = np.isin(sysfull, [0x02, 0x11, 0x12, 0x21]) & (pal_of != 0) & (np.arange(H)[:, None] >= 64)
    ci[wat_other] = 0
    # Stein in Holzblöcken (Wand hinter Fässern und Kisten): Schatten statt Rostbraun
    grey = (np.hypot(A, B) < 0.035) & (pal_of == 3) & (np.arange(H)[:, None] >= 96)
    ci[grey] = 0
    # Kai einsetzen (Palette 2 in allen Kai-Blöcken)
    qmask = (quay >= 0) & ~keep
    ci[qmask] = quay[qmask]
    # Fässer und Kisten neu zeichnen (Hintergrund dahinter schwarz: Schatten zwischen Haus und Kai)
    ci[112:128, 32:64] = 0
    for x0, y0, rows_ in PROPS:
        for dy, r in enumerate(rows_):
            for dx, ch in enumerate(r):
                if ch != ".":
                    ci[y0 + dy, x0 + dx] = "dro".index(ch) + 1
    # Reste der alten KI-Kiste im Meerblock (Palette 0) werden Wasser
    ghost = np.zeros((H, W), bool)
    ghost[104:126, 56:72] = True
    ghost &= (pal_of == 0) & ~edge
    ci[ghost] = 1
    water |= ghost

    # Wasserphasen: Grundfarbe 1 (Tiefblau, Palette 0), Wellen 2/3; nur wo Palette 0 gilt
    pal_of = np.repeat(np.repeat(attr, 16, 0), 16, 1)
    wmask = water & (pal_of == 0)
    wmask[84:112, 48:56] = False
    phases = np.repeat(ci[None], PHASES, 0)
    rng = np.random.default_rng(1987)
    wave_rows = list(range(66, 126, 4))
    for i, y in enumerate(wave_rows):
        depth = (y - 64) / 62.0                     # 0 am Horizont, 1 vorn
        length = 2 + int(round(depth * 4))          # 2..6 px
        offs = sorted(rng.choice(16, size=1, replace=False))
        direction = 1 if i % 2 == 0 else -1
        for k in range(PHASES):
            shift = direction * 2 * k
            row = np.ones(W, np.uint8)              # Tiefblau
            for x in range(W):
                p = (x - shift - offs[0] - i * 5) % 16
                if p < length:
                    row[x] = 2
                if p == 0 and depth > 0.35 and (x // 16 + i) % 3 == 0:
                    row[x] = 3                      # Glanzlicht
            for yy in (y,):
                m = wmask[yy]
                phases[k, yy, m] = row[m]
        # Zeile darunter: kurze Nachläufer für Tiefe
    for k in range(PHASES):
        base = phases[k]
        # restliche Wasserpixel ohne Welle: Tiefblau
        rest = wmask & ~np.isin(np.arange(H)[:, None], wave_rows)
        base[rest] = 1

    out = ENTRY / "assets" / "bg_build.npz"
    np.savez_compressed(out, phases=phases, attr=attr, pals=np.array(PALS), lighthouse=lh,
                        lh_box=np.array(lh_box), win_box=np.array(win_box), lan_box=np.array(lan_box),
                        sysfull=sysfull)
    # Vorschau (Phase 0, sichtbare Zeilen 8-175)
    rgb = render(phases[0], attr)
    Image.fromarray(rgb).save(ENTRY / "assets" / "bg_preview.png")

    print(f"{out}: {PHASES} Phasen, Paletten " + " | ".join(" ".join(f"{c:02X}" for c in p) for p in PALS))


def render(ci, attr):
    pal_of = np.repeat(np.repeat(attr, 16, 0), 16, 1)
    table = np.array([[neslib.BLACK] + p for p in PALS])
    sysc = table[pal_of, ci]
    return neslib.SYSPAL[sysc].astype(np.uint8)


if __name__ == "__main__":
    main()
