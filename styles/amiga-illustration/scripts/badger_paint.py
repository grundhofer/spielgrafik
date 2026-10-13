"""Dachs-BOBs in der Malweise des Hafenbilds (statt flacher Farbflächen mit schwarzer Kontur).

Aus build_assets.build_badger aufgerufen (group_regs, paste_heads, paint_frame, stamp_heads). Eingabe sind die
materialtreu verkleinerten Blender-Bilder (badger_cells.py: Material je Zielpixel und Schattierung aus dem
EEVEE-Rendering). Schritte:

1. Kopf als festes Teil wie in klassischen Adventures: Der Kopf eines Referenzbilds (Seitenansicht: Stehen,
   Vorderansicht: Stehen frontal) bekommt ein von Hand gesetztes Gesicht (SIDE_FACE, FRONT_FACE) und ersetzt in jedem
   Bild derselben Ansicht den gerenderten Kopf, versetzt um die ganzzahlige Verschiebung, bei der die Mütze am besten
   passt (paste_heads). Nach dem Malen werden die Kopfpixel des Referenzbilds pixelgleich gestempelt (stamp_heads),
   sonst ändert das Dither-Raster den Kopf von Bild zu Bild. Seite: weiße Wange und Schnauze, schwarzer Augenstreifen,
   Nase 2x2, Schnauze 2 px kürzer als im Rendering (vorher grauer „Schnabel“). Vorn: zwei schwarze Streifen über die
   Augen, weiße Mitte, Nase (vorher waagrechte „Banditenmaske“). Zwischenbilder der Drehung behalten ihren Kopf.
2. Paket: dunkles Packpapier, helle Oberkante und Schnur (Kreuz) in Cremeweiß.
3. Töne: je Materialgruppe eine Tonleiter aus den festen Figurenregistern plus Registern des Bildes mit passendem
   Farbton (group_regs). Die Schattierung des Renderings wird verstärkt (CONTRAST) und um einen Lichtverlauf von
   links oben (Laterne, LIGHT_GRAD) ergänzt und wie im Hintergrund mit Bayer 4x4 über Paare benachbarter Töne
   gedithert (4 Mischstufen, Raster fest an der Zelle, damit das Muster mit der Figur wandert).
4. Selektive Kontur: nur rechts und unten (Schattenseite; Licht kommt laut Rendering von links oben) im dunkelsten Ton
   der eigenen Materialgruppe statt Schwarz; links eine Stufe heller als Kantenlicht, oben nichts.
Den Kontaktschatten zeichnet die Demo als eigenes Blitter-Objekt (demo/scripts/shadow.gd), Breite je Bild steht
in badger.json ("feet", feet_extent).
"""
import numpy as np

import badger_cells
from amiga import dither, lin_to_srgb, oklab

MAT = {n: i for i, n in enumerate(badger_cells.MATERIALS)}
HEAD_MATS = [MAT[n] for n in ("FurDark", "FurLight", "Cap", "Brass", "Eye", "Nose", "Satchel")]
SIDE_REF, FRONT_REF = 48, 83          # Idle seitlich (3,2 s), frontal stehend (5,53 s)

