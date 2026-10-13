#!/usr/bin/env python3
"""Baut alle Bilddaten der Demo aus den beiden KI-Bildern (assets/raw/bg.png, assets/raw/badger.png).

    ../../.venv/bin/python scripts/build_assets.py        (aus styles/pc98-adventure)

Ablauf:
  1. Hintergrund BOX-verkleinert auf 416x279 (Bildfenster 416x256 + Rand), 10 Zeilen oben weg.
  2. Dachs: Vorderansicht aus dem Dreiansichten-Blatt, Brustbild bis zur Taille (172x196). Für die Palette
     Alpha-gewichtet BOX-verkleinert; für das Bild materialtreu verkleinert (badger_material.py).
  3. Palette (16 Register, 12 Bit): sprites.py palette --colors 14 (Median-Cut, Schritt aus dem Auftrag) über
     Hintergrund + Figur liefert die Startwerte für 9 freie Register; ein k-means in Oklab verfeinert sie,
     während 5 Akzentfarben fest bleiben (Schwarz, Creme, Rot, Grün, Pfirsich), weil Median-Cut die kleinen
     Akzentflächen (Schal, Mütze, Horizont) verliert. Dazu 2 animierte Register (Fensterlicht, Leuchtfeuer).
     Jeder Kanal wird auf 4 Bit gerundet (0x00, 0x11 … 0xff), wie die Palettenregister der Rechner.
  4. Musterdithering (pc98lib.pattern_dither) statt sprites.py pixelize --dither bayer: pixelize addiert die
     Bayer-Schwelle auf jede Farbe und rastert damit auch flache Flächen; hier werden nur Paare benachbarter
     Palettenfarben in 5 Stufen gemischt (0, 25, 50, 75, 100 %), flache Flächen bleiben flach.
  5. Leuchtfeuer: Lampenglas + Schein + Strahl als Pixel mit Index 15; Strahl- und Scheinpixel nur dort, wo
     der Himmel schon die Aus-Farbe hat, damit das ausgeschaltete Bild exakt dem Original entspricht.
     Fenster und Laterne: Index 14.
  6. Wasser: 3 Einzelbilder; jeder helle Glanzstrich ist in einem Bild weg, in einem an seinem Platz und in
     einem um 2 px versetzt (Phase und Richtung je Strich mit festem Seed).
  7. Blinzeln und Mund: Augen- und Mundteile als kleine Einzelbilder, von Hand im Indexraster gesetzt.
Ausgabe: assets/*.png (Indexbilder: R = G = B = Index * 17, Kopie in demo/art/), demo/art/meta.json,
assets/*_preview.png und assets/palette.png (Echtfarben zur Ansicht).
"""
import json, pathlib, shutil, subprocess, sys

import numpy as np
from PIL import Image

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import badger_material  # noqa: E402
from pc98lib import (BAYER4, c12, colorize, hexc, index_png, kmeans_fixed, oklab, oklab_to_rgb,  # noqa: E402
                     pattern_dither, tohex)

SD = HERE.parent
ROOT = SD.parent.parent
ART = SD / "demo" / "art"
ASSETS = SD / "assets"
PY = str(ROOT / ".venv" / "bin" / "python")

# Bildschirmaufteilung (640x360, Ausschnitt des 640x400-Schirms): Bildfenster links oben
SCENE_X, SCENE_Y, SCENE_W, SCENE_H = 12, 12, 416, 256
BG_SCALE_H, BG_CROP_TOP = 279, 10
# Dachs-Brustbild: Ausschnitt aus der Vorderansicht (raw 1264x848) und Zielgröße
BADGER_CROP = (0, 60, 440, 560)
BADGER_W, BADGER_H = 172, 196
BADGER_POS = (200, SCENE_H - BADGER_H)        # im Bildfenster: unten bündig, rechts der Bildmitte (Wasser links frei)

