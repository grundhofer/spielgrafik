#!/usr/bin/env python3
"""Dachs-Kurier als Palettensprite: shared/badger/walk_painted.png (6 gemalte Laufbilder, nur gelesen) wird
materialtreu auf 48 px Höhe verkleinert und in den Sprite-Bereich der Szenenpalette gelegt (Einträge 12..28).
Die Figur hängt damit an derselben Überblendung Abend -> Nacht -> Regen wie der Hintergrund.

    .venv/bin/python styles/farbzyklus/scripts/build_badger.py [--preview DIR]

Verfahren wie in styles/vga-adventure/scripts/build_badger.py (dort entwickelt, hier angepasst und kopiert):
Rohpixel nach Material (Schal, Weste/Mütze, Paket, Hell, Leder, Fell, Kontur) einteilen, je Zielpixel gewinnt
das Material mit den meisten Rohpixeln, Ton aus der Tonleiter des Materials; alle Bilder auf einem gemeinsamen
Raster, dessen Ursprung am Kopf hängt; danach Krümel entfernen und 1-px-Kontur.

Ausgabe: demo/art/badger.png (RGB: R = Palettenindex, G = Deckkraft 0/255; keine Maske im Alphakanal),
demo/art/badger.json (Zellen, Fußpunkte, Vorschub), Sprite-Einträge in demo/art/palette.json.
"""
import argparse, json, pathlib, sys
import numpy as np
from PIL import Image

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from fzcommon import oklab, kmeans_vec, hexs  # noqa: E402

STYLE = HERE.parent
ROOT = STYLE.parent.parent
RAW = ROOT / 'shared/badger/walk_painted.png'
ART = STYLE / 'demo/art'
HEIGHT = 48
SPRITE0 = 12                     # erster Sprite-Eintrag der Palette

MATERIALS = ('rot', 'gruen', 'paket', 'hell', 'braun', 'fell', 'dunkel')
RAMPS = {'rot': 3, 'gruen': 3, 'paket': 2, 'hell': 3, 'braun': 2, 'fell': 3, 'dunkel': 1}
PRIORITY = {'rot': 1.0, 'gruen': 1.0, 'paket': 1.1, 'hell': 1.05, 'braun': 1.0, 'fell': 1.0, 'dunkel': 1.35}


def frames():
    im = Image.open(RAW).convert('RGBA')
    a = np.asarray(im)
    op = a[..., 3] >= 128
    cols = op.any(0)
    out, x = [], 0
    W = im.width
    while x < W:
        if not cols[x]:
            x += 1; continue
        s = x
        while x < W and cols[x]:
            x += 1
        out.append((s, x))
    out = [(s, e) for s, e in out if e - s > 60]
    res = []
    for s, e in out:
        ys = np.flatnonzero(op[:, s:e].any(1))
        res.append(im.crop((s, ys[0], e, ys[-1] + 1)))
    return res, [(s, e) for s, e in out]


def classify(lab):
    L, a, b = lab[..., 0], lab[..., 1], lab[..., 2]
    M = {m: i for i, m in enumerate(MATERIALS)}
    m = np.full(L.shape, M['fell'])
    m[L >= 0.62] = M['hell']
    m[(b > 0.07) & (L > 0.5)] = M['paket']
    m[(a >= 0.03) & (b >= 0.04) & (L < 0.55) & (L >= 0.22)] = M['braun']
    m[(a < -0.012) & (L >= 0.2)] = M['gruen']
    red = (a > 0.07) & (a > 1.2 * b)
    m[red] = M['rot']
    m[(L < 0.2) & ~red] = M['dunkel']
    return m


def head_cx(alpha, frac=0.25):
    top = alpha[: int(alpha.shape[0] * frac)]
    return float(np.nonzero(top)[1].mean())