# Tonstufen: Material und Lage in der (nach Helligkeit sortierten) Tonleiter der Gruppe, 0 = dunkelster Ton
KEYS = {
    "k": ("Nose", 0.0),        # Nase: fast schwarz
    "d": ("FurDark", 0.0),     # schwarzer Gesichtsstreifen
    "D": ("FurDark", 0.67),    # Hinterkopf, Kehle (grau-schwarz)
    "l": ("FurLight", 1.0),    # weißes Fell
    "L": ("FurLight", 1.0),    # weißes Fell im Licht
    "g": ("FurLight", 0.5),    # weißes Fell im Schatten
    "E": ("FurLight", 1.0),    # Lichtpunkt im Auge (das Auge selbst liegt im schwarzen Streifen)
}
# Gesichter in Zielpixeln des Referenzbilds: (x0, y0, Zeilen). "?" = Pixel des Referenzbilds behalten,
# "." = leer (gekürzte Schnauze). Vorbild ist der gemalte Dachs der Nahaufnahme: schwarze Streifen über die Augen,
# weiße Mitte von der Nase bis unter die Mütze, weiße Wangen.
SIDE_FACE = (15, 18, [
    "?ggDddd",                                     # 18: Ohransatz weiß, Streifen beginnt unter der Mütze
    "gLll" "ddddd" "kd" "LLL" "..",                # 19: Streifen mit Auge, weiße Schnauze vor dem Schirm
    "gLlllll" "dddd" "LLL" "k" "..",               # 20: Streifen endet hinter der Schnauze
    "?g" "llllllllllll" "kk" "..",                 # 21: weiße Wange und Schnauze, Nase
    "?gg" "llllllll" "gg" ".....",                 # 22: Unterkiefer (Schnauze 2 px kürzer als im Rendering)
    "??????????" "ggg" ".....",                    # 23: Kinn neben dem Schal
])
FRONT_FACE = (14, 18, [
    "?L" "????????????" "l",                              # 18: Mütze
    "?" "L" "l" "d" "E" "d" "LLLL" "d" "E" "d" "l" "g",   # 19: Augen in zwei schwarzen Streifen
    "?" "L" "l" "ddd" "LLLL" "ddd" "ll" "g",              # 20: weiße Mitte
    "?" "L" "ll" "dd" "LLLL" "dd" "lll" "g",              # 21: Streifen enden über der Schnauze
    "?" "g" "lllll" "kk" "lllll" "g",                     # 22: Nase
])
CONTRAST = 1.5        # Helligkeitsabstand zum Mittel der Gruppe verstärken (das Rendering ist weich beleuchtet)
LIGHT_GRAD = 0.12     # Helligkeitszuwachs (Oklab L) von rechts unten nach links oben
SPREAD = 0.08         # Paar-Strafe beim Dithern (klein: die Tonleitern der Figur haben große Stufen)


def lab_to_srgb(lab):
    """Oklab -> sRGB (0..255)."""
    m2i = np.linalg.inv(np.array([[0.2104542553, 0.7936177850, -0.0040720468],
                                  [1.9779984951, -2.4285922050, 0.4505937099],
                                  [0.0259040371, 0.7827717662, -0.8086757660]]))
    m1i = np.linalg.inv(np.array([[0.4122214708, 0.5363325363, 0.0514459929],
                                  [0.2119034982, 0.6806995451, 0.1073969566],
                                  [0.0883024619, 0.2817188376, 0.6299787005]]))
    lin = (lab @ m2i.T) ** 3 @ m1i.T
    return lin_to_srgb(lin)


def group_of(groups):
    """Material -> Gruppe (Index in build_assets.BADGER_RAMPS)."""
    out = {}
    for g, (mats, _n) in enumerate(groups):
        for m in mats:
            out[MAT[m]] = g
    return out


def group_regs(pal, static, ramp_regs, groups, frames, extra=0.035, margin=0.06, hue=None):
    """Tonleiter je Gruppe: feste Figurenregister plus Bildregister mit ähnlichem Farbton (Abstand in a/b höchstens
    `extra` zum Mittel der Gruppe bzw. zum festen Farbton hue[Gruppe]) im Helligkeitsbereich der Gruppe
    (10.–97. Perzentil, +-margin). Sortiert nach Helligkeit; die Paar-Strafe beim Dithern lässt dann nur benachbarte
    Töne mischen."""
    lab = oklab(pal)
    out = {}
    for g, (mats, _n) in enumerate(groups):
        ks = [MAT[m] for m in mats]
        px = np.concatenate([f["rgb"][np.isin(f["mat"], ks)] for f in frames])
        pl = oklab(px)
        lo, hi = np.percentile(pl[:, 0], [10, 97])
        ab = np.array(hue[g]) if hue and g in hue else np.median(pl[:, 1:], 0)
        regs = set(ramp_regs.get(g, []))
        for r in static:
            if lo - margin <= lab[r, 0] <= hi + margin and np.hypot(*(lab[r, 1:] - ab)) <= extra:
                regs.add(r)
        if not regs:      # Gruppe ohne feste Töne und ohne passendes Bildregister: nächstes Register zum Mittel
            t = np.array([np.median(pl[:, 0]), *ab])
            regs.add(int(static[int(np.argmin(((lab[static] - t) ** 2).sum(-1)))]))
        out[g] = sorted(regs, key=lambda r: lab[r, 0])
    return out


def group_median_l(groups, frames):
    """Mittlere Helligkeit (Oklab L) je Gruppe über alle Bilder (Bezug für CONTRAST)."""
    out = {}
    for g, (mats, _n) in enumerate(groups):
        ks = [MAT[m] for m in mats]
        px = np.concatenate([f["rgb"][np.isin(f["mat"], ks)] for f in frames])
        out[g] = float(np.median(oklab(px)[:, 0]))
    return out