FIXED = {"black": "000000", "cream": "eeddbb", "red": "993322", "green": "556633", "peach": "ee9977"}
N_FREE = 16 - len(FIXED) - 2                      # 9 Register frei für Himmel, Wasser, Stein, Holz, Fell
GLOW = ["ffeeaa", "ffdd99", "eecc88", "ffffbb"]    # Fenster/Laterne, Flackerstufen (alle 12 Bit)
LAMP_ON = "ffffcc"
LEVELS = 4                                        # Mischstufen 0, 1/4, 1/2, 3/4, 1

# Bereiche im Bildfenster (x0, y0, x1, y1), am verkleinerten Hintergrund abgelesen
WINDOW_BOX = (36, 128, 64, 186)       # Fenster des Häuschens
LANTERN_BOX = (122, 98, 140, 124)     # Laternenglas
LAMP_BOX = (366, 22, 384, 38)         # Lampenraum des Leuchtturms
LAMP_C = (374.5, 30.0)                # Mitte des Lampenglases
SEA_ROWS = (128, 200)                 # Horizont bis Kaikante
# Gegenstände im Wasser, die nicht mitwellen (Polygone im Bildfenster)
SEA_EXCLUDE = [
    [(96, 120), (110, 120), (110, 205), (96, 205)],                  # Laternenpfahl
    [(285, 128), (305, 128), (305, 145), (285, 145)],                # Felsen im Wasser
    [(306, 128), (416, 128), (416, 160), (330, 160), (306, 140)],    # Landzunge
    [(240, 150), (416, 150), (416, 205), (240, 205)],                # Steg und Boote
    [(150, 120), (162, 120), (162, 205), (150, 205)],                # Poller und Seil
]


def nearest(pal, hx):
    return int(((oklab(np.asarray(pal)) - oklab(hexc(hx)[None])) ** 2).sum(-1).argmin())


def poly_mask(h, w, poly):
    from PIL import ImageDraw
    m = Image.new("L", (w, h), 0)
    ImageDraw.Draw(m).polygon(poly, fill=255)
    return np.asarray(m) > 0


def load_bg():
    im = Image.open(SD / "assets/raw/bg.png").convert("RGB")
    s = im.resize((SCENE_W, BG_SCALE_H), Image.BOX).crop((0, BG_CROP_TOP, SCENE_W, BG_CROP_TOP + SCENE_H))
    return np.asarray(s)


def load_badger():
    im = Image.open(SD / "assets/raw/badger.png").convert("RGBA").crop(BADGER_CROP)
    a = np.asarray(im).astype(np.float32)
    al = a[..., 3:4] / 255.0
    rgb = a[..., :3]
    # Magenta-Reste vom Freistellen: Pixel mit R und B deutlich über G am Rand gelten als Hintergrund
    mag = (rgb[..., 0] > rgb[..., 1] + 60) & (rgb[..., 2] > rgb[..., 1] + 60)
    al[mag] = 0
    pm = np.dstack([rgb * al, al * 255]).astype(np.uint8)
    r = np.asarray(Image.fromarray(pm, "RGBA").resize((BADGER_W, BADGER_H), Image.BOX)).astype(np.float32)
    a2 = r[..., 3] / 255.0
    col = np.where(a2[..., None] > 0, r[..., :3] / np.maximum(a2[..., None], 1e-3), 0)
    return np.clip(col, 0, 255).astype(np.uint8), a2 >= 0.5


