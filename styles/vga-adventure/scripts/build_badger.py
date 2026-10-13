#!/usr/bin/env python3
"""Dachs-Kurier: KI-Sheet (2 Reihen: 6 Lauf-, 4 Steh/Sprech-Frames) -> 40-px-Sprites mit gemeinsamer Palette.

    .venv/bin/python styles/vga-adventure/scripts/build_badger.py [--height 40] [--preview out.png]

Das Bildmodell zeichnet Figuren immer mit ca. 70 Kunstpixeln Höhe. Für 320x200 wird jede Figur mit
vormultipliziertem BOX-Filter auf die Zielhöhe verkleinert, auf eine gemeinsame Palette (k-means in Oklab)
gebracht, Alpha hart geschnitten (1 Bit), Einzelpixel bereinigt und eine dunkle 1-px-Kontur gesetzt.

Ausrichtung: Alle Bilder einer Reihe werden auf einem gemeinsamen Raster verkleinert, dessen Ursprung am
Bezugspunkt hängt (gleiche Körperteile -> gleiche Zielpixel). Bezugspunkt ist der Kopf, gemessen nur im oberen
Viertel, damit ein erhobener Gestik-Arm die Figur nicht seitlich verschiebt. Die Beinzeilen der Stehbilder
stammen alle aus einem Bild (die Füße stehen beim Sprechen still).

Nacharbeit wie bei einer Pixel-Künstlerin: Weste und Paket werden auf 2-3 feste Tonwerte geglättet
(Mehrheitsfilter innerhalb der Materialfläche), das Paket bekommt eine dunkle Unterkante und Schnur.
"""
import argparse, pathlib, sys
import numpy as np
from PIL import Image

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from pixgrid import kmeans, nearest, oklab  # noqa: E402

STYLE = HERE.parent
RAW = STYLE / 'assets/raw/badger_small.png'


def runs(mask, min_gap):
    idx = np.flatnonzero(mask)
    out, s, p = [], idx[0], idx[0]
    for i in idx[1:]:
        if i - p > min_gap:
            out.append((s, p + 1)); s = i
        p = i
    out.append((s, p + 1))
    return out


def extract(path):
    im = Image.open(path).convert('RGBA')
    a = np.asarray(im)
    op = a[..., 3] >= 128
    rows = [r for r in runs(op.any(1), 20) if r[1] - r[0] > 100]
    out = []
    for y0, y1 in rows:
        cols = [c for c in runs(op[y0:y1].any(0), 8) if c[1] - c[0] > 60]
        frames = []
        for x0, x1 in cols:
            sub = op[y0:y1, x0:x1]
            ys = np.flatnonzero(sub.any(1))
            frames.append(im.crop((x0, y0 + ys[0], x1, y0 + ys[-1] + 1)))
        out.append(frames)
    return out


def premult_box(im, size, box=None):
    """Vormultiplizierte BOX-Verkleinerung; box = Ausschnitt in Quellkoordinaten (darf über den Rand ragen)."""
    if box is not None:
        m = int(np.ceil(max(0, -box[0], -box[1], box[2] - im.width, box[3] - im.height))) + 1
        pad = Image.new('RGBA', (im.width + 2 * m, im.height + 2 * m), (0, 0, 0, 0))
        pad.paste(im, (m, m))
        im, box = pad, (box[0] + m, box[1] + m, box[2] + m, box[3] + m)
    a = np.asarray(im).astype(np.float64) / 255
    pm = a.copy(); pm[..., :3] *= pm[..., 3:4]
    big = Image.fromarray(np.round(pm * 255).astype(np.uint8))
    s = np.asarray(big.resize(size, Image.BOX, box=box)).astype(np.float64) / 255
    al = s[..., 3:4]
    rgb = np.where(al > 1e-3, s[..., :3] / np.maximum(al, 1e-3), 0)
    return np.dstack([np.clip(rgb * 255, 0, 255), al[..., 0] * 255])