def _head(frame, view):
    """Kopf des Referenzbilds mit Gesicht: Material, Ton, feste Tonstufe (oder None) und Maske, Lage."""
    m = frame["mat"].copy()
    rgb = frame["rgb"].copy()
    fix = np.full(m.shape, None, dtype=object)
    sc = np.argwhere(m == MAT["Scarf"])
    top = int(sc[:, 0].min())
    x0, y0, rows = SIDE_FACE if view == "side" else FRONT_FACE
    for dy, row in enumerate(rows):
        for dx, ch in enumerate(row):
            y, x = y0 + dy, x0 + dx
            if ch == "?":
                continue
            if ch == ".":
                m[y, x] = -1
                continue
            mat, pos = KEYS[ch]
            m[y, x] = MAT[mat]
            fix[y, x] = (mat, pos)
    mask = ((m >= 0) & (np.arange(m.shape[0])[:, None] < top)) | (fix != None)        # noqa: E711
    return {"mat": m, "rgb": rgb, "fix": fix, "mask": mask, "cap": (m == MAT["Cap"]) & mask, "top": top,
            "front_pad": 3 if view == "side" else 1}


def _best_shift(ref_cap, cap, r=3):
    best, arg = -1e9, (0, 0)
    for dy in range(-2, 3):
        for dx in range(-r, r + 1):
            s = np.roll(np.roll(ref_cap, dy, 0), dx, 1)
            score = (s & cap).sum() - 0.5 * (s ^ cap).sum()
            if score > best:
                best, arg = score, (dy, dx)
    return arg


def view_of(fr):
    yaw = float(fr.get("yaw", 0.0))
    if yaw > -30:
        return "side"
    if yaw <= -60:
        return "front"
    return None


def paste_heads(frames):
    """Ersetzt in jedem Bild der Seiten- bzw. Vorderansicht den Kopf durch das feste Kopfteil. Gibt je Bild das
    Feld der festen Tonstufen (None = aus der Schattierung) und die Lage des Kopfteils (Ansicht, dy, dx, Maske)
    zurück; stamp_heads setzt nach dem Malen in alle Bilder dieselben Kopfpixel."""
    refs = {"side": _head(frames[SIDE_REF], "side"), "front": _head(frames[FRONT_REF], "front")}
    fixes, places = [], []
    for f in frames:
        view = view_of(f["meta"])
        fix = np.full(f["mat"].shape, None, dtype=object)
        if view is None:
            fixes.append(fix)
            places.append(None)
            continue
        ref = refs[view]
        m = f["mat"]
        sc = np.argwhere(m == MAT["Scarf"])
        top = int(sc[:, 0].min())
        cap = (m == MAT["Cap"]) & (np.arange(m.shape[0])[:, None] < top)
        dy, dx = _best_shift(ref["cap"], cap)
        mask = np.roll(np.roll(ref["mask"], dy, 0), dx, 1)
        ys, xs = np.nonzero(mask)
        # alten Kopf entfernen: Kopfmaterialien über dem Schal im Bereich des neuen Kopfs (+1 Spalte, +2 vorn
        # für die gekürzte Schnauze)
        rows = np.arange(m.shape[0])[:, None]
        cols = np.arange(m.shape[1])[None, :]
        box = ((rows >= ys.min()) & (rows < max(top, ys.max() + 1)) & (cols >= xs.min() - 1)
               & (cols <= xs.max() + ref["front_pad"]))
        old = box & np.isin(m, HEAD_MATS)
        m[old] = -1
        for key in ("mat", "rgb", "fix"):
            src = np.roll(np.roll(ref[key], dy, 0), dx, 1)
            dst = f[key] if key != "fix" else fix
            dst[mask] = src[mask]
        fixes.append(fix)
        places.append((view, dy, dx, mask))
    return fixes, places


def stamp_heads(idxs, places):
    """Kopfpixel des gemalten Referenzbilds in alle Bilder derselben Ansicht übernehmen (nur verschoben). Sonst
    ändert das Muster-Dithering mit der Verschiebung gegen das Raster der Zelle die Kopfpixel und der Kopf
    flimmert."""
    for view, ref in (("side", SIDE_REF), ("front", FRONT_REF)):
        if places[ref] is None:
            continue
        _v, rdy, rdx, rmask = places[ref]
        src = np.roll(np.roll(idxs[ref], -rdy, 0), -rdx, 1)
        for k, pl in enumerate(places):
            if pl is None or pl[0] != view:
                continue
            _v, dy, dx, mask = pl
            shifted = np.roll(np.roll(src, dy, 0), dx, 1)
            idxs[k][mask] = shifted[mask]