def build_palette(bg, brgb, bmask):
    # Schritt aus dem Auftrag: sprites.py palette (Median-Cut) über Hintergrund + Figur (Figur auf Schwarz)
    comp = np.zeros((SCENE_H, SCENE_W + BADGER_W, 3), np.uint8)
    comp[:, :SCENE_W] = bg
    comp[SCENE_H - BADGER_H:, SCENE_W:] = np.where(bmask[..., None], brgb, 0)
    tmp = SD / "assets" / "_palette_src.png"
    Image.fromarray(comp).save(tmp)
    out = subprocess.run([PY, str(ROOT / "tools/sprites.py"), "palette", str(tmp),
                          str(ASSETS / "palette_mediancut.png"), "--colors", "14"],
                         capture_output=True, text=True, check=True).stdout.split()
    tmp.unlink()
    mediancut = out[:14]
    fixed_hex = list(FIXED.values())
    px = np.vstack([bg.reshape(-1, 3), brgb[bmask]])
    lab = oklab(px)
    rng = np.random.default_rng(1)
    sel = rng.choice(len(lab), 30000, replace=False)
    # Median-Cut verliert die kleinen Akzentflächen (Schal, Mütze, Horizont, Fenster): diese bleiben im
    # k-means fest, die übrigen 9 Register starten bei den ersten 9 Median-Cut-Farben.
    init = oklab(np.array([hexc(h) for h in mediancut[:N_FREE]]))
    fixed = oklab(np.array([hexc(h) for h in fixed_hex + [GLOW[0], LAMP_ON]]))
    free = kmeans_fixed(lab[sel], fixed, init)
    free_rgb = c12(oklab_to_rgb(free))
    pal = np.vstack([np.array([hexc(h) for h in fixed_hex]), free_rgb,
                     np.array([hexc(GLOW[0]), hexc(LAMP_ON)])])
    assert len(pal) == 16 and len({tohex(c) for c in pal}) == 16, [tohex(c) for c in pal]
    return pal, mediancut


def ring_dither(h, w, cx, cy, radii_levels, ox, oy):
    """Bayer-Raster in Ringen um (cx, cy): [(Radius, Deckung 0..1), ...] von innen nach außen."""
    yy, xx = np.mgrid[0:h, 0:w]
    d = np.hypot(xx + 0.5 - cx, (yy + 0.5 - cy))
    th = (BAYER4[(yy + oy) % 4, (xx + ox) % 4] + 0.5) / 16.0
    cov = np.zeros((h, w), np.float32)
    prev = 0.0
    for r, c in radii_levels:
        cov[(d >= prev) & (d < r)] = c
        prev = r
    return th < cov


# Gesichtsteile im Brustbild (Koordinaten im 172x196-Bild, am Indexbild abgelesen)
EYES = [(67, 46, 78, 57), (100, 47, 111, 57)]      # Kästen um die beiden Augen (x0, y0, x1, y1)
EYES_BOX = (64, 44, 114, 58)                        # gemeinsamer Ausschnitt für das Augen-Teilbild
MOUTH_BOX = (82, 72, 96, 80)
MOUTH_OPEN = [  # Zeilen ab y = 74, Spalten ab x = 84; '.' = unverändert, sonst Name des Registers
    ["black", "black", "black", "black", "black", "black", "black", "black", "black", "black"],
    [".", "black", "dark", "red", "red", "red", "red", "dark", "black", "."],
    [".", ".", "black", "red", "peach", "peach", "red", "black", ".", "."],
    [".", ".", ".", "black", "black", "black", "black", ".", ".", "."],
]
DARK = "221122"                                     # Mundinneres: dunkelstes Violett der Palette
MOUTH_HALF = [
    [".", "black", "black", "black", "black", "black", "black", "black", "black", "."],
    [".", ".", "black", "red", "red", "red", "red", "black", ".", "."],
    [".", ".", ".", "black", "black", "black", "black", ".", ".", "."],
]


