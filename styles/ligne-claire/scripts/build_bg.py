#!/usr/bin/env python3
"""Hintergrund aufbereiten: mitgemalten Rauch entfernen, Rahmenlinie abschneiden, Farben flach einrasten,
Bildausschnitt für das Comic-Panel der Demo.

    .venv/bin/python styles/ligne-claire/scripts/build_bg.py [--no-flat]

Eingang: assets/raw/bg.png (agy, 1264x848). Ausgabe: assets/bg.png in Panelgröße (PANEL_W x PANEL_H) und
assets/bg_layout.json (Lage von Lampe, Laterne, Fenster, Schornstein usw. in Panelkoordinaten).

Flach einrasten: Tusche = dunkle, unbunte Pixel (Deckung aus der Helligkeit, Kantenglättung bleibt). Alle übrigen
Pixel bekommen die Farbe der häufigsten Palettenfarbe in ihrer 5x5-Umgebung (Palette = die häufigsten Farben des
Bildes nach Rundung auf 4 bit je Kanal, danach Farben mit Abstand < MERGE zur häufigeren zusammengelegt). So
verschwinden JPEG-Reste und leichte Verläufe, die Linien bleiben glatt.
Nacharbeit nach der ersten Prüfung: (a) Im Himmel werden die Grenzen zwischen den Himmelsfarben geglättet
(Gauß-Mehrheit statt 5x5), dadurch keine ausgefransten Säume unter den Wolken. (b) Die waagerechten Trennlinien der
Himmelsbänder sind im KI-Bild rotbraun und halb kantengeglättet; die halbe Zeile fiel durch den Tuschetest und wurde
zu braunen Flecken. Sie werden als gerade 2-px-Tuschelinien neu gezogen, nur dort, wo das KI-Bild eine Linie hat
und darüber und darunter Himmel liegt.
"""
import argparse, json, pathlib

import numpy as np
from PIL import Image, ImageFilter

HERE = pathlib.Path(__file__).resolve().parent.parent
PANEL_W, PANEL_H = 1248, 688          # Innenmaß des Panels (Bildschirm 1280x720, Rand 12 px, Rahmen 4 px)
TRIM = 4                              # gezeichnete Rahmenlinie des Bildmodells am Bildrand
TOP = 92                              # erste übernommene Zeile (Originalkoordinaten)
MERGE = 16.0                          # Palettenfarben näher als dieser RGB-Abstand werden zusammengelegt
SKY_Y1 = 490                          # Himmel: Zeilen bis knapp über der Horizontlinie (y = 492/493)

ap = argparse.ArgumentParser()
ap.add_argument("--src", default=str(HERE / "assets/raw/bg.png"))
ap.add_argument("--out", default=str(HERE / "assets/bg.png"))
ap.add_argument("--no-flat", action="store_true")
a = ap.parse_args()

AREA_DIST = 40.0                      # Flutfüllung je umrissener Fläche: Töne näher als das an der Hauptfarbe -> Hauptfarbe
BLOB_PX, BLOB_DIST = 400, 60.0        # kleine Flecken ohne Kontur (bis BLOB_PX Pixel, Farbabstand < BLOB_DIST) auflösen
BLOB_RING = 0.6                       # ... wenn mehr als dieser Anteil ihres Randes Fläche ist (Rest: Tusche); 0,4
                                      # getestet: fleckige Wolken, aufgehellte Keile zwischen Wanten -> verworfen
SKY_BLOB_PX, SKY_BLOB_DIST = 3000, 40.0   # im Himmel auch größere Tonflecken (Himmel = eine Fläche über alle Bänder)
SKY_SIGMA = 5                         # Glättung der Grenzen zwischen Himmelsfarben (Gauß, Pixel)


