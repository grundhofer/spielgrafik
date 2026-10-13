#!/usr/bin/env python3
"""Schlussszene der Demo: der Hafen im VGA-Stil aus dem jeweils besseren Bild der Paare.

    .venv/bin/python styles/bildmodelle-vergleich/scripts/build_final.py [--preview out.png]

Hintergrund: Codex-Bild des VGA-Paars (styles/vga-adventure/assets/raw/bg.png; das agy-Bild malt Letterbox-
Balken und hat kaum Farbverläufe). BOX-Verkleinerung 1536×1024 → 320×213, Zeilen 34–171 als Szene 320×138,
Median-Cut auf 224 Farben ohne Dithering, jeder Kanal auf 6 Bit (VGA-DAC) gerundet.

Figur: Laufreihe des agy-Figurenblatts (assets/raw/vga_badger_agy.png; mehr verschiedene Beinstellungen, Kopf
wippt, freigestellt mit 1-Bit-Alpha). Die Stehreihe des Blatts ist 1,29-mal so groß gezeichnet und wird nicht
benutzt; Stehen = Durchgangsbild (Beine zusammen). Verkleinern wie in PIPELINE.md beschrieben:
  1. gemeinsame Palette aus allen Laufbildern (k-means, 24 Farben, 6 Bit je Kanal)
  2. jedes Quellpixel einer Palettenfarbe zuordnen, dann je Zielpixel Mehrheitsentscheid (kein Mitteln)
  3. alle Bilder auf einem gemeinsamen Raster: Kopfanker (Schwerpunkt der oberen 25 %) auf dieselbe Spalte,
     Fußlinie auf dieselbe Zeile, ein Maßstab für alle Bilder
  4. Alpha hart: Zielpixel deckend, wenn mehr als die Hälfte der Quellpixel deckend ist
Ausgabe: demo/art/final_bg.png, demo/art/badger_walk.png (Zellen nebeneinander), demo/art/badger.json
(Zellgröße, Fußzeile, Kopfspalte, Vorschub je Bild aus dem gemessenen Standfuß, Augenpixel für das Blinzeln).
"""
import argparse, json, pathlib
import numpy as np
from PIL import Image

HERE = pathlib.Path(__file__).resolve().parent
ENTRY = HERE.parent
ROOT = ENTRY.parent.parent
ART = ENTRY / "demo" / "art"

BG_SRC = ROOT / "styles/vga-adventure/assets/raw/bg.png"
SHEET = ENTRY / "assets/raw/vga_badger_agy.png"
CROP_TOP, SCENE_H = 34, 138
TARGET_H = 46            # Figurhöhe in Zielpixeln (Mittel der Laufbilder); bei 40 px verschwinden Auge und Streifen
CELL = (46, 50)          # Zelle je Bild (Breite, Höhe)
FOOT_ROW = 48            # Fußzeile in der Zelle (unterste deckende Zeile)
HEAD_COL = 25            # Kopfanker-Spalte in der Zelle
IDLE_FRAME = 5           # Durchgangsbild als Standpose
BREATH_ROW = 30          # Zeilen 0..30 (bis zur Hüfte) sinken beim Atmen um 1 px


def vga6(c):
    v6 = np.round(np.asarray(c, dtype=np.float64) * 63 / 255).astype(np.int32)
    return (v6 << 2) | (v6 >> 4)


def build_bg():
    im = Image.open(BG_SRC).convert("RGB").resize((320, 213), Image.BOX)
    im = im.crop((0, CROP_TOP, 320, CROP_TOP + SCENE_H))
    q = im.quantize(colors=224, method=Image.Quantize.MEDIANCUT, dither=Image.Dither.NONE)
    pal = np.array(q.getpalette()[:224 * 3]).reshape(-1, 3)
    pal = vga6(pal)
    idx = np.asarray(q)
    out = pal[idx].astype(np.uint8)
    Image.fromarray(out).save(ART / "final_bg.png")
    n = len(np.unique(out.reshape(-1, 3), axis=0))
    print("final_bg.png", out.shape[1], "x", out.shape[0], "Farben", n)
    return n


def runs(mask, min_gap):
    idx = np.flatnonzero(mask)
    out, s, p = [], idx[0], idx[0]
    for i in idx[1:]:
        if i - p > min_gap:
            out.append((s, p + 1))
            s = i
        p = i
    out.append((s, p + 1))
    return out


def frames_of_row(a, row=0):
    op = a[..., 3] >= 128
    rows = [r for r in runs(op.any(1), 10) if r[1] - r[0] > 40]
    y0, y1 = rows[row]
    cols = [c for c in runs(op[y0:y1].any(0), 4) if c[1] - c[0] > 30]
    return [(x0, y0, x1, y1) for x0, x1 in cols]