def face_parts(bidx, bmask, I, pal):
    """Blinzeln und Mund wie bei klassischen Adventures aus Teilen: kleine Überlagerungen auf dem festen
    Körper. Augen: halb geschlossen, geschlossen. Mund: halb offen, offen. Von Hand im Indexraster gesetzt."""
    black = I["black"]
    out = {}
    # Fellfarbe um die Augen = häufigster Index im Augenkasten außerhalb des Augapfels
    frames = []
    for state in ("half", "closed"):
        f = bidx.copy()
        for (x0, y0, x1, y1) in EYES:
            box = f[y0:y1, x0:x1]
            ring = np.concatenate([box[0], box[-1], box[:, 0], box[:, -1]])
            fur_i = int(np.bincount(ring, minlength=16).argmax())
            ys, xs = np.nonzero(box == black)             # Augapfel = Bereich der schwarzen Pixel
            ey0, ey1, ex0, ex1 = ys.min(), ys.max(), xs.min(), xs.max()
            eye = np.zeros(box.shape, bool)
            eye[ey0:ey1 + 1, ex0:ex1 + 1] = box[ey0:ey1 + 1, ex0:ex1 + 1] != fur_i   # samt Glanzlicht
            mid = (ey0 + ey1) // 2
            if state == "closed":
                box[eye] = fur_i
                lid = mid + 1
                box[lid, ex0 + 1:ex1] = black            # Lidlinie
                box[lid + 1, ex0] = black                # Enden leicht nach unten
                box[lid + 1, ex1] = black
            else:
                upper = eye.copy()
                upper[mid:] = False
                box[upper] = fur_i
                box[mid, ex0:ex1 + 1] = black            # Lidkante quer durch das Auge
                lower = eye.copy()
                lower[:mid + 1] = False
                box[lower] = black                       # Glanzlicht verschwindet
            f[y0:y1, x0:x1] = box
        frames.append(f)
    x0, y0, x1, y1 = EYES_BOX
    eyes = [fr[y0:y1, x0:x1] for fr in frames]
    eyes_alpha = np.zeros((y1 - y0, x1 - x0), bool)
    for e in eyes:
        eyes_alpha |= e != bidx[y0:y1, x0:x1]
    out["eyes"] = (eyes, eyes_alpha, (x0, y0))
    mframes = []
    for pat in (MOUTH_HALF, MOUTH_OPEN):
        f = bidx.copy()
        for r, row in enumerate(pat):
            for c, name in enumerate(row):
                if name != ".":
                    f[74 + r, 84 + c] = I[name] if name in I else nearest(pal, DARK)
        mframes.append(f)
    x0, y0, x1, y1 = MOUTH_BOX
    mouth = [fr[y0:y1, x0:x1] for fr in mframes]
    m_alpha = np.zeros((y1 - y0, x1 - x0), bool)
    for mm in mouth:
        m_alpha |= mm != bidx[y0:y1, x0:x1]
    out["mouth"] = (mouth, m_alpha, (x0, y0))
    return out, frames, mframes


