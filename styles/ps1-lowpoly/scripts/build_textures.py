#!/usr/bin/env python3
"""PS1-Texturen aus dem KI-Texturblatt und dem KI-Himmel bauen.

    .venv/bin/python styles/ps1-lowpoly/scripts/build_textures.py

Eingaben (assets/raw/):
  textures.png  4×4-Blatt mit schwarzen Fugen (genimg, agy)

Ausgaben (assets/textures/ und Kopie in demo/textures/):
  <name>.png    64×64, nahtlos kachelbar, Mittelwert auf die glTF-Materialfarbe abgeglichen,
                16 Farben (4-Bit-CLUT wie auf der Konsole), 15-Bit-Farbwerte (5 Bit je Kanal)
  flagstone.png 64×64 Kaipflaster (Granit + Plattenmuster aus Code) für den großen Boden aus wenigen Polygonen
  sky.png       352×160 Hintergrund aus Code (Horizont in Zeile 143, 16 px Rand je Seite), 15 Bit
  smoke.png, glow.png, shadow.png   kleine Effekt-Texturen aus Code
  barrel.png, railing.png, crate.png  Fass (Dauben, Reifen), Galeriegeländer (Ausschnitt) und Kiste
                (Bretter, Rahmen) für harbor_ps1.glb, aus wood/wooddark/iron.png und Code
  textures_sheet.png   Übersicht (8-fach vergrößert) zum Ansehen
"""
import json, pathlib

import numpy as np
from PIL import Image

HERE = pathlib.Path(__file__).resolve().parent.parent
RAW = HERE / "assets" / "raw"
OUT = HERE / "assets" / "textures"
DEMO = HERE / "demo" / "textures"
TILE = 64
OVERLAP = 12          # Pixel (bei 64er Kachel), die über den Rand hinweg überblendet werden

# Zelle im Blatt (Zeile, Spalte) -> Name, Zielfarbe (glTF-Material, sRGB) oder None (Farbe behalten)
CELLS = {
    (0, 0): ("granite", "8C877D"),       # Stone am Kai (Pflaster, Kantensteine)
    (0, 1): ("fieldstone", "8C877D"),    # Stone am Häuschen
    (0, 2): ("darkstone", "5A5650"),     # StoneDark
    (0, 3): ("wood", "8E6440"),          # Wood
    (1, 0): ("wooddark", "4E3726"),      # WoodDark
    (1, 1): ("plaster", "E8E4DA"),       # WhitePaint an Häuschen/Leuchtturm
    (1, 2): ("redplaster", "B02A22"),    # RedPaint an Häuschen/Leuchtturm
    (1, 3): ("slate", "4A5361"),         # Roof
    (2, 0): ("rope", "BFA77A"),          # Rope
    (2, 1): ("iron", "3C3D40"),          # Metal
    (2, 2): ("rock", "6E6A64"),          # Rock
    (2, 3): ("sand", "C9B48A"),          # Sand
    (3, 0): ("grass", "6E8048"),         # Grass
    (3, 1): ("water", "2B5A6B"),         # Water
    (3, 2): ("boatwhite", "E8E4DA"),     # WhitePaint an Booten
    (3, 3): ("boatred", "B02A22"),       # RedPaint an Booten
}


def srgb_to_lin(c):
    c = np.asarray(c, dtype=np.float64)
    return np.where(c <= 0.04045, c / 12.92, ((c + 0.055) / 1.055) ** 2.4)


def lin_to_srgb(c):
    c = np.clip(c, 0, 1)
    return np.where(c <= 0.0031308, c * 12.92, 1.055 * c ** (1 / 2.4) - 0.055)


def runs(mask):
    """Zusammenhängende True-Bereiche als (start, end)."""
    out, start = [], None
    for i, v in enumerate(mask):
        if v and start is None:
            start = i
        elif not v and start is not None:
            out.append((start, i))
            start = None
    if start is not None:
        out.append((start, len(mask)))
    return out


