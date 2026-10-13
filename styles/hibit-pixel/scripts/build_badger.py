#!/usr/bin/env python3
"""Dachs-Kurier für hibit-pixel: KI-Figurenblatt -> 60-px-Sprites mit Normal Maps, Porträt fürs Textfenster.

    .venv/bin/python styles/hibit-pixel/scripts/build_badger.py [--preview]

Eingabe: assets/raw/badger.png (8 Laufbilder oben, 4 Stehbilder unten; gezeichnet über die Blender-Posen aus
blender/walk_layout.py). Ablauf:
  1. Figuren über Alpha >= 200 ausschneiden (das Blatt hat einen halbtransparenten Dunst).
  2. Eine gemeinsame Palette (k-means in Oklab) für alle Bilder.
  3. Je Bild ein Zielraster, dessen Ursprung am Kopf hängt (Schwerpunkt im oberen Viertel) und dessen Grundlinie
     auf der Fußlinie liegt; je Reihe derselbe Maßstab (die Stehreihe ist im Blatt 6 % größer gezeichnet).
     Je Zielpixel entscheidet die Mehrheit im Zellinneren (deckend/transparent, dann Palettenfarbe).
  4. Kontur schließen: deckende Randpixel ohne dunkle Farbe bekommen die dunkle Variante ihres Materials.
  5. Korrekturen aus Teilen (Augen in Laufbild 2, Stehbild mit offenem Auge, Atmen + Blinzeln als fünftes
     Stehbild), Kantenlicht an der Vorderkante der Beine, Normal Maps (Höhe aus Helligkeit +
     Wölbung zum Umriss), gespiegelte Fassungen nach links (Normal-x umgedreht).
Ausgaben in assets/ und demo/art/: badger_walk(_n).png, badger_stand(_n).png, je *_l für links, badger.json,
portrait.png.
"""
import json, pathlib, sys

import numpy as np
from PIL import Image

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from hblib import box_blur, dist_inside, encode_normals, kmeans, nearest, normals_from_height, oklab, oklab_to_rgb

ROOT = pathlib.Path(__file__).resolve().parents[1]
RAW = ROOT / "assets" / "raw"
OUT_A, OUT_D = ROOT / "assets", ROOT / "demo" / "art"
TH = 64          # Zielhöhe der Figur in Pixeln
CW, CH = 52, 68  # Zellgröße im Sprite-Streifen
AX = 29          # Spalte des Kopfankers in der Zelle (Figur blickt nach rechts)
BASE = CH - 2    # Fußlinie (letzte deckende Zeile) in der Zelle
NCOL = 30
DARK_SHARE = 0.34
LEG_ROW = 49     # ab dieser Zellenzeile: Hose und Beine (unter Paket und Tasche)
LEG_RIM_L = 0.62  # Oklab-L des Kantenlichts an der Vorderkante der Beine (Farbton der Beinrampe)
PATCH = "--nopatch" not in sys.argv


def runs(v, gap):
    idx = np.flatnonzero(v)
    out, s, p = [], idx[0], idx[0]
    for i in idx[1:]:
        if i - p > gap:
            out.append((s, p + 1)); s = i
        p = i
    out.append((s, p + 1))
    return out


def figures(m):
    figs = []
    for r, (y0, y1) in enumerate(runs(m.any(1), 20)):
        for x0, x1 in runs(m[y0:y1].any(0), 3):
            sub = m[y0:y1, x0:x1]
            ys = np.flatnonzero(sub.any(1))
            figs.append({"row": r, "x0": int(x0), "x1": int(x1), "top": int(y0 + ys[0]), "bot": int(y0 + ys[-1])})
    return figs