def kmeans(x, k, iters=30, seed=7):
    rng = np.random.default_rng(seed)
    c = x[rng.choice(len(x), k, replace=False)].astype(np.float64)
    for _ in range(iters):
        d = ((x[:, None, :] - c[None]) ** 2).sum(-1)
        lab = d.argmin(1)
        for j in range(k):
            m = lab == j
            if m.any():
                c[j] = x[m].mean(0)
    return c


def build_badger():
    a = np.asarray(Image.open(SHEET).convert("RGBA")).astype(np.int32)
    boxes = frames_of_row(a, 0)
    heights = []
    for x0, y0, x1, y1 in boxes:
        ys = np.flatnonzero((a[y0:y1, x0:x1, 3] >= 128).any(1))
        heights.append(ys[-1] - ys[0] + 1)
    scale = TARGET_H / float(np.mean(heights))
    step = 1.0 / scale
    # gemeinsame Palette
    samples = []
    for x0, y0, x1, y1 in boxes:
        sub = a[y0:y1, x0:x1]
        samples.append(sub[sub[..., 3] >= 128][:, :3])
    allpx = np.concatenate(samples)
    rng = np.random.default_rng(3)
    pal = kmeans(allpx[rng.choice(len(allpx), min(40000, len(allpx)), replace=False)].astype(np.float64), 24)
    pal = vga6(np.clip(pal, 0, 255))
    # Freistellsaum: agy stellt auf Magenta frei; am Rand bleiben dunkle Lilatöne (z. B. 36/0/24) als eigene
    # Palettenfarbe übrig. Solche Einträge auf die nächste nicht lilafarbene Farbe umlenken.
    purple = (pal[:, 0] > pal[:, 1] + 15) & (pal[:, 2] > pal[:, 1] + 15)
    remap = np.arange(len(pal))
    for j in np.flatnonzero(purple):
        d = ((pal - pal[j]) ** 2).sum(1).astype(np.float64)
        d[purple] = np.inf
        remap[j] = int(d.argmin())
    cells, info = [], []
    for fi, (x0, y0, x1, y1) in enumerate(boxes):
        sub = a[y0:y1, x0:x1]
        op = sub[..., 3] >= 128
        ys = np.flatnonzero(op.any(1))
        top, bot = ys[0], ys[-1]
        h = bot - top + 1
        topq = op[top:top + h // 4]
        hx = float(np.nonzero(topq)[1].mean())
        # Palettenindex je Quellpixel (-1 = durchsichtig)
        rgb = sub[..., :3].reshape(-1, 1, 3)
        ids = np.full(op.size, -1, dtype=np.int32)
        flat = op.reshape(-1)
        d = ((rgb[flat] - pal[None]) ** 2).sum(-1)
        ids[flat] = remap[d.argmin(1)]
        ids = ids.reshape(op.shape)
        cell_rgba = np.zeros((CELL[1], CELL[0], 4), dtype=np.uint8)
        cell_ids = np.full((CELL[1], CELL[0]), -1, dtype=np.int32)
        for v in range(CELL[1]):
            # Zielzeile v deckt Quellzeilen [sy0, sy1); Fußzeile FOOT_ROW endet an der untersten Quellzeile
            sy1 = bot + 1 - (FOOT_ROW - v) * step
            sy0 = sy1 - step
            r0, r1 = int(round(sy0)), int(round(sy1))
            if r1 <= 0 or r0 >= op.shape[0]:
                continue
            r0, r1 = max(r0, 0), min(r1, op.shape[0])
            for u in range(CELL[0]):
                sx0 = hx + (u - HEAD_COL) * step
                c0, c1 = int(round(sx0)), int(round(sx0 + step))
                if c1 <= 0 or c0 >= op.shape[1]:
                    continue
                c0, c1 = max(c0, 0), min(c1, op.shape[1])
                blk = ids[r0:r1, c0:c1].reshape(-1)
                if blk.size == 0 or (blk >= 0).mean() <= 0.5:
                    continue
                vals, cnt = np.unique(blk[blk >= 0], return_counts=True)
                k = vals[cnt.argmax()]
                cell_ids[v, u] = k
                cell_rgba[v, u, :3] = pal[k]
                cell_rgba[v, u, 3] = 255
        cells.append(cell_rgba)
        opc = cell_ids >= 0
        ys2 = np.flatnonzero(opc.any(1))
        info.append({"src_box": [int(x0), int(y0), int(x1), int(y1)], "src_height": int(h),
                     "head_x_src": round(hx, 1), "top": int(ys2[0]), "bottom": int(ys2[-1])})
    return cells, info, pal, scale, [[int(v) for v in pal[j]] for j in np.flatnonzero(purple)]


def feet(cell):
    """Fußpunkte: in den untersten 3 Zeilen die deckenden Läufe (links→rechts) mit ihren Rändern."""
    op = cell[..., 3] > 0
    rows = np.flatnonzero(op.any(1))
    bot = rows[-1]
    band = op[bot - 2:bot + 1].any(0)
    rs = runs(band, 1) if band.any() else []
    return [(int(s), int(e - 1)) for s, e in rs], int(bot)


def advances(feet_list):
    """Vorschub je Bildwechsel aus dem Standfuß. Kontaktbilder haben zwei Fußläufe (hinten, vorn), Durchgangsbilder
    einen. Kontakt → Durchgang: der vordere Fuß setzt auf und bleibt stehen, also Vorschub = Spitze vorn (Kontakt)
    − Spitze (Durchgang). Durchgang → Kontakt: derselbe Fuß ist jetzt der hintere, Vorschub = Spitze (Durchgang)
    − Spitze hinten (Kontakt). Spitze = rechter Rand des Laufs (die Figur läuft nach rechts).
    Kontakt = zwei Läufe mit mindestens 5 px Lücke; sonst Durchgang mit der Spitze ganz rechts."""
    def kind(f):
        if len(f) >= 2 and f[-1][0] - f[0][1] >= 5:
            return "contact", f[0][1], f[-1][1]
        return "passing", None, f[-1][1]
    out = []
    n = len(feet_list)
    for i in range(n):
        ka, backa, fronta = kind(feet_list[i])
        kb, backb, frontb = kind(feet_list[(i + 1) % n])
        if ka == "contact" and kb == "passing":
            out.append(fronta - frontb)
        elif ka == "passing" and kb == "contact":
            out.append(fronta - backb)
        else:
            out.append(None)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--preview")
    a = ap.parse_args()
    ART.mkdir(parents=True, exist_ok=True)
    nbg = build_bg()
    cells, info, pal, scale, purple = build_badger()
    for i, (c, inf) in enumerate(zip(cells, info)):
        f, bot = feet(c)
        inf["feet"] = f
        print(f"Bild {i}: Höhe {inf['bottom'] - inf['top'] + 1} px, oben {inf['top']}, Fußzeile {bot}, Füße {f}")
    adv = advances([inf["feet"] for inf in info])
    print("Vorschub je Bildwechsel (px):", adv, "Lilatöne umgelenkt:", purple)
    sheet = np.concatenate(cells, axis=1)
    Image.fromarray(sheet).save(ART / "badger_walk.png")
    # Stehen: Durchgangsbild IDLE_FRAME (Beine zusammen); Atmen = Oberkörper (Zeilen bis BREATH_ROW) 1 px tiefer,
    # Beine bleiben (Teile statt eines zweiten KI-Bilds, damit nichts flimmert)
    idle = cells[IDLE_FRAME].copy()
    breath = idle.copy()
    breath[1:BREATH_ROW + 1] = idle[0:BREATH_ROW]
    breath[0] = 0
    Image.fromarray(np.concatenate([idle, breath], axis=1)).save(ART / "badger_idle.png")
    # Lichthöfe: radiale Stufen (4 Alphastufen, keine weichen Verläufe), Farbe kommt in Godot über modulate
    for name, r in (("glow_lamp", 7), ("glow_lantern", 11), ("glow_window", 14)):
        n = 2 * r + 1
        yy, xx = np.mgrid[0:n, 0:n] - r
        d = np.sqrt(xx ** 2 + yy ** 2) / r
        al = np.select([d < 0.35, d < 0.6, d < 0.82, d <= 1.0], [255, 150, 80, 36], 0).astype(np.uint8)
        img = np.dstack([np.full((n, n, 3), 255, np.uint8), al])
        Image.fromarray(img).save(ART / f"{name}.png")
    meta = {"cell": list(CELL), "frames": len(cells), "foot_row": FOOT_ROW, "head_col": HEAD_COL,
            "scale": round(scale, 4), "palette": [list(map(int, p)) for p in pal], "frames_info": info,
            "bg_colours": nbg, "scene_crop_top": CROP_TOP,
            "advance": adv, "purple_remapped": purple, "idle_frame": IDLE_FRAME, "breath_row": BREATH_ROW}
    (ART / "badger.json").write_text(json.dumps(meta, indent=1))
    if a.preview:
        big = Image.fromarray(sheet).resize((sheet.shape[1] * 8, sheet.shape[0] * 8), Image.NEAREST)
        bg = Image.new("RGBA", big.size, (90, 100, 120, 255))
        bg.alpha_composite(big)
        bg.convert("RGB").save(a.preview)


if __name__ == "__main__":
    main()