def ramps(fr):
    px = np.concatenate([np.asarray(f)[np.asarray(f)[..., 3] >= 220][:, :3] for f in fr]).astype(np.float64)
    lab = oklab(px)
    mat = classify(lab)
    pal, pmat = [], []
    rng = np.random.default_rng(4)
    for mi, m in enumerate(MATERIALS):
        sel = lab[mat == mi]
        if len(sel) > 30000:
            sel = sel[rng.choice(len(sel), 30000, replace=False)]
        cent, lbl = kmeans_vec(sel, RAMPS[m], iters=20, seed=10 + mi)
        cent = cent[np.argsort(-cent[:, 0])]
        pal.extend(cent); pmat.extend([mi] * len(cent))
    return np.array(pal), np.array(pmat)




def reduce(f, anchor, k, cell, plab, pmat):
    CW, Hc, AX = cell
    arr = np.asarray(f)
    ys, xs = np.nonzero(arr[..., 3] >= 128)
    lab = oklab(arr[ys, xs, :3].astype(np.float64))
    mat = classify(lab)
    x0 = anchor - AX / k
    y0 = f.height - Hc / k
    X = np.floor((xs + 0.5 - x0) * k).astype(int)
    Y = np.floor((ys + 0.5 - y0) * k).astype(int)
    ok = (X >= 0) & (X < CW) & (Y >= 0) & (Y < Hc)
    X, Y, mat, lab = X[ok], Y[ok], mat[ok], lab[ok]
    NM = len(MATERIALS)
    cnt = np.zeros((Hc, CW, NM)); np.add.at(cnt, (Y, X, mat), 1)
    lsum = np.zeros((Hc, CW, NM, 3)); np.add.at(lsum, (Y, X, mat), lab)
    cover = cnt.sum(-1) * k * k
    prio = np.array([PRIORITY[m] for m in MATERIALS])
    win = np.argmax(cnt * prio, -1)
    yy, xx = np.mgrid[0:Hc, 0:CW]
    n = cnt[yy, xx, win]
    mean = lsum[yy, xx, win] / np.maximum(n, 1)[..., None]
    idx = np.full((Hc, CW), -1)
    for mi in range(NM):
        sel = (win == mi) & (cover >= 0.5)
        if not sel.any():
            continue
        cand = np.flatnonzero(pmat == mi)
        d = ((mean[sel][:, None, :] - plab[cand][None]) ** 2).sum(-1)
        idx[sel] = cand[np.argmin(d, 1)]
    return idx


def tidy(idx, pmat, y_from=14):
    """Krümel: Pixel, dessen Material in 3x3 höchstens zweimal vorkommt, übernimmt das Mehrheitsmaterial (>= 5)."""
    H, W = idx.shape
    for _ in range(2):
        src = idx.copy()
        m = np.where(src >= 0, pmat[np.maximum(src, 0)], -1)
        for y in range(y_from, H):
            for x in range(W):
                if src[y, x] < 0:
                    continue
                y0, y1, x0, x1 = max(0, y - 1), min(H, y + 2), max(0, x - 1), min(W, x + 2)
                nm, nc = m[y0:y1, x0:x1].ravel(), src[y0:y1, x0:x1].ravel()
                ok = nm >= 0
                nm, nc = nm[ok], nc[ok]
                mine = (nm == m[y, x]).sum()
                u, c = np.unique(nm, return_counts=True)
                if mine <= 2 and c.max() >= 5:
                    w = u[np.argmax(c)]
                    vals, vc = np.unique(nc[nm == w], return_counts=True)
                    idx[y, x] = vals[np.argmax(vc)]
    return idx


def outline(idx, dark):
    pad = np.pad(idx, 1, constant_values=-1)
    edge = (idx >= 0) & ((pad[:-2, 1:-1] < 0) | (pad[2:, 1:-1] < 0) | (pad[1:-1, :-2] < 0) | (pad[1:-1, 2:] < 0))
    out = idx.copy()
    out[edge] = dark
    return out


