#!/usr/bin/env python3
"""KI-Bilder auf das Bildformat der Parser-Adventures bringen (160×168 Doppelpixel, 16 EGA-Farben).

Zwei Eingaben, einzeln oder zusammen nutzbar (Aufträge in assets/image_jobs.json):
  Farbbild    (bg_flat.png)  flache Farbflächen; Farben werden über Gruppen (k-means in Oklab) den 16 EGA-Farben
                             zugeordnet, nicht Pixel für Pixel: so bleibt eine Fläche einfarbig, auch wenn das Modell
                             leicht schattiert, und blasse Dämmerungstöne landen nicht alle bei Grau.
  Strichvorlage (bg_lines.png) schwarze Linien auf Weiß, vom Farbbild abgepaust (Referenz im Auftrag). Liefert die
                             Flächengrenzen wie die Vorzeichnung, die in den Vorbildern Linie für Linie
                             nachgezogen wurde.
Zusammen: jede von Linien umschlossene Fläche bekommt die Mehrheitsfarbe des Farbbilds (wenn sie eindeutig ist),
die Linien selbst gehen in eine der angrenzenden Farben auf oder bleiben als dunklere Detaillinie stehen.
Oder (detail_from_lines): Flächen bleiben wie im Farbbild, die Strichvorlage zeigt nur, wo dünne Details liegen,
die die Mehrheit je Zielpixel verschluckt hätte.

Nur Bibliothek; Aufruf über scripts/process_raw.py. Einstellungen (scripts/ai_settings.json) siehe dort.
"""
import pathlib, sys

import numpy as np
from PIL import Image, ImageDraw

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(ROOT / "tools"))
from agipic import EGA_RGB, W, H  # noqa: E402
from snap_ai_bg import clean  # noqa: E402
from sprites import oklab  # noqa: E402

EGA_LAB = oklab(EGA_RGB.astype(np.float32))
EGA_NAMES = ["Schwarz", "Dunkelblau", "Dunkelgrün", "Dunkelcyan", "Dunkelrot", "Dunkelmagenta", "Braun",
             "Hellgrau", "Dunkelgrau", "Hellblau", "Hellgrün", "Hellcyan", "Hellrot", "Hellmagenta", "Gelb", "Weiß"]
# Farbe für Detaillinien innerhalb einer Fläche (Fugen, Planken, Wellen): helle Flächen bekommen eine dunklere,
# dunkle eine hellere Linie – wie im Handbild (Hellgrau -> Dunkelgrau, Dunkelblau -> Hellblau, Rot -> Schwarz)
DETAIL = {0: 8, 1: 9, 2: 10, 3: 11, 4: 0, 5: 13, 6: 0, 7: 8, 8: 0, 9: 1, 10: 2, 11: 3, 12: 4, 13: 5, 14: 6, 15: 7}
ACHROMATIC = [0, 8, 7, 15]
WORK = (960, 504)          # Arbeitsraster: 6×3 Stimmen je Zielpixel


# ------------------------------------------------------------------ Ausschnitt

def crop_band(im, top=None):
    """Ausschnitt mit dem Seitenverhältnis der Bildfläche (320:168), volle Breite.
    top: Anteil der Bildhöhe, an dem der Ausschnitt beginnt (None = mittig). Gibt (Bild, top_anteil) zurück."""
    sw = im.width
    sh = round(sw * H / (2 * W))
    if sh > im.height:                        # sehr breites Bild: dann volle Höhe, Breite beschneiden
        sh = im.height
        sw2 = round(sh * 2 * W / H)
        x0 = (im.width - sw2) // 2
        return im.crop((x0, 0, x0 + sw2, sh)), 0.0
    y0 = (im.height - sh) / 2 if top is None else top * im.height
    y0 = int(max(0, min(im.height - sh, y0)))
    return im.crop((0, y0, sw, y0 + sh)), y0 / im.height


# ------------------------------------------------------------------ Farbbild -> EGA