def main():
    ART.mkdir(parents=True, exist_ok=True)
    bg = load_bg()
    brgb, bmask = load_badger()
    pal, mediancut = build_palette(bg, brgb, bmask)
    names = list(FIXED) + [f"k{i}" for i in range(N_FREE)] + ["glow", "lamp"]
    I = {n: i for i, n in enumerate(names)}
    lum = oklab(pal)[:, 0]
    static = list(range(14))                      # 14 und 15 nur über Masken (Fensterlicht, Leuchtfeuer)

    # --- Hintergrund ------------------------------------------------------------------------------------
    H, W = SCENE_H, SCENE_W
    idx = pattern_dither(bg, pal, allowed=static, levels=LEVELS, ox=SCENE_X, oy=SCENE_Y)
    # Fenster und Laterne: in ihren Rahmen gezielt mit Glühfarbe neu rastern
    for box in (WINDOW_BOX, LANTERN_BOX):
        x0, y0, x1, y1 = box
        sub = pattern_dither(bg[y0:y1, x0:x1], pal, allowed=static + [I["glow"]], levels=LEVELS,
                             ox=SCENE_X + x0, oy=SCENE_Y + y0)
        idx[y0:y1, x0:x1] = sub
    glow_px = int((idx == I["glow"]).sum())
    # Leuchtfeuer: helle Pixel im Lampenraum -> Index lamp; Schein und Strahl nur auf Himmelspixeln in der
    # Aus-Farbe des Registers, damit ausgeschaltet nichts vom Original abweicht.
    x0, y0, x1, y1 = LAMP_BOX
    lb = bg[y0:y1, x0:x1].astype(int)
    bright = (lb.sum(-1) > 480) & (lb[..., 0] > lb[..., 2] + 20)
    idx[y0:y1, x0:x1][bright] = I["lamp"]
    halo = ring_dither(H, W, LAMP_C[0], LAMP_C[1], [(5, 0.0), (9, 0.25), (13, 0.125)], SCENE_X, SCENE_Y)
    yy, xx = np.mgrid[0:H, 0:W]
    # Strahl nach links, spitz an der Lampe ansetzend: 50 %, dann 25 %, dann 12,5 % Raster
    dx = LAMP_C[0] - (xx + 0.5)
    dy = (yy + 0.5) - LAMP_C[1]
    in_beam = (dx > 6) & (dx < 135) & (np.abs(dy) < 0.8 + dx * 0.03)
    th = (BAYER4[(yy + SCENE_Y) % 4, (xx + SCENE_X) % 4] + 0.5) / 16.0
    beam_cov = np.where(dx < 35, 0.5, np.where(dx < 85, 0.25, 0.125))
    beam = in_beam & (th < beam_cov)
    # Aus-Farbe des Leuchtfeuers = häufigster Himmelsindex im Bereich von Schein und Strahl
    zone = (halo | in_beam) & ~poly_mask(H, W, [(x0, y0), (x1, y0), (x1, y1), (x0, y1)])
    off_idx = int(np.bincount(idx[zone], minlength=16).argmax())
    lamp_extra = (halo | beam) & (idx == off_idx)
    idx[lamp_extra] = I["lamp"]

    # --- Wasser: 3 Einzelbilder --------------------------------------------------------------------------
    r0, r1 = SEA_ROWS
    sea = np.zeros((H, W), bool)
    sea[r0:r1] = True
    blue = (bg[..., 2].astype(int) > bg[..., 0] + 15)
    sea &= blue
    sea[:, :84] = False
    for poly in SEA_EXCLUDE:
        sea &= ~poly_mask(H, W, poly)
    # Glanzpixel: deutlich heller als der Wassergrund
    light = sea & (lum[idx] > 0.55)
    # Grund unter den Glanzstrichen: Wasserfarbe 4 oder 8 Zeilen darüber/darunter (gleiche Rasterphase)
    fill = idx.copy()
    for y, x in zip(*np.nonzero(light)):
        for dy_ in (4, -4, 8, -8):
            yy2 = y + dy_
            if 0 <= yy2 < H and sea[yy2, x] and not light[yy2, x]:
                fill[y, x] = idx[yy2, x]
                break
    # Glanzstriche = waagrechte Läufe heller Pixel je Zeile. Jeder Strich bekommt eine Phase (fester Seed):
    # in den 3 Bildern ist er einmal unsichtbar, einmal an seinem Platz und einmal um 2 px versetzt.
    rng = np.random.default_rng(5)
    dashes = []
    for y in range(H):
        xs_ = np.flatnonzero(light[y])
        if xs_.size == 0:
            continue
        start = prev = xs_[0]
        for x in list(xs_[1:]) + [None]:
            if x is None or x != prev + 1:
                dashes.append((y, start, prev + 1, int(rng.integers(3)), int(rng.choice([-1, 1]))))
                if x is None:
                    break
                start = x
            prev = x
    base = np.where(light, fill, idx)
    frames = []
    for k in range(3):
        f = base.copy()
        for y, xa, xb, ph, d in dashes:
            state = (ph + k) % 3
            if state == 0:
                continue
            off = 0 if state == 1 else 2 * d
            for x in range(xa, xb):
                nx = x + off
                if 0 <= nx < W and sea[y, nx]:
                    f[y, nx] = idx[y, x]
        frames.append(f)
    water_mask = sea | light
    changed = np.zeros((H, W), bool)
    for f in frames:
        changed |= f != frames[0]
    idx_base = frames[0]

    # --- Dachs -------------------------------------------------------------------------------------------
    bidx, bmask, bmat, mat_names = badger_material.build(
        SD / "assets/raw/badger.png", BADGER_CROP, (BADGER_W, BADGER_H), pal,
        (SCENE_X + BADGER_POS[0], SCENE_Y + BADGER_POS[1]), levels=LEVELS)
    # Kontur: Kante der Figur schwarz, wo sie nicht schon dunkel ist (klare Anime-Kontur gegen den Himmel)
    m = bmask
    edge = m & ~(np.roll(m, 1, 0) & np.roll(m, -1, 0) & np.roll(m, 1, 1) & np.roll(m, -1, 1))
    edge[-1, :] = False                       # unten schneidet der Bildrand
    bidx[edge & (lum[bidx] > 0.30)] = I["black"]

    parts, eye_frames, mouth_frames = face_parts(bidx, bmask, I, pal)
    meta = {
        "palette": [tohex(c) for c in pal],
        "names": names,
        "index": I,
        "glow_steps": GLOW,
        "lamp_on": LAMP_ON,
        "lamp_off": tohex(pal[off_idx]),
        "lamp_off_index": off_idx,
        "mediancut_14": mediancut,
        "scene": [SCENE_X, SCENE_Y, SCENE_W, SCENE_H],
        "badger_pos": [SCENE_X + BADGER_POS[0], SCENE_Y + BADGER_POS[1]],
        "badger_size": [BADGER_W, BADGER_H],
        "water_frames": len(frames),
        "water_dashes": len(dashes),
        "stats": {"glow_px": glow_px, "lamp_px": int((idx_base == I["lamp"]).sum()),
                  "water_px": int(water_mask.sum()), "water_changed_px": int(changed.sum())},
    }
    # Dateien
    Image.fromarray(index_png(idx_base)).save(ASSETS / "bg.png")
    strip = np.zeros((H, W * len(frames)), np.int32)
    salpha = np.zeros((H, W * len(frames)), bool)
    for k, f in enumerate(frames):
        strip[:, k * W:(k + 1) * W] = f
        salpha[:, k * W:(k + 1) * W] = changed
    Image.fromarray(index_png(strip, salpha)).save(ASSETS / "water.png")
    Image.fromarray(index_png(bidx, bmask)).save(ASSETS / "badger_body.png")
    for name, (frs, alpha, pos) in parts.items():
        h_, w_ = alpha.shape
        st = np.zeros((h_, w_ * len(frs)), np.int32)
        sa = np.zeros((h_, w_ * len(frs)), bool)
        for k, fr in enumerate(frs):
            st[:, k * w_:(k + 1) * w_] = fr
            sa[:, k * w_:(k + 1) * w_] = alpha
        Image.fromarray(index_png(st, sa)).save(ASSETS / f"badger_{name}.png")
        meta[f"{name}_pos"] = [int(pos[0]), int(pos[1])]
        meta[f"{name}_frames"] = len(frs)
    (ART / "meta.json").write_text(json.dumps(meta, indent=1))
    for n in ("bg", "water", "badger_body", "badger_eyes", "badger_mouth"):   # Kopie für die Demo
        shutil.copyfile(ASSETS / f"{n}.png", ART / f"{n}.png")
    sheet = [bidx] + eye_frames + mouth_frames
    prev = np.zeros((BADGER_H, BADGER_W * len(sheet), 4), np.uint8)
    for k, fr in enumerate(sheet):
        prev[:, k * BADGER_W:(k + 1) * BADGER_W] = colorize(fr, pal, bmask)
    Image.fromarray(prev, "RGBA").save(ASSETS / "badger_faces_preview.png")
    (ART / "meta.json").write_text(json.dumps(meta, indent=1))
    # Vorschauen in Echtfarben
    Image.fromarray(colorize(idx_base, pal)).save(ASSETS / "bg_preview.png")
    Image.fromarray(colorize(bidx, pal, bmask), "RGBA").save(ASSETS / "badger_preview.png")
    Image.fromarray(np.repeat(np.repeat(pal[None], 32, 0), 32, 1)).save(ASSETS / "palette.png")
    print(json.dumps({k: meta[k] for k in ("palette", "lamp_off", "stats")}, indent=1))


if __name__ == "__main__":
    main()