def feet(idx, rows=2):
    """Spalten der opaken Pixel in den untersten Zeilen (Fußsohlen) als Läufe."""
    H = idx.shape[0]
    res = []
    for y in range(H - rows, H):
        xs = np.flatnonzero(idx[y] >= 0)
        runs, s, p = [], None, None
        for x in xs:
            if s is None:
                s = p = x
            elif x == p + 1:
                p = x
            else:
                runs.append((int(s), int(p))); s = p = x
        if s is not None:
            runs.append((int(s), int(p)))
        res.append(runs)
    return res


def build():
    fr, spans = frames()
    fh = max(f.height for f in fr)
    k = HEIGHT / fh
    alphas = [np.asarray(f)[..., 3] >= 128 for f in fr]
    anc = [head_cx(a) for a in alphas]
    AX = int(np.ceil(max(a * k for a in anc))) + 1
    CW = AX + int(np.ceil(max((f.width - a) * k for f, a in zip(fr, anc)))) + 1
    cell = (CW, HEIGHT, AX)
    plab, pmat = ramps(fr)
    dark = int(np.flatnonzero(pmat == MATERIALS.index('dunkel'))[0])
    out = []
    for f, a in zip(fr, anc):
        idx = reduce(f, a, k, cell, plab, pmat)
        idx = tidy(idx, pmat)
        idx = outline(idx, dark)
        out.append(idx)
    return out, plab, pmat, cell, k, anc


def night_factors():
    """Kanalfaktoren (linear) Abend -> Nacht, gemessen im Laufbereich des Dachses (Pflaster vorn)."""
    def lin(c):
        c = c / 255.0
        return np.where(c <= 0.04045, c / 12.92, ((c + 0.055) / 1.055) ** 2.4)
    E = np.asarray(Image.open(STYLE / 'assets/raw/bg_evening.png').convert('RGB').resize((426, 284), Image.BOX))
    N = np.asarray(Image.open(STYLE / 'assets/raw/bg_night.png').convert('RGB').resize((426, 284), Image.BOX))
    sl = (slice(20 + 206, 20 + 236), slice(140, 300))
    e, n = lin(E[sl].reshape(-1, 3).astype(float)), lin(N[sl].reshape(-1, 3).astype(float))
    return np.median(n, 0) / np.maximum(np.median(e, 0), 1e-4)