def head_cx(alpha, frac=0.25):
    """x-Schwerpunkt der opaken Pixel im oberen Viertel (Mütze + Kopf). Bewusst nicht tiefer: ein erhobener
    Gestik-Arm beginnt bei etwa 35 % der Höhe und darf den Bezugspunkt nicht verschieben."""
    top = alpha[: int(alpha.shape[0] * frac)]
    return float(np.nonzero(top)[1].mean())


def geometry(height):
    """Je Reihe: Rohbilder, Anker (Rohpixel), Maßstab k und Zelle (Breite, Höhe, Ankerspalte)."""
    rows = extract(RAW)
    out = []
    for ri, frames in enumerate(rows):
        fh = max(f.height for f in frames)
        k = height / fh
        alphas = [np.asarray(f)[..., 3] >= 128 for f in frames]
        # Alle Bilder am Kopf (oberes Viertel) ausrichten: Laufen und Stehen gehen ohne Sprung ineinander über,
        # und der Kopf bleibt beim Sprechen ruhig. Die Füße der Stehbilder werden in build() vereinheitlicht
        # (Beinzeilen aus einem Bild), weil die KI Bild 0 mit ca. 1 px anderem Kopf-Fuß-Abstand gezeichnet hat.
        anc = [head_cx(al) for al in alphas]
        AX = int(np.ceil(max(a * k for a in anc))) + 1
        CW = AX + int(np.ceil(max((f.width - a) * k for f, a in zip(frames, anc)))) + 1
        out.append((frames, anc, k, (CW, height, AX)))
    return out


MATERIALS = ('rot', 'gruen', 'paket', 'hell', 'braun', 'fell', 'dunkel')
RAMPS = {'rot': 3, 'gruen': 2, 'paket': 2, 'hell': 3, 'braun': 2, 'fell': 3, 'dunkel': 1}
# Vorrang bei der Mehrheitsentscheidung je Zielpixel: dunkle Kleinteile (Auge, Nase, Mund) sollen überleben
PRIORITY = {'rot': 1.0, 'gruen': 1.0, 'paket': 1.1, 'hell': 1.0, 'braun': 1.0, 'fell': 1.0, 'dunkel': 1.3}


def classify_raw(lab):
    """Material je Rohpixel aus Oklab (L, a, b): Schal, Weste/Mütze, Paket, Hell (Gesicht, Bauch, Hemd),
    Leder (Tasche, Riemen), Fell (dunkelgrau), Dunkel (Kontur, Auge)."""
    L, a, b = lab[..., 0], lab[..., 1], lab[..., 2]
    M = {m: i for i, m in enumerate(MATERIALS)}
    m = np.full(L.shape, M['fell'])
    m[L >= 0.55] = M['hell']
    m[(b > 0.08) & (L > 0.5)] = M['paket']
    m[(a >= 0.03) & (b >= 0.04) & (L < 0.55) & (L >= 0.215)] = M['braun']
    m[a < -0.01] = M['gruen']
    red = (a > 0.06) & (a > 1.2 * b)
    m[red] = M['rot']
    m[(L < 0.215) & ~red] = M['dunkel']
    return m


def material_cells(f, anchor, k, cell):
    """Materialtreue Verkleinerung: je Zielpixel gewinnt das Material mit den meisten Rohpixeln (mit Vorrang),
    der Tonwert ist das Oklab-Mittel nur dieses Materials. Keine Mischfarben über Materialgrenzen hinweg."""
    CW, height, AX = cell
    arr = np.asarray(f)
    ys, xs = np.nonzero(arr[..., 3] >= 128)
    lab = oklab(arr[ys, xs, :3].astype(np.float64))
    mat = classify_raw(lab)
    x0 = anchor - AX / k
    y0 = f.height - height / k
    X = np.floor((xs + 0.5 - x0) * k).astype(int)
    Y = np.floor((ys + 0.5 - y0) * k).astype(int)
    ok = (X >= 0) & (X < CW) & (Y >= 0) & (Y < height)
    X, Y, mat, lab = X[ok], Y[ok], mat[ok], lab[ok]
    NM = len(MATERIALS)
    cnt = np.zeros((height, CW, NM)); np.add.at(cnt, (Y, X, mat), 1)
    lsum = np.zeros((height, CW, NM, 3)); np.add.at(lsum, (Y, X, mat), lab)
    cover = cnt.sum(-1) * k * k
    prio = np.array([PRIORITY[m] for m in MATERIALS])
    win = np.argmax(cnt * prio, -1)
    yy, xx = np.mgrid[0:height, 0:CW]
    n = cnt[yy, xx, win]
    mean = lsum[yy, xx, win] / np.maximum(n, 1)[..., None]
    win[cover < 0.5] = -1
    return win, mean