def kmeans(x, k, seed=7, iters=16, sample=40000):
    rng = np.random.RandomState(seed)
    pts = x[rng.choice(len(x), min(sample, len(x)), replace=False)]
    cent = [pts[rng.randint(len(pts))]]
    d2 = ((pts - cent[0]) ** 2).sum(1)
    for _ in range(1, k):                     # k-means++: weit entfernte Farben (Lampe, Sterne) bekommen eigene Gruppen
        c = pts[rng.choice(len(pts), p=d2 / d2.sum())] if d2.sum() > 0 else pts[rng.randint(len(pts))]
        cent.append(c)
        d2 = np.minimum(d2, ((pts - c) ** 2).sum(1))
    cent = np.array(cent)
    for _ in range(iters):
        lab = ((pts[:, None] - cent[None]) ** 2).sum(-1).argmin(1)
        for j in range(k):
            m = lab == j
            if m.any():
                cent[j] = pts[m].mean(0)
    full = np.concatenate([((x[i:i + 65536, None] - cent[None]) ** 2).sum(-1).argmin(1)
                           for i in range(0, len(x), 65536)])
    return cent, full


def normalise(lab_pts, all_lab):
    """Helligkeit auf den vollen Umfang strecken (höchstens 1,5-fach) und blasse Bilder kräftiger machen
    (Buntheit so, dass das 90. Perzentil etwa die Buntheit der EGA-Farben erreicht, Faktor 1–2,2)."""
    L = all_lab[:, 0]
    lo, hi = np.percentile(L, 1), np.percentile(L, 99)
    scale = min(1.5, 1.0 / max(1e-3, hi - lo))
    mid_src = (lo + hi) / 2
    # Mitte bleibt, solange der gestreckte Umfang in 0..1 passt (eine Dämmerung bleibt dunkel)
    mid_dst = float(np.clip(mid_src, (hi - lo) * scale / 2, 1 - (hi - lo) * scale / 2))
    C = np.hypot(all_lab[:, 1], all_lab[:, 2])
    gain = float(np.clip(0.16 / max(1e-3, np.percentile(C, 90)), 1.0, 2.2))
    out = lab_pts.copy()
    out[:, 0] = np.clip((lab_pts[:, 0] - mid_src) * scale + mid_dst, 0, 1)
    out[:, 1:] *= gain
    return out, {"light_scale": round(float(scale), 3), "chroma_gain": round(gain, 3)}


def map_to_ega(norm, grey_chroma=0.04):
    """Gruppenfarbe -> EGA. Fast unbunte Gruppen (Buntheit < grey_chroma) nur auf Schwarz/Grau/Weiß, nach
    Helligkeit; bunte Gruppen nur auf die 12 bunten Farben, Farbton doppelt gewichtet (sonst landen blasses Braun
    und ein pastellfarbener Dämmerungshimmel bei Grau, bläuliches Grau bei Dunkelcyan)."""
    out = np.zeros(len(norm), np.int64)
    chromatic = [i for i in range(16) if i not in ACHROMATIC]
    for i, c in enumerate(norm):
        if np.hypot(c[1], c[2]) < grey_chroma:
            out[i] = ACHROMATIC[int(np.abs(EGA_LAB[ACHROMATIC, 0] - c[0]).argmin())]
        else:
            e = EGA_LAB[chromatic]
            d = (e[:, 0] - c[0]) ** 2 + 2.0 * ((e[:, 1:] - c[1:]) ** 2).sum(-1)
            out[i] = chromatic[int(d.argmin())]
    return out