CH = 'RSTGHIPQABCLMFXYK'          # Zeichen je Sprite-Farbe (Reihenfolge wie die Tonleitern in MATERIALS)
# Kopf von Hand nachgesetzt (Zeilen 0..12, ab Spalte 8): Die Verkleinerung verliert Auge und Augenstreif.
# Weiße Stirn unter dem Schirm, schwarzer Streif vom Ohr über das Auge (Glanzpunkt) zur Nase, weiße Wange.
HEAD = [
    "......KKKKKKKKK.........",   # 0  Mütze
    ".....KGGGGGGGGHK........",   # 1
    "....KGGGGGGGGHHHK.......",   # 2
    "...KHGGGGGGGHHHHHK......",   # 3
    "...KLLLLLLLPLLHHIIIIK...",   # 4  Band mit Messingknopf, Schirm nach vorn
    "..KFKXXAAAAAAAKKKKKK....",   # 5  Ohr, weiße Stirn
    "..KAFXXYYYYAAAAAAAK.....",   # 6
    "..KXFXYYYYYYAKYYYAAK....",   # 7  Auge: weißer Fleck (A) mit Pupille (K) nach vorn
    "..KXXXYYYYYYYYYYYYYKK...",   # 8  Streif bis zur Nase
    "...KXXXYYYAAAAAYYYYKKK..",   # 9
    "...KXXXAAAAAAAAAAAAAK...",   # 10 Wange
    "...KXXAAAAAAAAAAAAKK....",   # 11
    "...KXXAAAAAAAAAKKK......",   # 12
]
# Auge zu: Augenweiß und Pupille werden zum Lid in Fellfarbe (2 px). Das offene Auge ist dafür ein heller Fleck
# mit Pupille; vorher fehlte beim Blinzeln nur ein Glanzpixel, was nachts unsichtbar war.
BLINK = {(7, 20): 'X', (7, 21): 'X'}
# Paket unter dem Arm von Hand gesetzt (Rumpfzeilen 25..32, ab Spalte 15): Die Verkleinerung ergab nur einen
# hellbraunen Fleck, der in Hemd und Bauch überging. Papier hell (P) oben, Schattenseite (Q) unten, dunkle
# Schnur (M) als Kreuz, 1-px-Kontur (K).
PARCEL = [
    "KKKKKKKKK",
    "KPPPPMPPK",
    "KPPPPMPPK",
    "KMMMMMMMK",
    "KQQQQMQQK",
    "KQQQQMQQK",
    "KQQQQMQQK",
    "KKKKKKKKK",
]
PARCEL_AT = (25, 15)             # Zeile, Spalte der linken oberen Ecke im Rumpf
TORSO_FROM = 2                   # Rumpf aus dem Durchgangsbild (Beine unter dem Körper)
TORSO_ROWS = 38                  # Zeilen 0..37 Rumpf, darunter werden die Beine gezeichnet
TAIL_FROM = (2, 0, 3, 5)         # Schalenden aus diesen KI-Bildern (am Kopf ausgerichtet) -> Flattern im Wind
TAIL_BOX = (13, 26, 0, 9)        # Zeilen y0..y1, Spalten x0..x1 (exklusiv) des Schalendes
HIP_Y = 36
HIP_NEAR, HIP_FAR = 17, 12       # Hüftspalten (nahes Bein vorn, fernes Bein hinten)
STRIDE = 10                      # Abstand der Füße beim Aufsetzen (kurze Dachsbeine)
STEP_D = [2, 2, 1, 2, 2, 1]      # Vorschub je Bild (Summe = STRIDE), 6 Bilder je Schritt
# Fuß-Lage relativ zur Ankerspalte: Standfuß (fest am Boden) und Schwungfuß (x, Hub)
SWING = [(-5, 0), (-4, 2), (-1, 2), (2, 2), (4, 1), (5, 1)]
BOB = [0, 1, 0, 0, -1, 0]        # Rumpf 1 px tiefer im "Abfedern", 1 px höher im "Hoch"
GROUND = 48                      # Sohle in Zeile 48 der 49 Zeilen hohen Zelle (Zeile 0 = Platz für Auf und Ab)


def patch_head(idx, head=HEAD, x0=8, blink=False):
    idx = idx.copy()
    for y, row in enumerate(head):
        for i, c in enumerate(row):
            x = x0 + i
            if c == '.':
                idx[y, x] = -1
            else:
                idx[y, x] = CH.index(c)
    if blink:
        for (y, x), c in BLINK.items():
            idx[y, x] = CH.index(c)
    return idx


def patch_parcel(idx):
    """Paket einsetzen; übrige Paketpixel außerhalb werden Leder (links an der Tasche) oder Fell (darunter)."""
    idx = idx.copy()
    y0, x0 = PARCEL_AT
    ph, pw = len(PARCEL), len(PARCEL[0])
    paper = [CH.index('P'), CH.index('Q')]
    outside = np.isin(idx, paper)
    outside[:y0 - 5] = False                     # Kopf behalten (Messingknopf der Mütze ist ebenfalls P)
    outside[y0:y0 + ph, x0:x0 + pw] = False
    xs = np.arange(idx.shape[1])[None, :].repeat(idx.shape[0], 0)
    idx[outside & (xs < x0)] = CH.index('L')
    idx[outside & (xs >= x0)] = CH.index('X')
    for y, row in enumerate(PARCEL):
        for i, c in enumerate(row):
            if c != '.':
                idx[y0 + y, x0 + i] = CH.index(c)
    return idx