def cells(sheet):
    """Zellgrenzen aus den schwarzen Fugen messen (nicht annehmen)."""
    g = np.asarray(sheet.convert("L"), dtype=np.float64)
    xs = [r for r in runs(g.mean(0) > 24) if r[1] - r[0] > 100]
    ys = [r for r in runs(g.mean(1) > 24) if r[1] - r[0] > 100]
    assert len(xs) == 4 and len(ys) == 4, (xs, ys)
    return xs, ys


def seamless(img):
    """img: (T+O)×(T+O)×3 float. Den Überstand rechts/unten in den linken/oberen Rand überblenden."""
    t, o = TILE, OVERLAP
    a = img.copy()
    w = (np.arange(o) + 0.5) / o                       # 0 -> 1 über die Überblendzone
    a[:, :o] = a[:, t:t + o] * (1 - w)[None, :, None] + a[:, :o] * w[None, :, None]
    a = a[:, :t]
    a[:o, :] = a[t:t + o, :] * (1 - w)[:, None, None] + a[:o, :] * w[:, None, None]
    return a[:t]


def quantize(rgb, colors):
    """rgb uint8 -> auf 5 Bit je Kanal gerundet und auf `colors` Farben reduziert (Median Cut, ohne Dithering)."""
    im = Image.fromarray(rgb).quantize(colors=colors, method=Image.Quantize.MEDIANCUT, dither=Image.Dither.NONE)
    q = np.asarray(im.convert("RGB")).astype(np.int32)
    q = (np.round(q / 255 * 31) * 255 / 31).round().astype(np.uint8)   # 15-Bit-Farbwerte
    return q


