#!/usr/bin/env python3
"""Lage der animierten Teile und Prioritätsebene für ein automatisch umgewandeltes Bild (160×168, EGA-Indizes).

Die Demo braucht je Bild: Fußlinie des Dachses (walk_y), Laternenglas (Flackern), Leuchtfeuer (Blitz),
Schornstein (Rauch), Wasserfarbe und Glitzerstellen, Paketposition. Im Handbild stehen diese Werte von Hand in
scripts/pic_harbor.py; hier werden sie geschätzt und können in scripts/ai_settings.json -> "layout" überschrieben
werden. Jede Schätzung landet mit Grund im Bericht und als Markierung in <name>_layout.png.

Prioritätsebene wie in den Vorbildern: Gegenstände auf dem Kai (alles, was nicht Pflaster ist) bekommen das Band
ihrer Fußzeile; der Dachs (Band seiner Fußlinie) wird von Gegenständen mit höherem Band verdeckt.
"""
import pathlib, sys

import numpy as np
from PIL import Image, ImageDraw

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from agipic import W, H, band  # noqa: E402
from vectorize import chain, segments  # noqa: E402

START_X = 147          # wie main.gd
WALK_SPAN = 39         # Vorschub über 29 Laufbilder (2/1/1 …) – der Dachs hält bei start_x - 39
BADGER_H = 30
BADGER_W = 10


def shares(rows):
    v = rows.ravel()
    return np.bincount(v, minlength=16) / max(1, v.size)


def components(mask, conn8=True):
    lab = -np.ones(mask.shape, np.int32)
    comps = []
    nbs = [(-1, 0), (1, 0), (0, -1), (0, 1)] + ([(-1, -1), (1, 1), (-1, 1), (1, -1)] if conn8 else [])
    for y in range(mask.shape[0]):
        for x in range(mask.shape[1]):
            if not mask[y, x] or lab[y, x] >= 0:
                continue
            n = len(comps)
            pts = [(x, y)]
            lab[y, x] = n
            i = 0
            while i < len(pts):
                cx, cy = pts[i]
                i += 1
                for dx, dy in nbs:
                    nx, ny = cx + dx, cy + dy
                    if 0 <= nx < mask.shape[1] and 0 <= ny < mask.shape[0] and mask[ny, nx] and lab[ny, nx] < 0:
                        lab[ny, nx] = n
                        pts.append((nx, ny))
            comps.append(np.array(pts))
    return comps, lab


def find_quay(idx, floor):
    """Von unten nach oben: Kaikante = oberste Zeile mit mindestens 45 % Pflaster, bevor 4 Zeilen in Folge
    darunter bleiben (einzelne Zeilen mit Gegenständen werden übersprungen)."""
    fl = np.isin(idx, floor).mean(1)
    quay, miss = None, 0
    for y in range(H - 1, 40, -1):
        if fl[y] >= 0.45:
            quay, miss = y, 0
        else:
            miss += 1
            if miss >= 4:
                break
    return int(np.clip(quay if quay is not None else 118, 80, H - 20))


def ubiquitous(rows, bins=10):
    """Farben, die in mindestens 80 % der senkrechten Streifen mit ≥ 2 % vorkommen."""
    w = rows.shape[1] // bins
    cov = np.zeros(16)
    for b in range(bins):
        sh = shares(rows[:, b * w:(b + 1) * w])
        cov += sh >= 0.02
    return [int(c) for c in np.nonzero(cov >= 0.8 * bins)[0]]