def tail_from(src, base):
    """Schalende (rote Pixel samt Kontur) im Bereich TAIL_BOX aus src in base übernehmen."""
    y0, y1, x0, x1 = TAIL_BOX
    red = {CH.index(c) for c in 'RSTK'}
    out = base.copy()
    reg = out[y0:y1, x0:x1]
    reg[np.isin(reg, list(red))] = -1
    sreg = src[y0:y1, x0:x1]
    m = np.isin(sreg, list(red))
    reg[m] = sreg[m]
    return out


def draw_leg(cv, hip_x, hip_y, foot_x, lift, near):
    """Kurzes, dickes Dachsbein: Trapez von der Hüfte (8 px) zum Knöchel (6 px), Licht vorn, Schatten hinten;
    Fuß als zwei Zeilen nach vorn (rechts), Kralle als heller Punkt."""
    body = CH.index('X') if near else CH.index('Y')
    light = CH.index('F') if near else CH.index('X')
    shade = CH.index('Y') if near else CH.index('K')
    sole = GROUND - lift
    ankle_y = sole - 2
    for y in range(hip_y, ankle_y + 1):
        t = (y - hip_y) / max(1, ankle_y - hip_y)
        cx = hip_x + (foot_x - 1 - hip_x) * t
        ww = int(round(8 - 2 * t))
        xa = int(round(cx - ww / 2)); xb = xa + ww - 1
        cv[y, xa:xb + 1] = body
        cv[y, xb] = light
        cv[y, xa] = shade
    fx = foot_x
    cv[sole - 1, fx - 4:fx + 3] = body
    cv[sole, fx - 4:fx + 4] = body
    cv[sole - 1, fx + 2] = light
    if near:
        cv[sole, fx + 3] = CH.index('C')
    return cv


def compose(torso, near_foot, far_foot, bob=0):
    """Ein Bild: Beine (fern, nah) hinter dem Rumpf, Rumpf um bob verschoben, dann Kontur."""
    Hc = GROUND + 1
    CWc = torso.shape[1]
    cv = np.full((Hc, CWc), -1)
    hip = HIP_Y + 1 + bob
    fx, fl = far_foot
    nx, nl = near_foot
    draw_leg(cv, HIP_FAR, hip, AXc + fx, fl, False)
    draw_leg(cv, HIP_NEAR, hip, AXc + nx, nl, True)
    t = torso[:TORSO_ROWS]
    y0 = 1 + bob
    sel = t >= 0
    cv[y0:y0 + TORSO_ROWS][sel] = t[sel]
    return outline(cv, CH.index('K'))


AXc = 19