def parcel_marks(m):
    """Paket: Oberkante hell, Schnur als Kreuz (Spalte und Zeile in der Mitte der sichtbaren Fläche)."""
    p = m == MAT["Parcel"]
    edge = np.zeros_like(p)
    string = np.zeros_like(p)
    if p.sum() < 6:
        return edge, string
    pad = np.pad(p, 1)
    edge = p & ~pad[:-2, 1:-1]
    ys, xs = np.nonzero(p)
    cx, cy = int(round(np.median(xs))), int(round(np.median(ys)))
    string[:, cx] = p[:, cx]
    string[cy, :] = p[cy, :]
    string &= ~edge
    return edge, string


def paint_frame(f, fix, pal, regs, gof, boost, chroma, groups, med_l, outline=True):
    """Indexbild (Register, -1 = leer) eines Bildes."""
    m = f["mat"]
    op = m >= 0
    idx = np.full(m.shape, -1)
    # Licht der Laterne von links oben: Verlauf über die Figur (sonst bleiben große Flächen wie die Weste einfarbig)
    ys, xs = np.nonzero(op)
    yy, xx = np.mgrid[0:m.shape[0], 0:m.shape[1]]
    u = ((xs.max() - xx) / max(1, xs.max() - xs.min()) + (ys.max() - yy) / max(1, ys.max() - ys.min())) / 2
    grad = LIGHT_GRAD * (u - 0.5)
    for g, (mats, _n) in enumerate(groups):
        ks = [MAT[mm] for mm in mats]
        sel = np.isin(m, ks)
        if not sel.any():
            continue
        src = f["rgb"][sel]
        if mats in chroma:
            src = boost(src, chroma[mats])
        lab = oklab(src)
        lab[:, 0] = med_l[g] + (lab[:, 0] - med_l[g]) * CONTRAST + grad[sel]
        sub = np.zeros(m.shape + (3,))
        sub[sel] = lab_to_srgb(lab)
        d_idx = dither(sub, pal, levels=4, allowed=regs[g], spread=SPREAD)
        idx[sel] = d_idx[sel]
    # fast schwarzes Register (dunkelstes über reinem Schwarz) für Auge und Nase
    plab = oklab(pal)
    black = min((r for r in range(len(pal)) if 0.1 < plab[r, 0] < 0.25), key=lambda r: plab[r, 0], default=0)
    # feste Tonstufen (Gesicht)
    for (y, x) in zip(*np.nonzero(fix != None)):          # noqa: E711
        mat, pos = fix[y, x]
        r = regs[gof[MAT[mat]]]
        idx[y, x] = black if mat == "Nose" else r[int(round(pos * (len(r) - 1)))]
    # Auge und Nase außerhalb der festen Gesichter
    small = np.isin(m, [MAT["Eye"], MAT["Nose"]]) & (fix == None)        # noqa: E711
    idx[small] = black
    # Paket
    edge, string = parcel_marks(m)
    pr = regs[gof[MAT["Parcel"]]]
    body = m == MAT["Parcel"]
    idx[body & ~edge & ~string] = pr[0]               # Packpapier: dunkler Ton, damit Kante und Schnur stehen
    idx[edge] = pr[-1]
    idx[string] = regs[gof[MAT["FurLight"]]][-1]      # Schnur cremeweiß
    if outline:
        pad = np.pad(op, 1)
        right = op & ~pad[1:-1, 2:]
        down = op & ~pad[2:, 1:-1]
        left = op & ~pad[1:-1, :-2]
        free = fix == None                                                    # noqa: E711
        # Kantenlicht der Laterne (links): eine Stufe heller, nicht auf dem gemalten Gesicht
        for (y, x) in zip(*np.nonzero(left & ~right & ~down & free)):
            r = regs[gof[m[y, x]]]
            k = r.index(idx[y, x]) if idx[y, x] in r else 0
            idx[y, x] = r[min(len(r) - 1, k + 1)]
        # Kontur nur auf der Schattenseite (rechts, unten) im dunkelsten Ton der eigenen Gruppe
        for (y, x) in zip(*np.nonzero(right | down)):
            r = regs[gof[m[y, x]]]
            idx[y, x] = r[0]
    return idx


def feet_extent(m):
    """Spalten der Füße (unterste drei besetzte Zeilen) für den Kontaktschatten."""
    ys, _xs = np.nonzero(m >= 0)
    bot = ys.max()
    near = np.flatnonzero((m[max(0, bot - 2):bot + 1] >= 0).any(0))
    return [int(near.min()), int(near.max())]