def label_runs(lab, same_class=True):
    """Zusammenhängende Flächen (4er-Nachbarschaft) über Zeilenläufe und Union-Find.

    lab: Nummer je Pixel, -1 = Tusche (gehört zu keiner Fläche). same_class=True: nur gleiche Nummern hängen
    zusammen; False: alle Nicht-Tusche-Pixel (= von Tuschelinien umschlossene Fläche). Gibt die Läufe
    (y, x0, x1, nummer) und je Lauf die Wurzel seiner Fläche zurück."""
    H_, W_ = lab.shape
    runs, parent = [], []

    def find(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    prev = []
    for y in range(H_):
        row = lab[y] if same_class else np.where(lab[y] >= 0, 0, -1)
        cut = np.flatnonzero(np.diff(row)) + 1
        starts = np.concatenate([[0], cut]); ends = np.concatenate([cut, [W_]])
        cur = []
        for x0, x1 in zip(starts.tolist(), ends.tolist()):
            if row[x0] < 0:
                continue
            i = len(runs)
            runs.append((y, x0, x1, int(lab[y, x0]))); parent.append(i); cur.append(i)
        j = 0
        for i in cur:
            _, x0, x1, c = runs[i]
            while j < len(prev) and runs[prev[j]][2] <= x0:
                j += 1
            k = j
            while k < len(prev) and runs[prev[k]][1] < x1:
                if not same_class or runs[prev[k]][3] == c:
                    ri, rk = find(i), find(prev[k])
                    if ri != rk:
                        parent[ri] = rk
                k += 1
        prev = cur
    return runs, np.array([find(i) for i in range(len(runs))])


def flood_areas(lab, cols):
    """Flutfüllung je Fläche: Innerhalb jeder von Tusche umschlossenen Fläche gehen alle Töne, die näher als
    AREA_DIST an der häufigsten Farbe dieser Fläche liegen, in diese Farbe über (weiche Schattierungen und Wischflecken
    des KI-Bildes, z. B. graublaue Flecken im Wasser vor den Booten). Deutlich andere Farben (Himmelsbänder, Lichter,
    Sterne) bleiben. Jeder umrissene Stein behält seine eigene Farbe."""
    runs, roots = label_runs(lab, same_class=False)
    lbl = np.full(lab.shape, -1, np.int64)
    for (y, x0, x1, _), r in zip(runs, roots.tolist()):
        lbl[y, x0:x1] = r
    m = lbl >= 0
    nc = len(cols)
    key = lbl[m] * nc + lab[m]
    u, cnt = np.unique(key, return_counts=True)
    area, cls = u // nc, u % nc
    order = np.lexsort((-cnt, area))            # je Fläche die häufigste Farbe zuerst
    first = np.unique(area[order], return_index=True)[1]
    maj = dict(zip(area[order][first].tolist(), cls[order][first].tolist()))
    dist = np.sqrt(((cols[:, None] - cols[None]) ** 2).sum(-1))
    out = lab.copy()
    M = np.vectorize(maj.get)(lbl[m])
    take = dist[lab[m], M] < AREA_DIST
    vals = out[m]
    vals[take] = M[take]
    out[m] = vals
    return out, int((take & (lab[m] != M)).sum())


def clean_blobs(lab, cols, max_px=BLOB_PX, max_dist=BLOB_DIST, y_max=None):
    """Kleine Flächen ohne eigene Kontur (Tonflecken, Säume) der umgebenden Fläche zuschlagen.

    Zusammenhängende Flächen gleicher Nummer mit höchstens BLOB_PX Pixeln, deren Rand zu mehr als BLOB_RING aus
    Flächenpixeln besteht (also nicht von einer Linie umschlossen) und deren Farbe näher als BLOB_DIST an der
    häufigsten Randfarbe liegt, bekommen diese Randfarbe. Ligne claire umreißt jede gewollte Form; kleine Flächen
    ohne Linie sind Reste des Einrastens. Sterne, Lichter und Fenster bleiben durch den Farbabstand bzw. ihre Kontur
    erhalten. y_max: nur Flecken, die ganz oberhalb dieser Zeile liegen."""
    H_, W_ = lab.shape
    runs, roots = label_runs(lab)
    rr = np.array([r[:3] for r in runs])
    size = np.bincount(roots, weights=rr[:, 2] - rr[:, 1], minlength=len(runs))
    out = lab.copy()
    by_root = {}
    for i in np.flatnonzero(size[roots] <= max_px):
        by_root.setdefault(int(roots[i]), []).append(int(i))
    n = 0
    for root, idxs in by_root.items():
        ys = [runs[i][0] for i in idxs]
        if y_max is not None and max(ys) >= y_max:
            continue
        y0, y1 = max(0, min(ys) - 1), min(H_, max(ys) + 2)
        x0 = max(0, min(runs[i][1] for i in idxs) - 1); x1 = min(W_, max(runs[i][2] for i in idxs) + 1)
        mk = np.zeros((y1 - y0, x1 - x0), bool)
        for i in idxs:
            y, a0, a1, _ = runs[i]
            mk[y - y0, a0 - x0:a1 - x0] = True
        dil = mk.copy()
        dil[1:] |= mk[:-1]; dil[:-1] |= mk[1:]; dil[:, 1:] |= mk[:, :-1]; dil[:, :-1] |= mk[:, 1:]
        ring = dil & ~mk
        rv = lab[y0:y1, x0:x1][ring]
        sv_ = rv[rv >= 0]
        if len(rv) == 0 or len(sv_) <= BLOB_RING * len(rv):
            continue
        tgt = np.bincount(sv_).argmax()
        c = runs[idxs[0]][3]
        if np.sqrt(((cols[c] - cols[tgt]) ** 2).sum()) >= max_dist:
            continue
        out[y0:y1, x0:x1][mk] = tgt
        n += 1
    return out, n


im = np.asarray(Image.open(a.src).convert("RGB")).astype(np.int32)
H, W = im.shape[:2]

# 1. Rauch über dem Schornstein entfernen. Der Himmel besteht aus waagerechten Farbbändern: jedes Pixel der
#    Rauchmaske übernimmt das Pixel derselben Zeile DX weiter rechts (dort ist nur Himmel mit Bandlinien).
x0, x1, y0, y1, DX = 8, 125, 178, 289, 150
L = (im * [0.299, 0.587, 0.114]).sum(2)
sat = im.max(2) - im.min(2)
reg = np.zeros((H, W), bool)
reg[y0:y1, x0:x1] = True
grey = reg & (sat < 28) & (L > 150)                      # Rauchfüllung (hellgrau, unbunt)
m = Image.fromarray((grey * 255).astype(np.uint8)).filter(ImageFilter.MaxFilter(11))
smoke = (np.asarray(m) > 0) & reg
# Rauchansatz direkt auf dem Kaminaufsatz: nur die grauen Pixel selbst (plus 1 px), der Aufsatz bleibt stehen.
base = np.zeros((H, W), bool)
base[284:300, 75:102] = True
gb = base & (sat < 28) & (L > 150)
gb = np.asarray(Image.fromarray((gb * 255).astype(np.uint8)).filter(ImageFilter.MaxFilter(3))) > 0
smoke |= gb & base
smoke[284:294, 75:102] = True                           # oberhalb der Aufsätze (Oberkante bei y = 295) alles ersetzen
yy, xx = np.nonzero(smoke)
im[yy, xx] = im[yy, xx + DX]

# 2. Flach einrasten
if not a.no_flat:
    L = (im * [0.299, 0.587, 0.114]).sum(2)
    sat = im.max(2) - im.min(2)
    ink = np.clip((118.0 - L) / 78.0, 0, 1) * (sat < 70)          # 1 = volle Tusche (L <= 40)
    q = (im // 16) * 16 + 8
    key = (q[..., 0] // 16) * 256 + (q[..., 1] // 16) * 16 + q[..., 2] // 16
    solid = ink < 0.02
    vals, cnt = np.unique(key[solid], return_counts=True)
    order = np.argsort(-cnt)
    keep = vals[order][np.cumsum(cnt[order]) / cnt.sum() < 0.995]
    # Palettenfarbe = Mittelwert der Originalpixel je Schlüssel (nicht die gerundete Farbe)
    pal = {}
    for k in keep:
        sel = solid & (key == k)
        pal[int(k)] = im[sel].mean(0)
    keys = np.array(list(pal))
    cols = np.array([pal[k] for k in keys])
    # Zusammenlegen: Eine flache Fläche mit JPEG-Rauschen fällt beim Runden oft auf zwei benachbarte Schlüssel
    # (Abstand 10-16); sonst wechseln sich zwei fast gleiche Töne fleckig ab (Wasser vor den Booten, Bootsinneres).
    # Reihenfolge = Häufigkeit, jede Farbe geht in die nächste schon behaltene, wenn sie näher als MERGE liegt.
    n_raw = len(cols)
    kept = []
    for i in range(len(cols)):
        d = [np.sqrt(((cols[i] - cols[j]) ** 2).sum()) for j in kept]
        if not d or min(d) >= MERGE:
            kept.append(i)
    cols = cols[kept]
    # nächste Palettenfarbe für jedes Pixel
    flat = im.reshape(-1, 3).astype(np.float32)
    idx = np.empty(len(flat), np.int32)
    for s in range(0, len(flat), 200000):
        d = ((flat[s:s + 200000, None] - cols[None]) ** 2).sum(-1)
        idx[s:s + 200000] = d.argmin(1)
    idx = idx.reshape(H, W)
    # Mehrheitsfilter (5x5) über die Palettennummern der Flächenpixel; Tuschepixel (auch teilweise gedeckte) erhalten
    # danach die Farbe eines Nachbarn, damit unter der geglätteten Linie keine abgedunkelte Mischfarbe liegt.
    if len(cols) >= 255:
        raise SystemExit(f"Palette zu groß: {len(cols)}")
    idx_img = Image.fromarray(np.where(solid, idx, 255).astype(np.uint8))
    voted = np.asarray(idx_img.filter(ImageFilter.ModeFilter(5))).astype(np.int32)
    fill_idx = np.where(solid, np.where(voted == 255, idx, voted), -1)
    fill_idx, nf_ = flood_areas(fill_idx, cols)
    print("Flutfüllung je Fläche:", nf_, "Pixel umgefärbt")
    for _ in range(2):                  # zweimal: Flecken in Flecken
        fill_idx, nb_ = clean_blobs(fill_idx, cols)
        print(f"Flecken ohne Kontur aufgelöst (bis {BLOB_PX} px, Abstand < {BLOB_DIST:g}):", nb_)
    # Im Himmel hängen alle Bänder über Lücken in den Linien zusammen; die Flutfüllung greift dort nicht. Größere
    # Tonflecken (z. B. die pfirsichfarbene Unterseite einer Wolke) über die Fleckenregel mit größerer Grenze.
    fill_idx, nb_ = clean_blobs(fill_idx, cols, SKY_BLOB_PX, SKY_BLOB_DIST, y_max=SKY_Y1)
    print(f"Himmel: Tonflecken bis {SKY_BLOB_PX} px aufgelöst:", nb_)
    # (a) Himmel: Grenzen zwischen den häufigen Himmelsfarben glätten (je Farbe Gauß-geglättete Maske, größte
    # gewinnt). Nur Pixel, die schon eine Himmelsfarbe haben, und nur unter diesen Farben: Masten, Turm, Möwen usw.
    # behalten ihre Farbe.
    sky = np.zeros((H, W), bool)
    sky[:SKY_Y1] = True
    sv, sc = np.unique(fill_idx[sky & solid], return_counts=True)
    sky_cls = sv[sc > 0.01 * sc.sum()]
    sel = sky & solid & np.isin(fill_idx, sky_cls)
    score = []
    for c in sky_cls:
        mk = Image.fromarray(((fill_idx == c) & sel).astype(np.uint8) * 255)
        score.append(np.asarray(mk.filter(ImageFilter.GaussianBlur(SKY_SIGMA)), np.float32))
    best = sky_cls[np.argmax(np.stack(score), 0)]
    changed = sel & (best != fill_idx)
    fill_idx[sel] = best[sel]
    print("Himmel:", len(sky_cls), "Himmelsfarben, geglättet:", int(changed.sum()), "Pixel")
    # (b) Waagerechte Bandlinien neu ziehen: Zeilen, in denen über 400 dunkle Pixel mit hellem Himmel 4 Zeilen
    # darüber und darunter liegen; je Linie die 2 Zeilen mit den meisten dunklen Pixeln.
    Lr = (im * [0.299, 0.587, 0.114]).sum(2)
    dark = Lr < 75
    up, dn = np.roll(Lr, 4, 0) > 120, np.roll(Lr, -4, 0) > 120
    hits = [y for y in range(8, SKY_Y1 + 4) if (dark[y] & up[y] & dn[y]).sum() > 400]
    groups = []
    for y in hits:
        if groups and y - groups[-1][-1] <= 2:
            groups[-1].append(y)
        else:
            groups.append([y])
    redrawn = 0
    for g in groups:
        ys = range(g[0] - 1, g[-1] + 2)
        a0 = max(ys, key=lambda y: (Lr[y] < 100).sum() + (Lr[y + 1] < 100).sum() if y + 1 <= g[-1] + 1 else 0)
        rows2 = [a0, a0 + 1]
        has = (Lr[rows2].min(0) < 100) & (Lr[a0 - 4] > 120) & (Lr[a0 + 5] > 120)
        # Lücken bis 2 px schließen (Rauschen), größere Lücken des KI-Bildes bleiben
        hs = has.copy()
        for k in (1, 2):
            hs |= np.roll(has, k) & np.roll(has, -(3 - k))
        has = hs
        for y in rows2:
            ink[y, has] = 1.0
        for y in (a0 - 1, a0 + 2):          # Halbtonzeilen daneben: reine Fläche
            ink[y, has] = 0.0
        redrawn += int(has.sum())
        print(f"Bandlinie y={a0}..{a0 + 1}: {int(has.sum())} px")
    print("Bandlinien neu gezogen:", len(groups), "Linien,", redrawn, "Spalten")
    for _ in range(12):
        todo = fill_idx < 0
        if not todo.any():
            break
        for dy, dx in ((0, 1), (1, 0), (0, -1), (-1, 0)):
            nb = np.roll(fill_idx, (dy, dx), (0, 1))
            take = (fill_idx < 0) & (nb >= 0)
            fill_idx[take] = nb[take]
    fill_idx[fill_idx < 0] = idx[fill_idx < 0]
    fill = cols[fill_idx]
    ink_rgb = np.array([20, 20, 22], np.float32)
    out = fill * (1 - ink[..., None]) + ink_rgb * ink[..., None]
    im = np.clip(out + 0.5, 0, 255).astype(np.int32)
    print("Palette:", n_raw, "->", len(cols), "Farben")

# 3. Rahmen abschneiden, Ausschnitt, auf Panelgröße skalieren
im = im[TRIM:H - TRIM, TRIM:W - TRIM]
s = PANEL_W / im.shape[1]
rows = round(PANEL_H / s)
top = TOP - TRIM
crop = im[top:top + rows]
img = Image.fromarray(crop.astype(np.uint8)).resize((PANEL_W, PANEL_H), Image.LANCZOS)
img.save(a.out, optimize=True)


def P(x, y):
    """Originalkoordinate (agy-Bild) -> Panelkoordinate."""
    return [round((x - TRIM) * s, 1), round((y - TRIM - top) * s, 1)]


layout = {
    "panel": [PANEL_W, PANEL_H], "scale": s, "src_rows": [TOP, TOP + rows],
    "lighthouse_lamp": P(1085, 241), "lantern": P(713, 447), "window": P(125, 494),
    "chimney": P(92, 292), "quay_edge_y": P(0, 700)[1],
}
(pathlib.Path(a.out).with_name("bg_layout.json")).write_text(json.dumps(layout, indent=1))
print("bg:", img.size, "Maßstab", round(s, 4), "Zeilen", TOP, "bis", TOP + rows, layout)