def colour_to_index(im, settings):
    """Farbbild (schon zugeschnitten) -> 160×168-Indexbild. Rückgabe (idx, info) mit Gruppen und Zuordnung."""
    work = np.asarray(im.convert("RGB").resize(WORK, Image.BOX)).astype(np.float32)
    lab = oklab(work).reshape(-1, 3)
    k = int(settings.get("clusters", 20))
    cent, lab_of = kmeans(lab, k)
    norm, nin = normalise(cent, lab)
    mapping = map_to_ega(norm, float(settings.get("grey_chroma", 0.04)))
    rgb_c = work.reshape(-1, 3)
    means = np.array([rgb_c[lab_of == j].mean(0) if (lab_of == j).any() else np.full(3, -999.0) for j in range(k)])
    manual = set()
    # Handzuordnung: {"Gruppe": EGA-Index} oder {"#rrggbb": EGA-Index}. Die Gruppennummern hängen von Ausschnitt
    # und Gruppenzahl ab; "#rrggbb" trifft die Gruppe mit der nächsten Mittelfarbe und bleibt deshalb gültig.
    for key, v in (settings.get("cluster_map") or {}).items():
        if str(key).startswith("#"):
            rgb = np.array([int(key[i:i + 2], 16) for i in (1, 3, 5)], np.float32)
            j = int(((means - rgb) ** 2).sum(1).argmin())
        else:
            j = int(key)
        mapping[j] = int(v)
        manual.add(j)
    ega_work = mapping[lab_of].reshape(WORK[1], WORK[0])
    votes = cell_votes(ega_work)
    idx = votes.argmax(-1).astype(np.uint8)
    idx = clean(idx, int(settings.get("min_area", 3)))
    share = np.bincount(lab_of, minlength=k) / len(lab_of)
    groups = []
    for j in range(k):
        mean = means[j] if share[j] > 0 else np.zeros(3)
        groups.append({"group": j, "rgb": "%02x%02x%02x" % tuple(int(v) for v in mean), "share": round(float(share[j]), 4),
                       "ega": int(mapping[j]), "ega_name": EGA_NAMES[int(mapping[j])], "manual": j in manual})
    return idx, {"groups": groups, **nin, "posterized": cent_to_rgb(lab_of, rgb_c, k).reshape(WORK[1], WORK[0], 3),
                 "ega_work": ega_work, "votes": votes}


def cell_votes(ega_work):
    """Stimmen je Zielpixel: wie viele der 6×3 Arbeitspixel welche EGA-Farbe haben (H×W×16)."""
    fx, fy = WORK[0] // W, WORK[1] // H
    votes = np.zeros((H, W, 16), np.int32)
    for dy in range(fy):
        for dx in range(fx):
            sub = ega_work[dy::fy, dx::fx][:H, :W]
            np.add.at(votes, (np.arange(H)[:, None], np.arange(W)[None], sub), 1)
    return votes


def cent_to_rgb(lab_of, rgb, k):
    means = np.zeros((k, 3), np.uint8)
    for j in range(k):
        m = lab_of == j
        if m.any():
            means[j] = rgb[m].mean(0)
    return means[lab_of]


def nearest_index(im, settings):
    """Einfacher Weg für Bilder, die schon in EGA-Farben vorliegen: jedes Pixel zur nächsten EGA-Farbe, Mehrheit
    je Zielpixel (wie snap_ai_bg.py)."""
    work = np.asarray(im.convert("RGB").resize(WORK, Image.BOX)).astype(np.float32)
    lab = oklab(work)
    e = ((lab[..., None, :] - EGA_LAB[None, None]) ** 2).sum(-1).argmin(-1)
    fx, fy = WORK[0] // W, WORK[1] // H
    votes = np.zeros((H, W, 16), np.int32)
    for dy in range(fy):
        for dx in range(fx):
            np.add.at(votes, (np.arange(H)[:, None], np.arange(W)[None], e[dy::fy, dx::fx][:H, :W]), 1)
    return clean(votes.argmax(-1).astype(np.uint8), int(settings.get("min_area", 3)))


def ega_distance(im):
    """Mittlerer Abstand (Oklab) der Bildfarben zur nächsten EGA-Farbe: klein = Modell hat EGA-Farben getroffen."""
    work = np.asarray(im.convert("RGB").resize((320, 168), Image.BOX)).astype(np.float32)
    lab = oklab(work).reshape(-1, 3)
    d = np.sqrt(((lab[:, None] - EGA_LAB[None]) ** 2).sum(-1).min(1))
    return float(np.median(d))


# ------------------------------------------------------------------ Strichvorlage -> Linienraster

def otsu(gray):
    hist = np.bincount(gray.ravel(), minlength=256).astype(np.float64)
    p = hist / hist.sum()
    omega = np.cumsum(p)
    mu = np.cumsum(p * np.arange(256))
    with np.errstate(divide="ignore", invalid="ignore"):
        sb = (mu[-1] * omega - mu) ** 2 / (omega * (1 - omega))
    return int(np.nanargmax(sb))