def head_x(m, f):
    h = f["bot"] - f["top"] + 1
    sub = m[f["top"]:f["top"] + h // 4, f["x0"]:f["x1"]]
    return f["x0"] + np.nonzero(sub)[1].mean()


def reduce_fig(lbl, m, f, scale, hx, dark):
    """Zielzelle (CW×CH): Ursprung so, dass der Kopfanker bei AX und die Fußlinie bei BASE liegt.

    Deckung: Anteil deckender Quellpixel in der ganzen Zelle >= 0,5. Farbe: häufigster Index im Zellinneren;
    dunkle Linien (Kontur innen, Auge, Nase, Mund) gewinnen schon ab DARK_SHARE, sonst verschwinden 1-px-Linien
    des Blatts beim Verkleinern (Blatt: ca. 2,3 Bildpixel je Kunstpixel, Ziel: 4,7).
    """
    ox = hx - (AX + 0.5) * scale
    oy = (f["bot"] + 1) - (BASE + 1) * scale
    idx = np.full((CH, CW), -1, np.int64)
    inset = 0.15
    for v in range(CH):
        fy0, fy1 = oy + v * scale, oy + (v + 1) * scale
        if fy1 <= 0 or fy0 >= lbl.shape[0]:
            continue
        for u in range(CW):
            fx0, fx1 = ox + u * scale, ox + (u + 1) * scale
            a0, a1 = max(0, int(round(fy0))), min(lbl.shape[0], int(round(fy1)))
            b0, b1 = max(f["x0"] - 2, int(round(fx0))), min(f["x1"] + 2, int(round(fx1)))
            if a1 <= a0 or b1 <= b0 or m[a0:a1, b0:b1].mean() < 0.5:
                continue
            y0 = int(np.floor(fy0 + inset * scale)); y1 = max(y0 + 1, int(np.ceil(fy1 - inset * scale)))
            x0 = int(np.floor(fx0 + inset * scale)); x1 = max(x0 + 1, int(np.ceil(fx1 - inset * scale)))
            mm = m[y0:y1, x0:x1]
            if not mm.any():
                mm, y0, y1, x0, x1 = m[a0:a1, b0:b1], a0, a1, b0, b1
            ll = lbl[y0:y1, x0:x1][mm]
            bc = np.bincount(ll, minlength=NCOL)
            dk = bc * dark
            if dk.sum() >= DARK_SHARE * len(ll):
                idx[v, u] = int(np.argmax(dk))
            else:
                idx[v, u] = int(np.argmax(bc))
    return idx


def close_outline(idx, lab):
    """Umriss schließen: deckende Pixel an Transparenz bekommen die Konturfarbe (dunkles Pflaume wie im Blatt),
    wenn sie nicht schon dunkel sind."""
    L = lab[:, 0]
    plum = int(np.argmin(np.abs(L - 0.16) + 10 * (np.abs(lab[:, 1] - 0.04) > 0.03)))
    op = idx >= 0
    nb = np.zeros_like(op)
    nb[1:] |= ~op[:-1]; nb[:-1] |= ~op[1:]; nb[:, 1:] |= ~op[:, :-1]; nb[:, :-1] |= ~op[:, 1:]
    nb[0] = True; nb[-1] = True; nb[:, 0] = True; nb[:, -1] = True
    edge = op & nb
    out = idx.copy()
    fix = edge & (L[np.clip(idx, 0, None)] >= 0.25)
    out[fix] = plum
    return out


def normal_map(rgb, alpha):
    m = alpha > 0
    L = oklab(rgb.reshape(-1, 3))[:, 0].reshape(alpha.shape)
    dome = dist_inside(m, 6) / 6.0
    dome = np.sqrt(np.clip(dome, 0, 1))                  # gewölbt, flacher in der Mitte
    h = 3.0 * box_blur(L * m, 1) + 2.2 * dome
    h[~m] = 0
    n = normals_from_height(h, 1.6)
    n[~m] = (0, 0, 1)
    return n


def main(preview=False):
    sheet = np.asarray(Image.open(RAW / "badger.png").convert("RGBA"))
    m = sheet[..., 3] >= 200
    figs = figures(m)
    assert len(figs) == 12, len(figs)
    rgb = sheet[..., :3]
    lab_all = oklab(rgb[m])
    rng = np.random.default_rng(5)
    cent = kmeans(lab_all[rng.choice(len(lab_all), 80000, replace=False)], NCOL, iters=25, seed=5)
    lbl = np.zeros(m.shape, np.int64)
    lbl[m] = nearest(lab_all, cent)
    pal = np.clip(np.round(oklab_to_rgb(cent)), 0, 255).astype(np.uint8)
    dark = cent[:, 0] < 0.25

    heights = {r: np.median([f["bot"] - f["top"] + 1 for f in figs if f["row"] == r]) for r in (0, 1)}
    frames = []
    for f in figs:
        scale = heights[f["row"]] / TH
        hx = head_x(m, f)
        idx = reduce_fig(lbl, m, f, scale, hx, dark)
        frames.append(idx)
    walk, stand = frames[:8], frames[8:]

    # Laufbild 2 hat die Augen geschlossen: Augenfenster aus Laufbild 1 übernehmen (Kopf auf gleicher Höhe?)
    def head_top(idx):
        return int(np.flatnonzero((idx >= 0).any(1))[0])
    fixes = []

    def eye_patch(dst, src, box):
        x0, x1, y0, y1 = box
        dt, st = head_top(dst), head_top(src)
        dst[dt + y0:dt + y1, x0:x1] = src[st + y0:st + y1, x0:x1]
        fixes.append({"box": box, "dy": int(dt - st)})

    # Fenster (x0, x1, y0, y1) relativ zur Kopfoberkante, aus der Pixelkarte des verkleinerten Bildes abgelesen
    EYE = (32, 37, 9, 14)
    if PATCH:
        eye_patch(walk[2], walk[1], EYE)
    def close_mouth(idx, rows, x_from):
        """Rote Mundpixel in der Schnauze durch das Weiß der Schnauze ersetzen (Mundlinie bleibt)."""
        out = idx.copy()
        white = None
        for v in range(*rows):
            for u in range(x_from, out.shape[1]):
                c = out[v, u]
                if c >= 0 and cent[c, 0] > 0.75:
                    white = c
                if c >= 0 and cent[c, 1] > 0.06 and cent[c, 0] > 0.3 and white is not None:
                    out[v, u] = white
                    fixes.append({"mouth_closed": [int(u), int(v)]})
        return out

    def blink(idx, box):
        """Auge schließen: Iris, Pupille und Glanzpunkt im Fenster -> Fell des Augenstreifs, darüber ein Lid-Strich."""
        x0, x1, y0, y1 = box
        out = idx.copy()
        win = out[y0:y1, x0:x1]
        Lw = np.where(win >= 0, cent[np.clip(win, 0, None), 0], -1)
        aw = np.where(win >= 0, cent[np.clip(win, 0, None), 1], 0)
        bw = np.where(win >= 0, cent[np.clip(win, 0, None), 2], 0)
        iris = (win >= 0) & (aw > 0.03) & (bw > 0.05) & (Lw > 0.35) & (Lw < 0.75)
        if not iris.any():
            return out, None
        ys, xs = np.nonzero(iris)
        cy, cx0, cx1 = int(round(ys.mean())), xs.min(), xs.max()
        furs = win[(win >= 0) & (Lw > 0.25) & (Lw < 0.45) & (np.abs(aw) < 0.03)]
        fur = np.bincount(furs).argmax() if furs.size else win[cy, cx0]
        eye = iris.copy()
        for yy, xx in zip(ys, xs):    # Pupille/Glanz direkt neben der Iris mitnehmen
            for dy, dx in ((0, 1), (0, -1), (1, 0), (-1, 0)):
                y2, x2 = yy + dy, xx + dx
                if 0 <= y2 < win.shape[0] and 0 <= x2 < win.shape[1] and win[y2, x2] >= 0 and (Lw[y2, x2] < 0.2 or Lw[y2, x2] > 0.85):
                    eye[y2, x2] = True
        win[eye] = fur
        lid = int(np.argmin(np.where(cent[:, 0] > 0.1, cent[:, 0], 9)))
        win[min(cy + 1, win.shape[0] - 1), max(0, cx0 - 1):cx1 + 2] = lid
        return out, [int(x0 + cx0), int(y0 + cy)]

    # Stehen: Sprechbild B (Auge offen, Mund halb offen) mit geschlossenem Mund ist die Grundpose; daraus aus
    # Teilen: Blinzeln (Auge zu), Sprechen (= Sprechbild B), Atmen (Oberkörper 1 px tiefer, Beine fest),
    # Atmen + Blinzeln (Blinzelbild mit demselben Atemversatz, damit Blinzeln in der Atemphase nicht springt).
    talk = stand[3].copy()
    top = head_top(talk)
    base = close_mouth(talk, (top + 15, top + 19), 36) if PATCH else talk
    blinked, eye_at = blink(base, (31, 38, top + 8, top + 15))
    fixes.append({"blink_eye": eye_at})
    WAIST = 44

    def breathe_of(src):
        out = src.copy()
        out[1:WAIST + 1] = src[0:WAIST]
        out[0] = -1
        return out

    breathe = breathe_of(base)
    breathe_blink = breathe_of(blinked)
    stand_frames = [base, blinked, talk, breathe, breathe_blink]   # stehen, blinzeln, sprechen, atmen, atmen+blinzeln

    lab_pal = cent
    walk = [close_outline(w, lab_pal) for w in walk]
    stand_frames = [close_outline(s, lab_pal) for s in stand_frames]

    # Kantenlicht an den Beinen: Im Blatt unterscheiden sich vorderes und hinteres Bein nur um 0,04–0,08 in L und
    # liegen vor dem abgedunkelten Kai (L ≈ 0,40) als eine dunkle Masse. Je Zeile ab LEG_ROW bekommt das vorderste
    # Pixel jedes Beinabschnitts (rechts davon Kontur oder Leere; nach dem Spiegeln die Seite zur Laterne) einen
    # hellen Kantenton. So hat jedes Bein eine eigene Vorderkante, und der Schritt liest sich. Gleichmäßiges
    # Aufhellen oder Spreizen der Rampe brachte die Beine nur auf die Helligkeit des Kais (geprüft und verworfen).
    Cc = np.hypot(cent[:, 1], cent[:, 2])
    ramp = (cent[:, 0] > 0.20) & (cent[:, 0] < 0.40) & (Cc < 0.045) & (cent[:, 1] > 0.015) & (np.abs(cent[:, 2]) < 0.012)
    rim_lab = np.array([LEG_RIM_L, *np.median(cent[ramp][:, 1:], axis=0)])
    rim_c = len(cent)
    cent = np.vstack([cent, rim_lab[None]])
    pal = np.clip(np.round(oklab_to_rgb(cent)), 0, 255).astype(np.uint8)
    Lp = cent[:, 0]

    def leg_rim(idx):
        out = idx.copy()
        for v in range(LEG_ROW, idx.shape[0]):
            row = idx[v]
            for u in range(idx.shape[1] - 1):
                c, r = row[u], row[u + 1]
                if c >= 0 and ramp[c] and (r < 0 or Lp[r] < 0.20):
                    out[v, u] = rim_c
        return out

    walk = [leg_rim(w) for w in walk]
    stand_frames = [leg_rim(s) for s in stand_frames]
    fixes.append({"leg_rim": {"row": LEG_ROW, "L": LEG_RIM_L, "rgb": pal[rim_c].tolist(),
                              "px_per_frame": [int((w == rim_c).sum()) for w in walk + stand_frames]}})

    def strip(frs, flip=False):
        n = len(frs)
        col = np.zeros((CH, CW * n, 3), np.uint8)
        al = np.zeros((CH, CW * n), np.uint8)
        nrm = np.zeros((CH, CW * n, 3), np.uint8)
        for i, idx in enumerate(frs):
            a = (idx >= 0)
            c = pal[np.clip(idx, 0, None)]
            c[~a] = 0
            nm = normal_map(c, a.astype(np.uint8))
            if flip:
                a, c, nm = a[:, ::-1], c[:, ::-1], nm[:, ::-1].copy()
                nm[..., 0] *= -1
            col[:, i * CW:(i + 1) * CW] = c
            al[:, i * CW:(i + 1) * CW] = a * 255
            nrm[:, i * CW:(i + 1) * CW] = encode_normals(nm)
        return np.dstack([col, al]), nrm

    meta = {"cell": [CW, CH], "anchor_x": AX, "baseline": BASE, "height": TH, "palette": len(pal),
            "row_heights_src": heights, "fixes": fixes}
    for name, frs in (("walk", walk), ("stand", stand_frames)):
        for flip, suf in ((False, ""), (True, "_l")):
            c, n = strip(frs, flip)
            Image.fromarray(c, "RGBA").save(OUT_D / f"badger_{name}{suf}.png")
            Image.fromarray(n, "RGB").save(OUT_D / f"badger_{name}{suf}_n.png")
            if not flip:
                Image.fromarray(c, "RGBA").save(OUT_A / f"badger_{name}.png")
                Image.fromarray(n, "RGB").save(OUT_A / f"badger_{name}_n.png")
    (OUT_D / "badger.json").write_text(json.dumps(meta, indent=1))

    # Porträt fürs Textfenster: Kopf und Schultern aus Sprechbild B in höherer Auflösung (gleiche Palette),
    # Grundbild/Blinzeln/Sprechen wie beim Sprite aus Teilen desselben Bildes.
    f = figs[11]
    hx = head_x(m, f)
    sc = (f["bot"] - f["top"] + 1) / 112.0      # Figur 112 px hoch: Kopf, Schal und Schultern im 52er-Feld
    ox, oy = hx - 22 * sc, f["top"] - 3 * sc
    P = 52
    ptalk = np.full((P, P), -1, np.int64)
    for v in range(P):
        y0 = int(oy + (v + 0.2) * sc); y1 = max(y0 + 1, int(np.ceil(oy + (v + 0.8) * sc)))
        for u in range(P):
            x0 = int(ox + (u + 0.2) * sc); x1 = max(x0 + 1, int(np.ceil(ox + (u + 0.8) * sc)))
            mm = m[y0:y1, x0:x1]
            if mm.size and mm.mean() >= 0.5:
                ptalk[v, u] = np.bincount(lbl[y0:y1, x0:x1][mm], minlength=NCOL).argmax()
    pbase = close_mouth(ptalk, (27, 36), 34)
    pblink, peye = blink(pbase, (28, 42, 18, 30))
    fixes.append({"portrait_blink_eye": peye})
    por = [pbase, pblink, ptalk]
    pc = np.zeros((52, 52 * len(por), 4), np.uint8)
    for i, idx in enumerate(por):
        a = idx >= 0
        c = pal[np.clip(idx, 0, None)]
        pc[:, i * 52:(i + 1) * 52, :3] = c
        pc[:, i * 52:(i + 1) * 52, 3] = a * 255
    Image.fromarray(pc, "RGBA").save(OUT_D / "portrait.png")
    Image.fromarray(pc, "RGBA").save(OUT_A / "portrait.png")
    print(json.dumps(meta))


if __name__ == "__main__":
    main("--preview" in sys.argv)