def ramps_from_raw(rows):
    """Tonleiter je Material: k-means (Oklab) über alle Rohpixel dieses Materials, hell nach dunkel sortiert."""
    labs = []
    for frames, _, _, _ in rows:
        for f in frames:
            arr = np.asarray(f)
            ys, xs = np.nonzero(arr[..., 3] >= 200)
            labs.append(arr[ys, xs, :3].astype(np.float64))
    px = np.concatenate(labs)
    mat = classify_raw(oklab(px))
    pal, pmat = [], []
    for mi, m in enumerate(MATERIALS):
        sel = px[mat == mi]
        rng = np.random.default_rng(mi)
        if len(sel) > 40000:
            sel = sel[rng.choice(len(sel), 40000, replace=False)]
        tones = kmeans(sel, RAMPS[m], iters=20, seed=10 + mi)
        tones = tones[np.argsort(-oklab(tones)[:, 0])]
        pal.extend(tones); pmat.extend([mi] * len(tones))
    return np.array(pal), np.array(pmat)


def nb3(arr, y, x):
    H, W = arr.shape
    return arr[max(0, y - 1):min(H, y + 2), max(0, x - 1):min(W, x + 2)].ravel()


def tidy(idx, pal, mat, y_from=13, iters=2):
    """Pixel-Nacharbeit unterhalb des Gesichts (ab Zeile y_from):
    1. Krümel: Ein Pixel, dessen Material in der 3x3-Nachbarschaft höchstens zweimal vorkommt, übernimmt das
       Material, das mindestens 5 Nachbarn haben (mit dessen häufigstem Farbwert).
    2. Tonwerte: innerhalb von Weste, Schal und Fell gewinnt der häufigste Farbwert der gleichen Fläche
       (Mehrheit >= 5), damit Flächen 2-3 feste Töne behalten statt zu rauschen."""
    H, W = idx.shape
    flat = {MATERIALS.index(m) for m in ('gruen', 'rot', 'fell')}
    for _ in range(iters):
        src = idx.copy()
        m = np.where(src >= 0, mat[np.maximum(src, 0)], -1)
        for y in range(y_from, H):
            for x in range(W):
                c = src[y, x]
                if c < 0:
                    continue
                nm = nb3(m, y, x); nc = nb3(src, y, x)
                ok = nm >= 0
                nm, nc = nm[ok], nc[ok]
                mine = (nm == m[y, x]).sum()
                u, cnt = np.unique(nm, return_counts=True)
                if mine <= 2 and cnt.max() >= 5:
                    win = u[np.argmax(cnt)]
                    vals, vc = np.unique(nc[nm == win], return_counts=True)
                    idx[y, x] = vals[np.argmax(vc)]
                    continue
                if m[y, x] in flat:
                    same = nc[nm == m[y, x]]
                    vals, vc = np.unique(same, return_counts=True)
                    if vc.max() >= 5 and vals[np.argmax(vc)] != c:
                        idx[y, x] = vals[np.argmax(vc)]
    return idx