def main():
    global AXc
    ap = argparse.ArgumentParser()
    ap.add_argument('--preview')
    a = ap.parse_args()
    out, plab, pmat, cell, k, anc = build()
    from fzcommon import oklab_to_rgb
    pal = oklab_to_rgb(plab)
    CW, _, AXc = cell
    print('Zelle', cell, 'Maßstab', round(k, 4), 'Farben', len(pal))
    torso = patch_parcel(patch_head(out[TORSO_FROM]))
    torso_blink = patch_parcel(patch_head(out[TORSO_FROM], blink=True))
    tails = [tail_from(out[f], torso) for f in TAIL_FROM]
    frames, names = [], []
    # Laufen: 2 Schritte x 6 Bilder. Schritt A: nahes Bein steht, fernes schwingt; Schritt B umgekehrt.
    for step in (0, 1):
        for kk in range(6):
            plant = STRIDE // 2 - sum(STEP_D[:kk])
            swing = SWING[kk]
            tail = tails[(step * 6 + kk) // 3 % len(tails)]
            if step == 0:
                f = compose(tail, (plant, 0), swing, BOB[kk])
            else:
                f = compose(tail, swing, (plant, 0), BOB[kk])
            frames.append(f); names.append(f'walk{step * 6 + kk}')
    # Anhalten aus dem Aufsetzbild von Schritt A (nahes Bein vorn bei +8): Körper rückt 3 und 2 px nach,
    # das hintere (ferne) Bein setzt neben das vordere.
    frames.append(compose(tails[0], (5 - 2, 0), (-1, 1), 0)); names.append('settle0')
    stand = (5 - 3, 0), (-3, 0)
    frames.append(compose(tails[0], *stand, 0)); names.append('stand0')
    for i in range(1, len(tails)):
        frames.append(compose(tails[i], *stand, 0)); names.append(f'stand{i}')
    frames.append(compose(tail_from(out[TAIL_FROM[0]], torso_blink), *stand, 0)); names.append('blink')
    Hc = GROUND + 1
    sheet = np.full((Hc, CW * len(frames)), -1)
    for i, f in enumerate(frames):
        sheet[:, i * CW:(i + 1) * CW] = f
    # Textur: R = Palettenindex, G = Deckkraft
    rgb = np.zeros(sheet.shape + (3,), np.uint8)
    op = sheet >= 0
    rgb[op, 0] = SPRITE0 + sheet[op]
    rgb[op, 1] = 255
    ART.mkdir(parents=True, exist_ok=True)
    Image.fromarray(rgb, 'RGB').save(ART / 'badger.png')
    (STYLE / 'assets/badger.png').write_bytes((ART / 'badger.png').read_bytes())
    # Fußlage je Bild (Spalten relativ zur Ankerspalte) für Godot und die Prüfung
    meta = {'cell': [CW, Hc], 'anchor_col': AXc, 'ground_row': GROUND, 'frames': names,
            'step_d': STEP_D, 'stop_d': [2, 1], 'stride': STRIDE, 'fps': 15}
    (ART / 'badger.json').write_text(json.dumps(meta, indent=1))
    # Paletten: Abend leicht in Dämmerlicht getönt, Nacht mit Kanalfaktoren aus dem Pflaster, Regen dunkler
    def lin(c):
        c = np.clip(c, 0, 255) / 255.0
        return np.where(c <= 0.04045, c / 12.92, ((c + 0.055) / 1.055) ** 2.4)
    def srgb(l):
        l = np.clip(l, 0, 1)
        return np.where(l <= 0.0031308, l * 12.92, 1.055 * l ** (1 / 2.4) - 0.055) * 255
    dusk = np.array([0.92, 0.80, 0.86])
    fac = night_factors()
    fac = np.clip(fac / fac.max() * 0.62, 0.05, 1.0)   # Verhältnis der Kanäle aus dem Bild, Helligkeit begrenzt
    pe = srgb(lin(pal) * dusk)
    # Nacht: kühles Restlicht (Kanalfaktoren aus dem Pflaster) plus etwas warmes Laternenlicht, damit die Figur
    # auf dem dunklen Kai lesbar bleibt
    pn = srgb(lin(pe) * fac + lin(pe) * np.array([0.10, 0.07, 0.03]))
    pr = np.clip(pn * 0.86 + np.array([4, 6, 12]), 0, 255)
    print('Nachtfaktoren', np.round(fac, 3))
    pj = ART / 'palette.json'
    meta_p = json.loads(pj.read_text())
    for name, P in (('evening', pe), ('night', pn), ('rain', pr)):
        for i, c in enumerate(P):
            meta_p['palettes'][name][SPRITE0 + i] = hexs(c)
    meta_p['sprite'] = {'start': SPRITE0, 'n': len(pal), 'chars': CH}
    pj.write_text(json.dumps(meta_p, indent=1))
    (STYLE / 'assets/palette.json').write_bytes(pj.read_bytes())
    if a.preview:
        pv = pathlib.Path(a.preview); pv.mkdir(parents=True, exist_ok=True)
        for name, P in (('e', pe), ('n', pn), ('o', pal)):
            img = np.zeros(sheet.shape + (3,), np.uint8) + np.array([70, 70, 90], np.uint8)
            img[op] = np.round(P[sheet[op]]).astype(np.uint8)
            Image.fromarray(img).resize((img.shape[1] * 4, img.shape[0] * 4), Image.NEAREST).save(pv / f'sheet_{name}.png')
        print(names)
    return frames


if __name__ == '__main__':
    main()