def build_tiles():
    sheet = Image.open(RAW / "textures.png").convert("RGB")
    xs, ys = cells(sheet)
    info = {}
    previews = []
    for (r, c), (name, target) in CELLS.items():
        x0, x1 = xs[c]
        y0, y1 = ys[r]
        inset = 6
        crop = sheet.crop((x0 + inset, y0 + inset, x1 - inset, y1 - inset))
        big = np.asarray(crop.resize((TILE + OVERLAP, TILE + OVERLAP), Image.LANCZOS), dtype=np.float64) / 255
        tile = seamless(big)
        lin = srgb_to_lin(tile)
        mean = lin.reshape(-1, 3).mean(0)
        tgt = srgb_to_lin(np.array([int(target[i:i + 2], 16) for i in (0, 2, 4)]) / 255)
        gain = tgt / np.maximum(mean, 1e-4)
        lin = lin * gain[None, None, :]
        rgb = (lin_to_srgb(lin) * 255).round().astype(np.uint8)
        q = quantize(rgb, 16)
        Image.fromarray(q).save(OUT / f"{name}.png")
        Image.fromarray(q).save(DEMO / f"{name}.png")
        info[name] = {"cell": [r, c], "src_box": [x0 + inset, y0 + inset, x1 - inset, y1 - inset],
                      "target": "#" + target, "gain": [round(float(v), 3) for v in gain],
                      "colors": int(len(np.unique(q.reshape(-1, 3), axis=0)))}
        # Vorschau: 2×2 gekachelt, damit Nähte auffallen
        previews.append((name, np.tile(q, (2, 2, 1))))
    # Übersicht
    cols = 4
    pw = TILE * 2
    sheet_out = Image.new("RGB", (cols * (pw + 4), ((len(previews) + cols - 1) // cols) * (pw + 4)), "black")
    for i, (name, arr) in enumerate(previews):
        sheet_out.paste(Image.fromarray(arr), ((i % cols) * (pw + 4), (i // cols) * (pw + 4)))
    sheet_out = sheet_out.resize((sheet_out.width * 4, sheet_out.height * 4), Image.NEAREST)
    sheet_out.save(OUT / "textures_sheet.png")
    return info


def build_flagstone(info):
    """Kaipflaster als Kacheltextur für den großen Boden aus wenigen Polygonen (wie auf der Konsole).

    Grundlage ist die Granit-Zelle des KI-Blatts (vor dem Quantisieren), darüber per Code ein Plattenmuster:
    8 Reihen zu 8 Texeln, Plattenbreiten 8/12/16/20 Texel im Läuferverband (fester Seed), 1 Texel dunkle Fuge
    unten/rechts, 1 Texel helle Kante oben/links, jede Platte leicht anders getönt. Gerade Fugen machen das
    affine Verziehen auf großen Polygonen sichtbar. Bei 6 m je Kachel ist eine Reihe 0,75 m tief.
    """
    sheet = Image.open(RAW / "textures.png").convert("RGB")
    xs, ys = cells(sheet)
    x0, x1 = xs[0]
    y0, y1 = ys[0]
    crop = sheet.crop((x0 + 6, y0 + 6, x1 - 6, y1 - 6))
    big = np.asarray(crop.resize((TILE + OVERLAP, TILE + OVERLAP), Image.LANCZOS), dtype=np.float64) / 255
    lin = srgb_to_lin(seamless(big))
    tgt = srgb_to_lin(np.array([0x8C, 0x87, 0x7D]) / 255)
    lin = lin * (tgt / lin.reshape(-1, 3).mean(0))[None, None, :]
    # Körnung abschwächen (Granit ist sonst bei 15 Bit + Dithering nur Rauschen), Platten bleiben gesprenkelt
    mean = lin.reshape(-1, 3).mean(0)
    lin = mean + (lin - mean) * 0.55
    rng = np.random.default_rng(20261011)
    out = lin.copy()
    row_h = 8
    for r in range(TILE // row_h):
        # Plattenbreiten, die zusammen 64 ergeben; Versatz je Reihe (Läuferverband, nahtlos über den Rand)
        widths = []
        while sum(widths) < TILE:
            widths.append(int(rng.choice([8, 12, 16, 16, 20])))
        widths[-1] -= sum(widths) - TILE
        if widths[-1] < 6:
            widths[-2] += widths.pop()
        off = int(rng.integers(0, TILE))
        x = off
        for w in widths:
            tone = rng.uniform(0.86, 1.12) * np.array([1.0, rng.uniform(0.98, 1.02), rng.uniform(0.96, 1.04)])
            cols = [(x + i) % TILE for i in range(w)]
            ys_ = slice(r * row_h, (r + 1) * row_h)
            out[ys_, cols] = lin[ys_, cols] * tone
            # Kanten: oben/links hell, unten/rechts Fuge
            out[r * row_h, cols] *= 1.22
            out[ys_, cols[0]] *= 1.12
            out[(r + 1) * row_h - 1, cols] = lin[(r + 1) * row_h - 1, cols] * 0.32
            out[ys_, cols[-1]] = lin[ys_, cols[-1]] * 0.38
            x += w
    rgb = (lin_to_srgb(out) * 255).round().astype(np.uint8)
    q = quantize(rgb, 16)
    Image.fromarray(q).save(OUT / "flagstone.png")
    Image.fromarray(q).save(DEMO / "flagstone.png")
    Image.fromarray(np.tile(q, (2, 2, 1))).resize((TILE * 8, TILE * 8), Image.NEAREST).save(OUT / "flagstone_preview.png")
    info["flagstone"] = {"cell": [0, 0], "derived_from": "granite + Plattenmuster (Code)", "target": "#8C877D",
                         "colors": int(len(np.unique(q.reshape(-1, 3), axis=0)))}


# Himmel: 352 breit (16 px Rand je Seite für den Kameraschwenk), 160 hoch, Horizont in Zeile 143.
SKY_W, SKY_H, HORIZON_ROW = 352, 160, 143
# Höhe über dem Horizont (Zeilen) -> Farbe (sRGB): Orange am Horizont, Rosa, staubiges Violett, Nachtblau oben.
# Die untersten Zeilen (#ef9452) geben die Nebelfarbe (Meer und ferne Inseln laufen darin aus).
SKY_STOPS = [(0, "ef9452"), (5, "e88c52"), (9, "d88454"), (13, "c87c5a"), (18, "b07468"), (24, "9c6c72"),
             (32, "946b74"), (40, "86647a"), (47, "6a5c7e"), (54, "4e5484"), (62, "3c4b7c"), (72, "2c3c6c"),
             (84, "233263"), (100, "1e2b5b"), (120, "1a2552"), (143, "151e48")]
# Wolkenstreifen: Mittelzeile (Höhe über dem Horizont), Start x, Länge, Dicke (Zeilen)
SKY_CLOUDS = [(51, -10, 165, 4.0), (47, 228, 170, 3.5), (38, 140, 150, 3.0), (61, 92, 110, 2.2),
              (28, -30, 150, 3.0), (26, 270, 140, 3.0), (19, 70, 115, 2.2), (32, 205, 70, 2.0)]


def build_sky():
    """Himmel als 2D-Hintergrund (wie bei vielen Spielen der Zeit), 352×160, Horizont in Zeile 143, aus Code.

    main.gd setzt das Bild je Kamera: Horizontzeile = 120 + f·tan(Neigung), seitlicher Versatz = f·tan(Gieren)
    mit f = 160 / tan(horizontaler Bildwinkel / 2). Totale (6° nach unten, f = 234,5): Horizont in Zeile 95,4,
    das Bild beginnt bei y = −48. Nahaufnahme (0,19° nach unten, f = 190,7): Horizont in Zeile 119,4, das Bild
    beginnt bei y = −24. Die erste Fassung (KI-Bild, 128 hoch, Horizont 111) begann dort erst bei y = 8, und
    die obersten 8 Zeilen blieben schwarz.

    In der ersten Fassung (10.10.2026) kam der Himmel aus einem agy-Bild; agy hatte den Prompt umformuliert und
    Konsolennamen eingefügt. Deshalb jetzt ganz aus Code (fester Seed): Verlauf über SKY_STOPS, auf 15 Bit gerundet (die
    Stufen ergeben das Banding gemalter Hintergründe), Bandgrenzen leicht wellig, Nachglühen links der Mitte,
    acht flache Wolkenstreifen mit angeleuchteter Unterkante, 46 Sterne im oberen Teil. Darunter 17 Zeilen
    Horizontfarbe (vom Meer verdeckt).
    """
    rng = np.random.default_rng(20261014)
    x = np.arange(SKY_W)
    hs = np.array([s[0] for s in SKY_STOPS], float)
    cs = np.array([[int(s[1][i:i + 2], 16) for i in (0, 2, 4)] for s in SKY_STOPS], float)

    def grad(h):
        h = np.clip(np.asarray(h, float), 0, hs[-1])
        return np.stack([np.interp(h, hs, cs[:, k]) for k in range(3)], -1)

    def q5(c):
        return (np.round(np.clip(c, 0, 255) / 255 * 31) * 255 / 31).round()

    # periodisches Wertrauschen (nahtlos über die Breite): Bandgrenzen wellig wie mit breitem Pinsel
    cells = 11
    v = rng.uniform(-1, 1, cells)
    xs = x / SKY_W * cells
    i0 = np.floor(xs).astype(int) % cells
    f = xs - np.floor(xs)
    f = f * f * (3 - 2 * f)
    wob = 1.3 * (v[i0] * (1 - f) + v[(i0 + 1) % cells] * f)
    sun = 7.0 * np.exp(-((x - 150) / 75.0) ** 2)            # Nachglühen hebt das Orange links der Mitte an
    yy = np.arange(SKY_H)[:, None]
    h0 = (HORIZON_ROW - yy).astype(float)
    lift = sun[None, :] * np.clip(h0 / 10.0, 0, 1) * np.clip((70.0 - h0) / 40.0, 0, 1)
    h = np.where(h0 <= 3, h0, h0 - lift + wob[None, :])     # unterste Zeilen glatt (Nebelfarbe)
    img = q5(grad(h))

    # Wolken: spitz auslaufend, oben dunkel blaugrau, unten wärmer, Unterkante orange/rosa angeleuchtet
    for hc, x0, length, th in SKY_CLOUDS:
        ph = rng.uniform(0, 6.283, 3)
        dark = grad(hc + 14.0) * np.array([0.80, 0.82, 0.92]) + np.array([6, 8, 16])
        warm = grad(hc + 2.0) * np.array([0.92, 0.84, 0.88])
        lit = grad(max(hc - 20.0, 0.0)) * np.array([1.06, 0.96, 0.92])
        for xi in range(length):
            prof = np.sin(np.pi * (xi + 0.5) / length) ** 0.8
            t_top = th * prof * (0.75 + 0.25 * np.sin(xi * 0.09 + ph[0]) + 0.12 * np.sin(xi * 0.23 + ph[1]))
            t_bot = 0.45 * th * prof * (0.8 + 0.2 * np.sin(xi * 0.13 + ph[2]))
            if t_top < 0.5:
                continue
            xx = (x0 + xi) % SKY_W
            top = int(round(HORIZON_ROW - hc - t_top))
            bot = int(round(HORIZON_ROW - hc + t_bot))
            n = max(bot - top, 1)
            for k, yv in enumerate(range(top, bot + 1)):
                img[yv, xx] = q5(dark * (1 - k / n) + warm * (k / n))
            if prof > 0.35:
                a = min(1.0, prof + 0.2)
                img[bot + 1, xx] = q5(lit * a + img[bot + 1, xx] * (1 - a))

    # Sterne: einzelne Punkte in den obersten 62 Zeilen, drei Helligkeiten (meist schwach)
    star_cols = np.array([[0x4a, 0x5a, 0x8c], [0x7b, 0x8c, 0xbd], [0xc6, 0xd0, 0xf0]], float)
    for _ in range(46):
        sx, sy = rng.integers(0, SKY_W), rng.integers(0, 62)
        img[sy, sx] = q5(star_cols[rng.choice([0, 0, 0, 1, 1, 2])])

    q = img.astype(np.uint8)
    Image.fromarray(q).save(OUT / "sky.png")
    Image.fromarray(q).save(DEMO / "sky.png")
    # Nebelfarbe = Horizontfarbe des fertigen Himmels (Mittel der Zeilen direkt über dem Horizont)
    fog = q[HORIZON_ROW - 4:HORIZON_ROW].reshape(-1, 3).mean(0)
    return {"size": [SKY_W, SKY_H], "horizon_row": HORIZON_ROW,
            "fog_color": "#" + "".join(f"{int(round(v)):02x}" for v in fog),
            "colors": int(len(np.unique(q.reshape(-1, 3), axis=0)))}


def build_fx():
    """Kleine Effekt-Texturen aus Code (1-Bit-Alpha bzw. wenige Stufen)."""
    # Rauchwölkchen 16×16: Kreis mit drei Grautönen (oben links hell, Mitte, unten rechts dunkel),
    # auf 5 Bit gerundet, harte Alphakante (1 Bit)
    s = 16
    yy, xx = np.mgrid[0:s, 0:s] + 0.5
    d = np.hypot(xx - s / 2, yy - s / 2) / (s / 2)
    rng = np.random.default_rng(20261010)
    bump = d + rng.uniform(-0.12, 0.12, d.shape)
    a = (bump < 0.95).astype(np.uint8) * 255
    k = ((xx - s / 2) * 0.8 + (yy - s / 2)) / s + rng.uniform(-0.06, 0.06, d.shape)   # Licht von oben links
    tones = np.array([235, 196, 150])                                                # hell, mittel, dunkel
    g = tones[np.digitize(k, [-0.12, 0.22])]
    g = (np.round(g / 255 * 31) * 255 / 31).round().astype(np.uint8)
    b = (np.round(np.clip(g * 1.04, 0, 255) / 255 * 31) * 255 / 31).round().astype(np.uint8)
    smoke = np.dstack([g, g, b, a])
    Image.fromarray(smoke, "RGBA").save(DEMO / "smoke.png")
    Image.fromarray(smoke, "RGBA").save(OUT / "smoke.png")

    # Lichthof 32×32 für Laterne und Leuchtfeuer: Stufen statt Verlauf (additiv)
    s = 32
    yy, xx = np.mgrid[0:s, 0:s] + 0.5
    d = np.hypot(xx - s / 2, yy - s / 2) / (s / 2)
    core = np.clip(1 - d, 0, 1) ** 1.6
    star = np.clip(1 - np.minimum(np.abs(xx - s / 2), np.abs(yy - s / 2)) / 1.2, 0, 1) * np.clip(1 - d, 0, 1) ** 0.8
    v = np.clip(core + 0.6 * star, 0, 1)
    v = np.floor(v * 6) / 6                                            # 6 Helligkeitsstufen
    g = (v * 255).astype(np.uint8)
    glow = np.dstack([g, g, g, np.full_like(g, 255)])
    Image.fromarray(glow, "RGBA").save(DEMO / "glow.png")
    Image.fromarray(glow, "RGBA").save(OUT / "glow.png")

    # Rundschatten 16×16 (1-Bit), wird halbtransparent gezeichnet
    s = 16
    yy, xx = np.mgrid[0:s, 0:s] + 0.5
    d = np.hypot(xx - s / 2, (yy - s / 2)) / (s / 2)
    a = (d < 0.92).astype(np.uint8) * 255
    sh = np.dstack([np.zeros_like(a), np.zeros_like(a), np.zeros_like(a), a])
    Image.fromarray(sh, "RGBA").save(DEMO / "shadow.png")
    Image.fromarray(sh, "RGBA").save(OUT / "shadow.png")


def build_barrel():
    """Fass-Textur 64×64 für harbor_ps1.glb (Material BarrelSide, UV einmal herum, oben = Fassdeckel):
    8 Dauben zu 8 Texeln (= 8 Seiten des Fasses), Maserung senkrecht (Holz-Kachel gedreht), je Daube eigener
    Ton, 1 Texel dunkle Fuge; vier Eisenreifen (Farbe aus iron.png) mit heller Oberkante und Schatten darunter.
    Reifen in den Zeilen der Knicke des Drehkörpers (z = 0,2 und 0,7 m) und an den Rändern."""
    wood = np.asarray(Image.open(OUT / "wood.png").convert("RGB"), dtype=np.float64) / 255
    iron = np.asarray(Image.open(OUT / "iron.png").convert("RGB"), dtype=np.float64) / 255
    lin = srgb_to_lin(np.transpose(wood, (1, 0, 2)))
    iron_lin = srgb_to_lin(iron)
    rng = np.random.default_rng(20261012)
    out = lin.copy()
    for k in range(8):
        cols = slice(k * 8, k * 8 + 8)
        out[:, cols] *= rng.uniform(0.84, 1.12)
        out[:, k * 8] *= 0.42                     # Fuge
        out[:, k * 8 + 1] *= 1.12                 # Kante
    for r0, r1 in ((1, 4), (9, 13), (51, 55), (60, 63)):
        out[r0:r1] = iron_lin[r0:r1] * 1.15
        out[r0] = iron_lin[r0] * 2.6              # Licht auf der Oberkante
        if r1 < TILE:
            out[r1] *= 0.55                       # Schatten unter dem Reifen
    rgb = (lin_to_srgb(out) * 255).round().astype(np.uint8)
    q = quantize(rgb, 16)
    for d in (OUT, DEMO):
        Image.fromarray(q).save(d / "barrel.png")
    return {"size": [TILE, TILE], "colors": int(len(np.unique(q.reshape(-1, 3), axis=0)))}


def build_crate():
    """Kisten-Textur 64×64 für harbor_ps1.glb (Material CrateSide, eine Textur je Würfelseite): waagrechte
    Bretter aus wood.png mit dunklen Fugen, Rahmen aus wooddark.png (7 Texel breit) mit dunkler Außenkante
    und heller Innenkante, Nägel in den Ecken. Ersetzt die 12 modellierten Leisten je Kiste."""
    wood = srgb_to_lin(np.asarray(Image.open(OUT / "wood.png").convert("RGB"), dtype=np.float64) / 255)
    dark = srgb_to_lin(np.asarray(Image.open(OUT / "wooddark.png").convert("RGB"), dtype=np.float64) / 255)
    rng = np.random.default_rng(20261013)
    out = wood.copy()
    for k, y0 in enumerate(range(0, TILE, 13)):
        out[y0:y0 + 13] *= rng.uniform(0.86, 1.1)
        out[y0] *= 0.45                            # Fuge zwischen den Brettern
    b = 7
    frame = np.zeros((TILE, TILE), bool)
    frame[:b], frame[-b:], frame[:, :b], frame[:, -b:] = True, True, True, True
    out[frame] = dark[frame] * 1.25
    out[[0, -1], :] *= 0.5
    out[:, [0, -1]] *= 0.5
    out[b, b:-b] *= 0.55                           # Schatten unter dem oberen Rahmen
    out[b:-b, b] *= 0.7
    out[b - 1, b - 1:TILE - b + 1] *= 1.3          # Licht auf der Innenkante
    for y, x in ((3, 3), (3, 60), (60, 3), (60, 60)):
        out[y, x] = dark[y, x] * 0.35              # Nägel
        out[y - 1, x - 1] = dark[y, x] * 2.4
    rgb = (lin_to_srgb(out) * 255).round().astype(np.uint8)
    q = quantize(rgb, 16)
    for d in (OUT, DEMO):
        Image.fromarray(q).save(d / "crate.png")
    return {"size": [TILE, TILE], "colors": int(len(np.unique(q.reshape(-1, 3), axis=0)))}


def build_railing():
    """Geländer der Leuchtturm-Galerie als Ausschnitt-Textur 32×32 (eine Seite des 10-eckigen Bandes,
    0,89 × 0,82 m): Handlauf oben, Mittelholm, zwei Stäbe; alles andere durchsichtig (Alpha 0, wie Farbe 0
    in einer CLUT der Konsole)."""
    iron = np.asarray(Image.open(OUT / "iron.png").convert("RGB"), dtype=np.float64)[:32, :32] / 255
    lin = srgb_to_lin(iron) * 1.2
    a = np.zeros((32, 32), np.uint8)
    out = lin.copy()
    for r0, r1 in ((0, 3), (15, 17)):             # Handlauf, Mittelholm
        a[r0:r1] = 255
        out[r0] = lin[r0] * 2.4
    for c0 in (0, 16):                            # Stäbe
        a[:, c0:c0 + 2] = 255
        out[:, c0] = lin[:, c0] * 1.8
    rgb = (lin_to_srgb(out) * 255).round().astype(np.uint8)
    q = quantize(rgb, 8)
    rgba = np.dstack([q, a])
    for d in (OUT, DEMO):
        Image.fromarray(rgba, "RGBA").save(d / "railing.png")
    return {"size": [32, 32], "colors": int(len(np.unique(q[a > 0].reshape(-1, 3), axis=0)))}


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    DEMO.mkdir(parents=True, exist_ok=True)
    info = {"tiles": build_tiles(), "sky": build_sky()}
    build_flagstone(info["tiles"])
    build_fx()
    info["barrel"] = build_barrel()
    info["railing"] = build_railing()
    info["crate"] = build_crate()
    (OUT / "textures.json").write_text(json.dumps(info, indent=1, ensure_ascii=False))
    print(json.dumps(info["sky"]))
    print({k: v["colors"] for k, v in info["tiles"].items()})


if __name__ == "__main__":
    main()