def redraw_parcel(idx, pal, mat):
    """Paket unter dem Arm als klare Form: Packpapier in einem Ton, Schnur als dunkles Kreuz, dunkle Unterkante.
    Fläche = größte zusammenhängende Paket-Fläche (mit hellen Schnurpixeln darin) in der unteren Hälfte."""
    H, W = idx.shape
    P, Hl = MATERIALS.index('paket'), MATERIALS.index('hell')
    m = np.where(idx >= 0, mat[np.maximum(idx, 0)], -1)
    core = (m == P)
    core[: H // 2 - 2] = False
    if not core.any():
        return idx
    # größte 4-Komponente
    lbl = np.zeros_like(idx); n = 0; best, bsize = 0, 0
    for y, x in zip(*np.nonzero(core)):
        if lbl[y, x]:
            continue
        n += 1; stack = [(y, x)]; lbl[y, x] = n; size = 0
        while stack:
            cy, cx = stack.pop(); size += 1
            for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                yy, xx = cy + dy, cx + dx
                if 0 <= yy < H and 0 <= xx < W and core[yy, xx] and not lbl[yy, xx]:
                    lbl[yy, xx] = n; stack.append((yy, xx))
        if size > bsize:
            best, bsize = n, size
    ys, xs = np.nonzero(lbl == best)
    y0, y1, x0, x1 = ys.min(), ys.max(), xs.min(), xs.max()
    area = np.zeros_like(core)
    area[y0:y1 + 1, x0:x1 + 1] = (m[y0:y1 + 1, x0:x1 + 1] == P) | (m[y0:y1 + 1, x0:x1 + 1] == Hl)
    lab = oklab(pal)
    paper = int(np.argmax(np.where(mat == P, 1, 0) * 10 + lab[:, 2]))           # sattester Paket-Ton
    br = [i for i in range(len(pal)) if mat[i] == MATERIALS.index('braun')]
    string = min(br, key=lambda i: lab[i, 0])                                     # dunkles Braun
    shade = max(br, key=lambda i: lab[i, 0])                                      # helleres Braun
    idx[area] = paper
    cx, cy = (x0 + x1 + 1) // 2, (y0 + y1) // 2
    col = area[:, cx]; idx[col, cx] = string
    row = area[cy, :]; idx[cy, row] = string
    idx[y1, area[y1]] = shade
    return idx


# Beinkorrektur je (Reihe, Bild): Zeilen ab LEG_ROW werden um dx nach vorn (Blickrichtung) geschoben, die Zeile
# darüber um die Hälfte. Im KI-Bild "Aufwärts" (Laufbild 3) steht das Standbein ca. 3 px zu weit hinten; ohne
# Korrektur rutscht der Standfuß beim Gehen oder der Körper ruckt.
LEG_ROW = 34
LEG_SHIFT = {(0, 3): 2}
# Beine beim Stehen/Sprechen bewegen sich nicht: alle Stehbilder bekommen die Beinzeilen aus diesem Bild
STAND_LEGS_FROM = 3
# Sprech- und Blinzelbilder wie bei den Vorbildern aus Teilen: Körper aus Bild STAND_BASE, vom jeweiligen Bild nur
# das Gesichtsfeld (Mund, Auge) und der Gestik-Arm (Umriss-Unterschiede in der vorderen Hälfte, 2 px erweitert).
# Die übrigen, verstreuten Unterschiede der KI-Bilder würden den Körper beim Sprechen flimmern lassen.
STAND_BASE = 0
FACE_BOX = (2, 13, 16)      # Zeilen 2..12, ab Spalte 16 (Schnauze zeigt nach rechts)
ARM_FROM_X = 16             # Gestik nur vorn (rechts der Körpermitte)


def add_outline(idx, dark):
    """Opake Randpixel (Nachbar transparent) bekommen die dunkelste Farbe."""
    pad = np.pad(idx, 1, constant_values=-1)
    edge = (idx >= 0) & ((pad[:-2, 1:-1] < 0) | (pad[2:, 1:-1] < 0) | (pad[1:-1, :-2] < 0) | (pad[1:-1, 2:] < 0))
    idx[edge] = dark
    return idx


def composite(base, frame, dark):
    H, W = base.shape
    keep = np.zeros((H, W), bool)
    y0, y1, x0 = FACE_BOX
    keep[y0:y1, x0:] = True
    sil = (base >= 0) != (frame >= 0)
    sil[:, :ARM_FROM_X] = False
    sil[:y1] = False
    sil[LEG_ROW:] = False
    grown = sil.copy()
    for _ in range(2):
        pad = np.pad(grown, 1)
        grown = grown | pad[:-2, 1:-1] | pad[2:, 1:-1] | pad[1:-1, :-2] | pad[1:-1, 2:]
    keep |= grown
    out = base.copy()
    out[keep] = frame[keep]
    return add_outline(out, dark)


def shift_rows(idx, y0, dx):
    out = idx.copy()
    out[y0:] = -1
    if dx >= 0:
        out[y0:, dx:] = idx[y0:, :idx.shape[1] - dx]
    else:
        out[y0:, :dx] = idx[y0:, -dx:]
    return out


def build(height, ncol=None, outline=True, clean=True):
    """Gibt je Reihe gleich große Zellen (Index-Arrays, -1 = transparent), die Palette, die Zellmaße
    (Breite, Höhe, Ankerspalte) und das Material je Palettenfarbe zurück.
    ncol wird nicht mehr gebraucht (Farbzahl = Summe der Tonleitern, 16)."""
    geo = geometry(height)
    pal, mat = ramps_from_raw(geo)
    plab = oklab(pal)
    dark = int(np.argmin(plab[:, 0]))
    out_rows, cells = [], []
    for ri, (frames, anc, k, cell) in enumerate(geo):
        out = []
        for fi, (f, a) in enumerate(zip(frames, anc)):
            win, mean = material_cells(f, a, k, cell)
            idx = np.full(win.shape, -1)
            for mi in range(len(MATERIALS)):
                sel = win == mi
                if not sel.any():
                    continue
                cand = np.flatnonzero(mat == mi)
                d = ((mean[sel][:, None, :] - plab[cand][None]) ** 2).sum(-1)
                idx[sel] = cand[np.argmin(d, 1)]
            if clean:
                idx = tidy(idx, pal, mat)
                idx = redraw_parcel(idx, pal, mat)
            dx = LEG_SHIFT.get((ri, fi), 0)
            if dx:
                idx = shift_rows(shift_rows(idx, LEG_ROW - 1, dx // 2), LEG_ROW, dx - dx // 2)
            if outline:
                idx = add_outline(idx, dark)
            out.append(idx)
        if ri == 1 and STAND_LEGS_FROM is not None:
            for fi in range(len(out)):
                out[fi][LEG_ROW:] = out[STAND_LEGS_FROM][LEG_ROW:]
            out = [out[fi] if fi == STAND_BASE else composite(out[STAND_BASE], out[fi], dark) for fi in range(len(out))]
        out_rows.append(out)
        cells.append(cell)
    return out_rows, pal, cells, mat


def compose(rows, pal, zoom=6, bgcol=(58, 46, 92)):
    tiles = []
    for r in rows:
        Hh = max(f.shape[0] for f in r)
        row = []
        for f in r:
            rgba = np.zeros(f.shape + (4,), np.uint8)
            rgba[f >= 0, :3] = pal[f[f >= 0]]; rgba[f >= 0, 3] = 255
            rgba = np.pad(rgba, ((Hh - f.shape[0] + 2, 2), (2, 2), (0, 0)))
            row.append(rgba)
        tiles.append(np.concatenate(row, 1))
    Wm = max(t.shape[1] for t in tiles)
    sheet = np.concatenate([np.pad(t, ((0, 0), (0, Wm - t.shape[1]), (0, 0))) for t in tiles], 0)
    bg = Image.new('RGBA', (sheet.shape[1], sheet.shape[0]), bgcol + (255,))
    bg.alpha_composite(Image.fromarray(sheet))
    return bg.resize((bg.width * zoom, bg.height * zoom), Image.NEAREST)


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('--height', type=int, default=40)
    ap.add_argument('--preview')
    ap.add_argument('--no-outline', action='store_true')
    a = ap.parse_args()
    rows, pal, cells, _ = build(a.height, outline=not a.no_outline)
    print([[f.shape for f in r] for r in rows], cells)
    if a.preview:
        compose(rows, pal).save(a.preview)