def thin(mask):
    """Zhang-Suen-Verdünnung auf 1 Pixel breite, 8-zusammenhängende Linien (sperren 4er-Flutfüllungen ab)."""
    m = np.pad(mask.astype(np.uint8), 1)
    while True:
        changed = False
        for step in (0, 1):
            P = [m[1:-1, 1:-1], m[:-2, 1:-1], m[:-2, 2:], m[1:-1, 2:], m[2:, 2:], m[2:, 1:-1], m[2:, :-2],
                 m[1:-1, :-2], m[:-2, :-2]]
            p1, p2, p3, p4, p5, p6, p7, p8, p9 = P
            nb = p2 + p3 + p4 + p5 + p6 + p7 + p8 + p9
            seq = [p2, p3, p4, p5, p6, p7, p8, p9, p2]
            trans = sum(((seq[i] == 0) & (seq[i + 1] == 1)).astype(np.uint8) for i in range(8))
            if step == 0:
                c = (p2 * p4 * p6 == 0) & (p4 * p6 * p8 == 0)
            else:
                c = (p2 * p4 * p8 == 0) & (p2 * p6 * p8 == 0)
            rm = (p1 == 1) & (nb >= 2) & (nb <= 6) & (trans == 1) & c
            if rm.any():
                m[1:-1, 1:-1][rm] = 0
                changed = True
        if not changed:
            return m[1:-1, 1:-1].astype(bool)


def lines_to_mask(im, settings):
    """Strichvorlage (schon zugeschnitten) -> Linienraster 160×168 (bool), verdünnt, kleine Lücken geschlossen."""
    g = np.asarray(im.convert("L"))
    thr = int(np.clip(otsu(g), 64, 192)) if settings.get("ink_threshold") is None else int(settings["ink_threshold"])
    ink = (g < thr).astype(np.float32)
    cov = np.asarray(Image.fromarray((ink * 255).astype(np.uint8)).resize((W, H), Image.BOX)) / 255.0
    mask = cov >= float(settings.get("ink_coverage", 0.18))
    if int(settings.get("close_gaps", 1)):
        # Lücken von einem Pixel schließen: Pixel mit Linien auf beiden gegenüberliegenden Seiten
        p = np.pad(mask, 1)
        bridge = ((p[1:-1, :-2] & p[1:-1, 2:]) | (p[:-2, 1:-1] & p[2:, 1:-1]) |
                  (p[:-2, :-2] & p[2:, 2:]) | (p[:-2, 2:] & p[2:, :-2]))
        mask = mask | bridge
    return thin(mask), {"ink_threshold": thr, "ink_share": round(float(ink.mean()), 4)}


def label4(free):
    """4-zusammenhängende Flächen der freien (nicht-Linien-)Pixel. -1 = Linie."""
    lab = -np.ones(free.shape, np.int32)
    n = 0
    for y in range(H):
        for x in range(W):
            if not free[y, x] or lab[y, x] >= 0:
                continue
            stack = [(x, y)]
            lab[y, x] = n
            while stack:
                cx, cy = stack.pop()
                for nx, ny in ((cx - 1, cy), (cx + 1, cy), (cx, cy - 1), (cx, cy + 1)):
                    if 0 <= nx < W and 0 <= ny < H and free[ny, nx] and lab[ny, nx] < 0:
                        lab[ny, nx] = n
                        stack.append((nx, ny))
            n += 1
    return lab, n


def alignment(lines, idx):
    """Wie gut die Strichvorlage zum Farbbild passt: Anteil der Linienpixel mit einer Farbgrenze des Farbbilds im
    Abstand von höchstens einem Pixel (1,0 = jede Linie liegt auf einer Farbkante)."""
    e = np.zeros((H, W), bool)
    e[:, 1:] |= idx[:, 1:] != idx[:, :-1]
    e[:, :-1] |= idx[:, 1:] != idx[:, :-1]
    e[1:] |= idx[1:] != idx[:-1]
    e[:-1] |= idx[1:] != idx[:-1]
    p = np.pad(e, 1)
    near = np.zeros_like(e)
    for dy in (-1, 0, 1):
        for dx in (-1, 0, 1):
            near |= p[1 + dy:H + 1 + dy, 1 + dx:W + 1 + dx]
    n = int(lines.sum())
    return float((near & lines).sum() / n) if n else 0.0