def detect(idx, over=None):
    """Schätzt die Lage. over: Werte aus ai_settings.json -> layout (haben Vorrang). Rückgabe (layout, report)."""
    over = dict(over or {})
    rep = {}
    # Pflaster, erster Durchgang: Farben, die in den untersten 12 Zeilen mindestens 8 % ausmachen
    floor = [int(c) for c in np.nonzero(shares(idx[H - 12:]) >= 0.08)[0]]
    quay = find_quay(idx, floor)
    # zweiter Durchgang: Pflaster sind die Farben, die auf dem Kai überall vorkommen (Steine und Fugen), nicht die
    # Farben einzelner Gegenstände
    floor = ubiquitous(idx[quay:])
    quay = int(over.get("quay_top", find_quay(idx, floor)))
    rep["floor_colours"] = floor
    rep["quay_top"] = quay
    # Wasser: häufigste Nicht-Pflaster-Farbe in den 14 Zeilen über dem Kai
    sw = shares(idx[max(0, quay - 16):quay - 2])
    for c in floor:
        sw[c] = 0
    water = int(over.get("water", int(sw.argmax())))
    rep["water"] = water
    walk_y = int(over.get("walk_y", min(H - 3, quay + round(0.56 * (H - quay)))))
    rep["walk_y"] = walk_y
    start_x = int(over.get("start_x", START_X))
    stop_x = start_x - WALK_SPAN

    # Horizont: von der Kaikante aufwärts, solange die Wasserfarbe mindestens 15 % einer Zeile ausmacht
    hz, miss = quay, 0
    for y in range(quay - 1, 0, -1):
        if (idx[y] == water).mean() >= 0.15:
            hz, miss = y, 0
        else:
            miss += 1
            if miss >= 3:
                break
    rep["horizon"] = hz
    # Himmel: Farben, die oberhalb des Horizonts in mindestens 3 Zeilen die häufigste Farbe sind (Bänder)
    tops = [int(np.bincount(idx[y], minlength=16).argmax()) for y in range(0, max(1, hz))]
    sky = sorted({c for c in tops if tops.count(c) >= 3})
    rep["sky_colours"] = sky

    # Gelbe Flecken: Leuchtfeuer (oben rechts) und Laternenglas (unter dem Horizont, klein)
    yel_comps, _ = components(idx == 14, conn8=False)
    cands = []
    for pts in yel_comps:
        x0, y0 = pts.min(0)
        x1, y1 = pts.max(0)
        cands.append({"box": [int(x0), int(y0), int(x1), int(y1)], "area": len(pts),
                      "cx": (x0 + x1) / 2, "cy": (y0 + y1) / 2, "w": int(x1 - x0 + 1), "h": int(y1 - y0 + 1)})
    lamp = over.get("lamp")
    if lamp is None and "lamp" not in over:
        top = [c for c in cands if c["cx"] >= 96 and c["cy"] < min(quay - 30, hz - 15) and 2 <= c["area"] <= 60
               and c["w"] <= 10]
        if top:
            b = list(min(top, key=lambda c: c["cy"])["box"])
            for c in top:    # Scheiben, die eine Sprosse trennt, gehören zur selben Lampe
                x0, y0, x1, y1 = c["box"]
                if x0 <= b[2] + 2 and x1 >= b[0] - 2 and y0 <= b[3] + 2 and y1 >= b[1] - 2:
                    b = [min(b[0], x0), min(b[1], y0), max(b[2], x1), max(b[3], y1)]
            lamp = b
    rep["lamp"] = lamp
    lamp_origin = None
    if lamp is not None:
        lamp_origin = [(lamp[0] + lamp[2]) // 2 - 9, (lamp[1] + lamp[3]) // 2 - 3]   # wie im Handbild: [131, 15]
    lantern = over.get("lantern")
    if lantern is None and "lantern" not in over:
        low = [c for c in cands if c["cy"] >= quay - 40 and 2 <= c["area"] <= 40 and c["w"] <= 6 and c["h"] <= 10
               and c["box"] != lamp]
        lantern = min(low, key=lambda c: (c["area"], -c["cx"]))["box"] if low else None
    rep["lantern"] = lantern

    # Schornstein: höchster Punkt des Hauses links. Je Spalte von der Kaikante aufwärts, solange weder Himmel noch
    # Wasser kommt (Schwarz zählt nicht als Himmel: Umrisslinien); das Haus ist die Spalte, die am höchsten reicht.
    chimney = over.get("chimney_top")
    if chimney is None and "chimney_top" not in over:
        stop = (set(sky) | {water}) - {0}
        best = []
        for x in range(0, 72):
            y = quay - 1
            if int(idx[y, x]) in stop:
                continue
            while y > 0 and int(idx[y - 1, x]) not in stop:
                y -= 1
            if quay - y >= 12 and y >= 8:
                best.append((y, x))
        if best:
            ty = min(b[0] for b in best)
            xs = [b[1] for b in best if b[0] == ty]
            chimney = [int(np.median(xs)), ty - 1]
    rep["chimney_top"] = chimney

    # Glitzern: Stellen mit 3 Wasserpixeln nebeneinander, darüber und darunter ebenfalls Wasser
    glints = over.get("glints")
    if glints is None:
        rng = np.random.RandomState(1986)
        wm = idx == water
        ok = np.zeros_like(wm)
        ok[1:-1, :-2] = (wm[1:-1, :-2] & wm[1:-1, 1:-1] & wm[1:-1, 2:] & wm[:-2, 1:-1] & wm[2:, 1:-1])
        ok[:max(0, quay - 50)] = False
        ok[quay - 2:] = False
        ys, xs = np.nonzero(ok)
        glints = []
        if len(ys):
            # über die Breite verteilt: je Zehntel der Breite höchstens zwei Stellen
            order = rng.permutation(len(ys))
            used = {}
            for i in order:
                b = int(xs[i]) * 10 // W
                if used.get(b, 0) >= 2 or any(abs(int(xs[i]) - g[0]) < 6 and abs(int(ys[i]) - g[1]) < 4 for g in glints):
                    continue
                used[b] = used.get(b, 0) + 1
                glints.append([int(xs[i]), int(ys[i]), 3 if len(glints) % 2 == 0 else 2])
                if len(glints) >= 12:
                    break
    rep["glints"] = len(glints)

    # Möwe: knapp unter dem Horizont über dem Wasser (auf hellen Himmelsbändern ist sie weiß kaum zu sehen)
    gull_y = int(over.get("gull_y", min(quay - 24, hz + 8)))
    rep["gull_y"] = gull_y

    layout = {"walk_y": walk_y, "quay_edge": quay, "water": water, "glints": glints, "lamp": lamp, "gull_y": gull_y,
              "lamp_origin": lamp_origin, "lantern": lantern, "chimney_top": chimney, "start_x": start_x,
              "parcel_x": int(over.get("parcel_x", stop_x - 6))}
    return layout, rep


def priority(idx, layout, rep, over_objects=None):
    """Prioritätsebene: Gegenstände auf dem Kai mit dem Band ihrer Fußzeile. Spalten oberhalb des Kais werden bis
    4 Zeilen über die Kopfhöhe des Dachses mitgenommen, solange sie nicht Himmel oder Wasser sind (Laternenpfahl,
    Fassdeckel; Schwarz und Dunkelgrau zählen dabei zum Gegenstand).
    over_objects: [[x0, y0, x1, y1, band], ...] ersetzt die Schätzung. Rückgabe (pri, objekte)."""
    pri = np.full((H, W), 4, np.uint8)
    objs = []
    if over_objects is not None:
        for x0, y0, x1, y1, b in over_objects:
            pri[y0:y1 + 1, x0:x1 + 1] = b
            objs.append({"box": [x0, y0, x1, y1], "band": b, "area": int((x1 - x0 + 1) * (y1 - y0 + 1))})
        return pri, objs
    quay, walk_y = layout["quay_edge"], layout["walk_y"]
    floor = rep["floor_colours"]
    # Hintergrund beim Hochziehen über die Kaikante: nur Wasser und Himmel. Schwarz und Dunkelgrau gehören zum
    # Gegenstand (Umrisse, Fassdeckel, Pfahlkontur), auch wenn sie als oberstes Himmelsband oder als Pflasterfuge
    # vorkommen; sonst endet die Silhouette an der Kaikante. Auf dem Kai bleibt das Pflaster Hintergrund.
    bg_up = ({layout["water"]} | set(rep["sky_colours"])) - {0, 8}
    bg_quay = bg_up | set(floor)
    mask = ~np.isin(idx, floor)
    mask[:quay] = False
    comps, _ = components(mask, conn8=True)
    comps = [c for c in comps if len(c) >= 3]
    # Teile eines Gegenstands (Umriss, Deckel, Bauch eines Fasses) zusammenfassen: Rahmen liegen höchstens 1 px
    # auseinander (dazwischen z. B. ein Reifen in Pflasterfarbe).
    # Je Teil die Zeilenspanne und je Spalte der Gruppe die Spaltenspanne füllen (Pflasterfarben im Inneren, z. B.
    # ein grauer Deckel oder ein Reifen, gehören dazu; eine Lücke zwischen zwei Fässern bleibt offen).
    boxes = [(c[:, 0].min(), c[:, 1].min(), c[:, 0].max(), c[:, 1].max()) for c in comps]
    group = list(range(len(comps)))

    def root(i):
        while group[i] != i:
            group[i] = group[group[i]]
            i = group[i]
        return i
    # Nebeneinanderliegende Teile (ohne gemeinsame Spalte) nur, wenn sie auf demselben Band stehen: Poller und
    # Pfahlfuß mit 1 px Abstand behalten ihr eigenes Band.
    for i in range(len(comps)):
        for j in range(i + 1, len(comps)):
            a, c = boxes[i], boxes[j]
            if a[0] <= c[2] + 2 and c[0] <= a[2] + 2 and a[1] <= c[3] + 2 and c[1] <= a[3] + 2 and (
                    (a[0] <= c[2] and c[0] <= a[2]) or band(int(a[3])) == band(int(c[3]))):
                group[root(j)] = root(i)
    merged = {}
    for i, pts in enumerate(comps):
        m = merged.setdefault(root(i), np.zeros((H, W), bool))
        for y in np.unique(pts[:, 1]):
            xs = pts[pts[:, 1] == y][:, 0]
            m[y, xs.min():xs.max() + 1] = True
    for m in merged.values():
        for x in np.nonzero(m.any(0))[0]:
            ys = np.nonzero(m[:, x])[0]
            m[ys.min():ys.max() + 1, x] = True
    head = walk_y - BADGER_H - 4      # 4 Zeilen über der Mütze (in den Durchgangsbildern reicht sie bis walk_y - 30)
    for m in merged.values():
        if m.sum() < 6:
            continue
        pts = np.argwhere(m)[:, ::-1]
        bottom = int(pts[:, 1].max())
        b = band(bottom)
        # nach oben fortsetzen (nur in den Spalten des Gegenstands, nur Nicht-Hintergrund, bis über Kopfhöhe)
        for x in np.unique(pts[:, 0]):
            y = int(pts[pts[:, 0] == x][:, 1].min()) - 1
            while y >= max(0, head) and int(idx[y, x]) not in (bg_quay if y >= quay else bg_up):
                m[y, x] = True
                y -= 1
        if b <= 4:
            continue
        sel = m & (pri < b)
        pri[sel] = b
        ys, xs = np.nonzero(m)
        objs.append({"box": [int(xs.min()), int(ys.min()), int(xs.max()), int(ys.max())], "band": b,
                     "area": int(m.sum()), "front_of_badger": bool(b > band(walk_y))})
    return pri, objs


def priority_commands(pri):
    """Befehle für die Prioritätsebene (sichtbare Ebene aus): je Band Umriss als Linien, Inneres flutfüllen."""
    cmds = [["c", -1]]
    for b in sorted(int(v) for v in np.unique(pri) if v != 4):
        m = pri == b
        comps, _ = components(m, conn8=False)
        cmds.append(["p", b])
        for pts in comps:
            region = np.zeros((H, W), bool)
            region[pts[:, 1], pts[:, 0]] = True
            border, inner = set(), np.zeros((H, W), bool)
            for x, y in pts:
                edge = any(0 <= nx < W and 0 <= ny < H and not region[ny, nx]
                           for nx, ny in ((x - 1, y), (x + 1, y), (x, y - 1), (x, y + 1)))
                if edge:
                    border.add((int(x), int(y)))
                else:
                    inner[y, x] = True
            dots = []
            for poly in chain(segments(border)):
                if len(poly) == 2 and poly[0] == poly[1]:
                    dots += list(poly[0])
                else:
                    cmds.append(["l", [v for pt in poly for v in pt]])
            if dots:
                cmds.append(["s", dots])
            seeds = []
            icomps, _ = components(inner, conn8=False)
            for ip in icomps:
                seeds += [int(ip[0][0]), int(ip[0][1])]
            if seeds:
                cmds.append(["f", seeds])
    cmds.append(["p", -1])
    return cmds


def overlay(vis_rgb, layout, objs, path):
    """Ansicht zum Prüfen (×4): Kaikante, Fußlinie, Gegenstände mit Band, Lampe, Laterne, Schornstein, Glitzern,
    Dachs-Umriss an Start- und Haltepunkt."""
    s = 4
    im = vis_rgb.convert("RGB").resize((W * 2 * s, H * s), Image.NEAREST)
    d = ImageDraw.Draw(im)

    def box(b, col, label=""):
        x0, y0, x1, y1 = b
        d.rectangle((x0 * 2 * s, y0 * s, (x1 + 1) * 2 * s - 1, (y1 + 1) * s - 1), outline=col, width=2)
        if label:
            d.text((x0 * 2 * s + 2, y0 * s - 12), label, fill=col)

    d.line((0, layout["quay_edge"] * s, im.width, layout["quay_edge"] * s), fill=(0, 255, 255), width=1)
    d.line((0, layout["walk_y"] * s, im.width, layout["walk_y"] * s), fill=(255, 0, 255), width=1)
    d.text((4, layout["walk_y"] * s + 2), f"walk_y {layout['walk_y']} (Band {band(layout['walk_y'])})", fill=(255, 0, 255))
    d.text((4, layout["quay_edge"] * s - 12), f"quay_edge {layout['quay_edge']}", fill=(0, 255, 255))
    for o in objs:
        box(o["box"], (255, 64, 64) if o.get("front_of_badger") else (255, 200, 0), f"P{o['band']}")
    if layout.get("lamp"):
        box(layout["lamp"], (255, 255, 255), "lamp")
    if layout.get("lantern"):
        box(layout["lantern"], (255, 255, 255), "lantern")
    if layout.get("chimney_top"):
        cx, cy = layout["chimney_top"]
        box([cx - 1, cy - 2, cx + 1, cy], (255, 255, 255), "chimney")
    for gx, gy, gl in layout.get("glints") or []:
        box([gx, gy, gx + gl - 1, gy], (128, 255, 128))
    for x in (layout["start_x"], layout["start_x"] - WALK_SPAN):
        box([x, layout["walk_y"] - BADGER_H + 1, x + BADGER_W - 1, layout["walk_y"]], (255, 0, 255))
    px = layout["parcel_x"]
    box([px, layout["walk_y"] - 3, px + 3, layout["walk_y"]], (255, 0, 255), "Paket")
    im.save(path)