def combine(idx, lines, settings, region_colors=()):
    """Linienraster + Farben -> Indexbild.
    idx: Indexbild aus dem Farbbild oder None (dann nur region_colors: [[x, y, ega], ...]).
    Jede Fläche bekommt die Mehrheitsfarbe, wenn sie mindestens `region_majority` ausmacht, sonst bleiben die
    Farben des Farbbilds stehen. Linienpixel (line_style auto): zwischen verschiedenfarbigen Flächen die Farbe des
    Farbbilds an dieser Stelle, wenn sie zu einer der Flächen gehört, sonst die der größeren Fläche (keine
    schwarzen Umrisse, flache Flächen wie in den Vorbildern); trennt die Linie gleichfarbige Flächen oder endet frei
    (Fugen, Planken, Wellen), wird sie Detaillinie (DETAIL)."""
    lab, n = label4(~lines)
    out = np.full((H, W), 15, np.uint8) if idx is None else idx.copy()
    areas = np.bincount(lab[lab >= 0], minlength=n)
    region_col = np.full(n, -1, np.int32)
    if idx is not None:
        thr = float(settings.get("region_majority", 0.6))
        for r in range(n):
            m = lab == r
            cnt = np.bincount(idx[m], minlength=16)
            c = int(cnt.argmax())
            if cnt[c] >= thr * m.sum():
                out[m] = c
                region_col[r] = c
    for x, y, c in region_colors:
        r = lab[int(y), int(x)]
        if r >= 0:
            out[lab == r] = int(c)
            region_col[r] = int(c)
    style = settings.get("line_style", "auto")
    ys, xs = np.nonzero(lines)
    for y, x in zip(ys, xs):
        nbr = {}
        for nx, ny in ((x - 1, y), (x + 1, y), (x, y - 1), (x, y + 1), (x - 1, y - 1), (x + 1, y + 1),
                       (x - 1, y + 1), (x + 1, y - 1)):
            if 0 <= nx < W and 0 <= ny < H and lab[ny, nx] >= 0:
                r = int(lab[ny, nx])
                nbr[r] = int(out[ny, nx])
        if not nbr:
            continue
        cols = set(nbr.values())
        larger = nbr[max(nbr, key=lambda r: areas[r])]
        if style == "black":
            out[y, x] = 0
        elif len(cols) == 1:
            c = cols.pop()
            out[y, x] = c if style == "absorb" else DETAIL[c]
        elif style == "absorb" or idx is None:
            out[y, x] = larger
        else:
            out[y, x] = idx[y, x] if int(idx[y, x]) in cols else larger
    unset = [int(r) for r in range(n) if region_col[r] < 0 and idx is None]
    return clean(out, int(settings.get("min_area", 3))), {"regions": int(n), "regions_without_colour": len(unset)}


def detail_from_lines(idx, votes, lines, settings):
    """Strichvorlage als Hinweis auf dünne Details (Fugen, Masten, Fensterkreuze, Sterne), ohne Flächen neu zu
    füllen: Die Mehrheit je Zielpixel verliert alles, was schmaler als ein Doppelpixel ist (eine 3 px breite Fuge
    deckt nur ein Drittel eines 9,6 px breiten Zielpixels). Wo die Strichvorlage eine Linie hat, wird hier die
    stärkste Minderheitsfarbe des Farbbilds gesetzt, wenn sie mindestens `detail_theta` des Zielpixels deckt und
    dunkler ist als die Mehrheit (auf Schwarz und Dunkelblau auch heller: Sterne, Glitzer). Weil die Vorlage ein
    eigenes Bild ist und um ein Pixel danebenliegen kann, wird auch das Nachbarpixel quer zur Linie geprüft
    (`detail_search`). Einzelne gesetzte Pixel ohne gleichfarbigen 8er-Nachbarn werden zurückgenommen (Krümel),
    außer helle Punkte auf Schwarz/Dunkelblau (Sterne). Rückgabe (Indexbild, Bericht)."""
    theta = float(settings.get("detail_theta", 0.25))
    search = int(settings.get("detail_search", 1))
    darker_only = bool(settings.get("detail_darker", True))
    share = votes / max(1, int(votes[0, 0].sum()))
    L = EGA_LAB[:, 0]
    out = idx.copy()
    det = np.zeros((H, W), bool)
    offs = [(0, 0), (0, -1), (0, 1), (-1, 0), (1, 0)] if search else [(0, 0)]
    for y, x in zip(*np.nonzero(lines)):
        best = None
        for dx, dy in offs:
            yy, xx = y + dy, x + dx
            if not (0 <= yy < H and 0 <= xx < W) or det[yy, xx]:
                continue
            m = int(idx[yy, xx])
            v = share[yy, xx].copy()
            v[m] = 0
            if darker_only and m not in (0, 1):
                v = np.where(L < L[m] - 0.05, v, 0)
            c = int(v.argmax())
            # das Pixel auf der Linie selbst hat leichten Vorrang vor dem Nachbarn
            score = v[c] + (0.05 if (dx, dy) == (0, 0) else 0.0)
            if v[c] >= theta and (best is None or score > best[0]):
                best = (score, yy, xx, c)
        if best:
            _, yy, xx, c = best
            out[yy, xx] = c
            det[yy, xx] = True
    set_px = int(det.sum())
    undone = 0
    for y, x in zip(*np.nonzero(det)):
        c = out[y, x]
        same = sum(1 for dy in (-1, 0, 1) for dx in (-1, 0, 1)
                   if (dy or dx) and 0 <= y + dy < H and 0 <= x + dx < W and out[y + dy, x + dx] == c)
        if same == 0 and not (idx[y, x] in (0, 1) and c in (7, 15)):
            out[y, x] = idx[y, x]
            undone += 1
    return out, {"detail_pixels": set_px - undone, "detail_undone": undone, "detail_theta": theta}


# ------------------------------------------------------------------ Ansichten

def ega_rgb(idx, scale=1):
    rgb = np.repeat(EGA_RGB[idx], 2, axis=1)
    im = Image.fromarray(rgb)
    return im.resize((im.width * scale, im.height * scale), Image.NEAREST) if scale > 1 else im


def cluster_sheet(crop, info, path):
    """Ansicht der Farbzuordnung: Ausschnitt, Gruppen (Mittelfarbe), EGA-Fassung, Liste Gruppe -> EGA."""
    w, h = 640, 336
    a = crop.convert("RGB").resize((w, h), Image.BOX)
    b = Image.fromarray(info["posterized"].astype(np.uint8)).resize((w, h), Image.NEAREST)
    c = Image.fromarray(EGA_RGB[info["ega_work"]]).resize((w, h), Image.NEAREST)
    rows = sorted(info["groups"], key=lambda g: -g["share"])
    sheet = Image.new("RGB", (w + 330, max(3 * h + 20, 22 * len(rows) + 40)), (24, 24, 24))
    for i, im in enumerate((a, b, c)):
        sheet.paste(im, (0, i * (h + 10)))
    d = ImageDraw.Draw(sheet)
    d.text((w + 10, 6), "Gruppe  Anteil  Mittelfarbe -> EGA   (gruen = Handzuordnung)", fill=(230, 230, 230))
    for i, g in enumerate(rows):
        y = 26 + 22 * i
        d.rectangle((w + 10, y, w + 40, y + 16), fill="#" + g["rgb"])
        d.rectangle((w + 60, y, w + 90, y + 16), fill=tuple(int(v) for v in EGA_RGB[g["ega"]]))
        d.text((w + 100, y + 3), f"{g['group']:2d}  {g['share'] * 100:5.1f} %  -> {g['ega']:2d} {g['ega_name']}",
               fill=(120, 230, 120) if g["manual"] else (230, 230, 230))
    sheet.save(path)
