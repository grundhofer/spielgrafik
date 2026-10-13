#!/usr/bin/env python3
"""Rotoskopie: macht aus den Kennbildern von blender/rotoscope.py flache Polygone für die Godot-Demo.

  .venv/bin/python styles/polygon-kino/scripts/vectorize.py <passes-ordner> [--only A] [--preview <ordner>]

Ablauf je Bild (Hintergrund-Ebene oder Dachs-Phase):
  1. Kennnummer -> (Objekt, Material); Lichtbild -> Helligkeit s. Regeln je Einstellung (RULES) wählen daraus
     einen Paletteneintrag (0..15) und ggf. eine Marke (Fenster, Laterne, Lampe, Boot).
  2. Kleine Flecken (< MIN_AREA Zielpixel) gehen im häufigsten Nachbarn auf.
  3. Jeder zusammenhängende Bereich wird ein Polygon: Umriss auf den Pixelkanten des überabgetasteten Bildes,
     Löcher gefüllt, nach unten unter später gezeichnete Nachbarn verlängert (keine Ritzen), auf Zielpixel
     verkleinert und mit Douglas-Peucker vereinfacht. Zeichenreihenfolge: große Flächen zuerst.
  3b. Stehphasen (SNAP): Ecken, die sich gegenüber der Vorphase um höchstens 1 px bewegen, rasten auf deren
     Ecken ein; so brodeln die Umrisse beim Stehen weniger.
  4. Prüfen: einfache Polygone (Godot verwirft sich selbst schneidende ohne Meldung), Rasterung wie die
     Grafikkarte (Pixelmitten) gegen das Kennbild -> Abweichung in Prozent.
Ausgabe: demo/data/scenes.json (Paletten, Ebenen, Dachs-Phasen, Ankerpunkte) und assets/vector_stats.json.
"""
import argparse
import fnmatch
import json
import os
import pathlib
import sys
import time

import numpy as np
from PIL import Image

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import polyvec as pv  # noqa: E402

HERE = pathlib.Path(__file__).resolve().parent
ENTRY = HERE.parent

TAGS = ["", "window", "lantern", "lamp", "boatA", "boatB"]

# 16 Farben je Einstellung. Einträge 0, 3, 12/8 und 7/6 (Schwarz, Rahmen, Schrift, Akzent) sind in beiden gleich,
# damit die Textleiste beim Palettenwechsel stehen bleibt.
PALETTES = {
    "A": [  # Totale, Abenddämmerung: violette Welt, Meer blaugrün, warme Lichter
        "#0b0a14",  # 0 Schwarz: Silhouetten, Fell dunkel, Leiste
        "#18172b",  # 1 Nacht: tiefe Schatten, nahe Silhouetten
        "#2b2a4f",  # 2 Blauviolett: Himmel oben, Stein im Schatten, ferne Inseln
        "#4a4579",  # 3 Violett: Himmel, Stein im Licht, Rahmen der Leiste
        "#7a5a8c",  # 4 Malve: Himmel Mitte, Kai hinten
        "#c06a7e",  # 5 Rosa: Himmel unten, Spiegelung
        "#f08c50",  # 6 Orange: Horizont, Glitzern
        "#ffd27a",  # 7 Lampengelb: Fenster, Laterne, Leuchtfeuer, Akzent
        "#24425c",  # 8 Meer
        "#3d6878",  # 9 Meer hell, Wellen
        "#4a2e2a",  # 10 Holz dunkel, Tasche
        "#8a5a3c",  # 11 Holz hell, Paket
        "#f0e2c8",  # 12 Weiß (Leuchtturm, Gesicht, Hemd), Schrift
        "#b3342c",  # 13 Rot (Band, Schal, Läden, Boot)
        "#2f4a35",  # 14 Grün (Mütze, Weste, Gras)
        "#9aa0b8",  # 15 Weiß im Schatten, gedämpfte Schrift
    ],
    "B": [  # Nah, Laterne von rechts vorn
        "#0b0a14",  # 0 Schwarz
        "#18172b",  # 1 Nacht: Meer, tiefe Schatten
        "#2b2a4f",  # 2 Blauviolett: Himmel oben, Fels, Kai vorn
        "#4a4579",  # 3 Violett: Himmel, Fels im Licht, Kai hinten, Rahmen
        "#c06a7e",  # 4 Rosa: Himmel unten
        "#f08c50",  # 5 Orange: Horizont, Laterne gedämpft
        "#3b3340",  # 6 Fell dunkel im Licht
        "#ffd27a",  # 7 Lampengelb: Laterne, Leuchtfeuer, Messing, Akzent
        "#f0e2c8",  # 8 Fell hell / Hemd im Licht, Schrift
        "#9aa0b8",  # 9 Fell hell / Hemd im Schatten, Leuchtturm im Schatten
        "#24402f",  # 10 Grün Schatten
        "#5e7a3a",  # 11 Grün Licht
        "#6e1c2a",  # 12 Rot Schatten
        "#d8452f",  # 13 Rot Licht
        "#4f3025",  # 14 Braun Schatten (Tasche, Holz)
        "#b47a45",  # 15 Braun Licht (Paket, Holz)
    ],
}


def R(obj, mat, **spec):
    return (obj, mat, spec)


# Regeln: erste passende (Objekt, Material) gewinnt. ramp = Paletteneinträge dunkel -> hell, cuts = Schwellen
# auf s = key + up_w * max(oben, 0) (Lichtbild). floor = Bänder nach Bildzeile für nach oben zeigende Flächen.
RULES = {
    "A": {
        "shade": {"up_w": 0.15},
        "rules": [
            R("Sea", "*", skip=True),
            R("CottageWindow", "*", c=7, tag="window"),
            R("LanternGlass", "*", c=7, tag="lantern"),
            R("LighthouseLamp", "*", c=7, tag="lamp"),
            R("Quay", "*", floor=[[110, 4], [142, 3], [999, 2]], ramp=[1, 2], cuts=[0.3]),
            R("Cottage", "Stone", ramp=[2, 3], cuts=[0.3]),
            R("Cottage", "StoneDark", ramp=[1, 2], cuts=[0.3]),
            R("Cottage", "Roof", ramp=[1, 2], cuts=[0.3]),
            R("Cottage", "WhitePaint", ramp=[15, 12], cuts=[0.3]),
            R("Cottage", "RedPaint", c=13),
            R("Lighthouse", "WhitePaint", ramp=[15, 12], cuts=[0.25]),
            R("Lighthouse", "RedPaint", c=13),
            R("Lighthouse", "StoneDark", ramp=[1, 2], cuts=[0.3]),
            R("Lighthouse", "*", c=0),
            R("Headland", "Grass", ramp=[2, 14], cuts=[0.45]),
            R("Headland", "*", ramp=[2, 3], cuts=[0.3]),
            R("IslandsFar", "*", c=2),
            R("WestHill", "Grass", ramp=[1, 14], cuts=[0.45]),
            R("WestHill", "*", ramp=[1, 2], cuts=[0.3]),
            R("RocksSea", "*", ramp=[1, 2], cuts=[0.3]),
            R("Boat*", "WhitePaint", ramp=[15, 12], cuts=[0.3], tag="boat"),
            R("Boat*", "RedPaint", c=13, tag="boat"),
            R("Boat*", "Wood", ramp=[10, 11], cuts=[0.3], tag="boat"),
            R("Boat*", "Rope", c=11, tag="boat"),
            R("Boat*", "*", c=10, tag="boat"),
            R("*", "WoodDark", ramp=[0, 10], cuts=[0.3]),
            R("*", "Wood", ramp=[10, 11], cuts=[0.3]),
            R("*", "Metal", c=0),
            R("*", "Rope", ramp=[10, 11], cuts=[0.3]),
            R("LanternPost", "StoneDark", c=1),
            # Dachs: flache Kostümfarben, Weiß mit Schattenseite
            R("*", "FurDark", c=0, near=2),
            R("*", "FurLight", ramp=[15, 12], cuts=[0.2]),
            R("Parcel", "Shirt", c=12),
            R("*", "Shirt", ramp=[15, 12], cuts=[0.2]),
            R("*", "Cap", c=14),
            R("*", "Vest", c=14),
            R("*", "Scarf", c=13),
            R("*", "Satchel", c=10),
            R("*", "Parcel", c=11),
            R("*", "Brass", c=14),
            R("*", "Nose", c=0),
            R("*", "Eye", c=0),
        ],
    },
    "B": {
        "shade": {"up_w": 0.15},
        "rules": [
            R("Sea", "*", skip=True),
            R("CottageWindow", "*", c=7, tag="window"),
            R("LanternGlass", "*", c=7, tag="lantern"),
            R("LighthouseLamp", "*", c=7, tag="lamp"),
            R("Quay", "*", floor=[[111, 3], [999, 2]], ramp=[1, 2], cuts=[0.3]),
            R("Lighthouse", "WhitePaint", ramp=[9, 8], cuts=[0.25]),
            R("Lighthouse", "RedPaint", ramp=[12, 13], cuts=[0.25]),
            R("Lighthouse", "StoneDark", ramp=[1, 2], cuts=[0.3]),
            R("Lighthouse", "*", c=0),
            R("Headland", "Grass", ramp=[1, 10], cuts=[0.45]),
            R("Headland", "*", ramp=[2, 3], cuts=[0.3]),
            R("IslandsFar", "*", c=2),
            R("WestHill", "Grass", ramp=[1, 10], cuts=[0.45]),
            R("WestHill", "*", ramp=[1, 2], cuts=[0.3]),
            R("RocksSea", "*", ramp=[1, 2], cuts=[0.3]),
            R("Boat*", "WhitePaint", ramp=[9, 8], cuts=[0.3], tag="boat"),
            R("Boat*", "RedPaint", ramp=[12, 13], cuts=[0.3], tag="boat"),
            R("Boat*", "Wood", ramp=[14, 15], cuts=[0.3], tag="boat"),
            R("Boat*", "*", c=14, tag="boat"),
            R("*", "WoodDark", ramp=[0, 14], cuts=[0.3]),
            R("*", "Wood", ramp=[14, 15], cuts=[0.3]),
            R("Bollards", "Metal", ramp=[1, 6], cuts=[0.3], rim=[0.45, 3]),   # Poller am Bildrand: Form statt Schwarz
            R("*", "Metal", c=0),
            R("*", "Rope", ramp=[14, 15], cuts=[0.3]),
            R("*", "StoneDark", ramp=[1, 6], cuts=[0.3]),
            R("*", "Stone", ramp=[6, 3], cuts=[0.3]),
            # Dachs (zur Kamera gedreht, Laterne von rechts vorn)
            R("*", "FurDark", ramp=[0, 6], cuts=[0.25], rim=[0.45, 5]),
            R("*", "FurLight", ramp=[9, 8], cuts=[0.15], rim=[0.45, 8]),
            R("Parcel", "Shirt", c=8),
            R("*", "Shirt", ramp=[9, 8], cuts=[0.15], rim=[0.45, 8]),
            R("*", "Cap", ramp=[10, 11], cuts=[0.25], rim=[0.45, 11]),
            R("*", "Vest", ramp=[10, 11], cuts=[0.25], rim=[0.45, 11]),
            R("*", "Scarf", ramp=[12, 13], cuts=[0.25], rim=[0.45, 13]),
            R("*", "Satchel", c=14, rim=[0.45, 5]),                  # Tasche dunkel mit Kante,
            R("*", "Parcel", c=15),                                  # Paket hell: zwei Gegenstände
            R("*", "Brass", c=7),
            R("*", "Nose", c=0),
            R("*", "Eye", c=0),
        ],
    },
}

# Vereinfachung (Zielpixel) und kleinste Fläche (Zielpixel²) je Bildart
EPS = {"bg": 1.6, "badger_A": 0.8, "badger_B": 1.3}
MIN_AREA = {"bg": 2.0, "badger_A": 0.8, "badger_B": 1.5}
if os.environ.get("PK_EPS"):                     # Versuche: PK_EPS="bg=1.6,badger_B=1.4"
    for kv in os.environ["PK_EPS"].split(","):
        k, v = kv.split("=")
        EPS[k] = float(v)
UNDER = 1.5          # Unterlage unter später gezeichnete Nachbarn, Zielpixel
EPS_GROW = {"bg": 0.045, "badger_A": 0.0, "badger_B": 0.02}   # große Flächen gröber: eps = max(eps, k * Wurzel(Fläche))
SNAP = {"idle": 1.0}  # Stehphasen: Ecken bis zu so vielen Zielpixeln an die Vorphase einrasten (weniger Brodeln;
                     # 1,2 px ließ einzelne Löcher zwischen Nachbarflächen offen)


def find_rule(shot, obj, mat):
    for o, m, spec in RULES[shot]["rules"]:
        if fnmatch.fnmatchcase(obj, o) and fnmatch.fnmatchcase(mat, m):
            return spec
    raise KeyError(f"keine Regel für {shot}: {obj}/{mat}")


def label_map(shot, ids, base, ss):
    idimg = np.asarray(Image.open(f"{base}_id.png"))
    lit = np.asarray(Image.open(f"{base}_lit.png")).astype(np.float32) / 255.0
    h, w = idimg.shape[:2]
    ident = np.where(idimg[..., 3] > 0, idimg[..., 0].astype(np.int32), -1)
    key = lit[..., 0]
    rim = lit[..., 1]
    up = lit[..., 2] * 2.0 - 1.0
    side_path = pathlib.Path(f"{base}_side.png")
    near = None
    if side_path.exists():                       # Gliedmaßen der rechten (kamerazugewandten) Körperseite
        sd = np.asarray(Image.open(side_path))
        near = (sd[..., 1] > 127) & (sd[..., 0] <= 127) & (sd[..., 3] > 0)
    sh = RULES[shot]["shade"]
    s = key + sh["up_w"] * np.maximum(up, 0.0)
    yy = (np.arange(h)[:, None] + 0.5) / ss * np.ones((1, w), np.float32)
    lab = np.full((h, w), -1, np.int32)
    for i in np.unique(ident):
        if i < 0:
            continue
        meta = ids.get(str(int(i)))
        if meta is None:
            raise KeyError(f"Kennnummer {i} unbekannt in {base}")
        spec = find_rule(shot, meta["object"], meta["material"])
        if spec.get("skip"):
            continue
        m = ident == i
        tname = spec.get("tag", "")
        if tname == "boat":                      # Marke nach Objekt (BoatA -> boatA): main.gd hängt jedes Boot an
            tname = "b" + meta["object"][1:]     # seinen Anker; unbekannte Namen brechen hier ab (TAGS.index)
        tag = TAGS.index(tname)
        vals = np.empty(int(m.sum()), np.int32)
        sv = s[m]
        if "c" in spec:
            vals[:] = spec["c"]
        else:
            ramp, cuts = spec["ramp"], spec["cuts"]
            vals[:] = ramp[0]
            for k, t in enumerate(cuts):
                vals[sv > t] = ramp[k + 1]
        if "near" in spec and near is not None:   # nahe Gliedmaßen heller als ferne
            vals[near[m]] = spec["near"]
        if "rim" in spec:                      # Gegenlicht: Kante zur Abendglut
            t_rim, c_rim = spec["rim"]
            vals[rim[m] > t_rim] = c_rim
        if "floor" in spec:
            f = up[m] > 0.5
            yv = yy[m]
            fv = np.full(f.sum(), spec["floor"][-1][1], np.int32)
            for ymax, idx in reversed(spec["floor"]):
                fv[yv[f] < ymax] = idx
            vals[f] = fv
        lab[m] = vals + 16 * tag
    return lab


def despeckle(lab, min_px):
    for _ in range(3):
        comp, info = pv.components(lab)
        small = [k for k, it in enumerate(info) if it[1] < min_px]
        if not small:
            return lab
        small.sort(key=lambda k: info[k][1])
        h, w = lab.shape
        for k in small:
            x0, y0, x1, y1 = info[k][2]
            xa, ya, xb, yb = max(x0 - 1, 0), max(y0 - 1, 0), min(x1 + 1, w), min(y1 + 1, h)
            cm = comp[ya:yb, xa:xb] == k
            ring = pv.dilate(cm, 1) & ~cm
            nb = lab[ya:yb, xa:xb][ring]
            nb_ne = nb[nb >= 0]
            if nb_ne.size and nb_ne.size >= 0.25 * nb.size:
                v, c = np.unique(nb_ne, return_counts=True)
                new = int(v[np.argmax(c)])
            else:
                new = -1
            sub = lab[ya:yb, xa:xb]
            sub[cm] = new
    return lab


def vectorize(lab, ss, eps, min_area, stats, grow=0.0):
    """Polygone in Zeichenreihenfolge: Liste (farbe, marke, punkte[(x, y) in Zielpixeln])."""
    lab = despeckle(lab, int(min_area * ss * ss))
    comp, info = pv.components(lab)
    h, w = lab.shape
    outlines = []
    for k, (v, a, bb) in enumerate(info):
        x0, y0, x1, y1 = bb
        m = comp[y0:y1, x0:x1] == k
        pts = pv.trace_outer(pv.close_pinches(m))
        outlines.append(abs(pv.area(pts)))
    order = sorted(range(len(info)), key=lambda k: -outlines[k])
    rank = np.full(len(info), 0, np.int32)
    for r, k in enumerate(order):
        rank[k] = r
    rank_img = np.where(comp >= 0, rank[np.maximum(comp, 0)], -1)
    r_ss = int(round(UNDER * ss))
    polys = []
    for k in order:
        v, a, bb = info[k]
        x0, y0, x1, y1 = bb
        xa, ya = max(x0 - r_ss - 1, 0), max(y0 - r_ss - 1, 0)
        xb, yb = min(x1 + r_ss + 1, w), min(y1 + r_ss + 1, h)
        cm = comp[ya:yb, xa:xb] == k
        later = rank_img[ya:yb, xa:xb] > rank[k]
        m = cm | (pv.dilate(cm, r_ss) & later)
        # nur der Teil, der mit dem Bereich selbst zusammenhängt
        mc, mi = pv.components(np.where(m, 0, -1).astype(np.int32))
        keep = np.unique(mc[cm])
        m = np.isin(mc, keep[keep >= 0])
        m = pv.close_pinches(m)
        pts = pv.trace_outer(m)
        pts = [((px + xa) / ss, (py + ya) / ss) for px, py in pts]
        e = max(eps, grow * np.sqrt(outlines[k]) / ss)    # outlines: Fläche in Pixeln des Kennbilds
        simp = None
        while e >= 0.05:
            cand = pv.drop_collinear(pv.simplify_closed(pts, e))
            if len(cand) >= 3 and pv.is_simple(cand):
                simp = cand
                break
            e *= 0.6
            stats["retries"] += 1
        if simp is None:
            cand = pv.drop_collinear(pts)
            if pv.is_simple(cand):
                simp = cand
            else:
                stats["dropped_nonsimple"] += 1
                continue
        if abs(pv.area(simp)) < 0.3:
            stats["dropped_tiny"] += 1
            continue
        polys.append((int(v) % 16, int(v) // 16, [(round(x, 2), round(y, 2)) for x, y in simp]))
    return polys


def snap_frames(frames, r, stats):
    """Zeitliche Glättung einer Phasenfolge: Jede Ecke rastet auf die nächste Ecke derselben Farbe und Marke der
    (bereits eingerasteten) Vorphase ein, wenn sie höchstens r Zielpixel entfernt liegt. Bewegung unter r bleibt
    stehen, größere kommt als ganzer Sprung. r < UNDER, damit keine Ritzen aufgehen. Polygone, die dadurch nicht
    mehr einfach oder zu klein sind, bleiben unverändert. Phase 0 bleibt unverändert."""
    out = [frames[0]]
    for polys in frames[1:]:
        ref = {}
        for c, t, pts in out[-1]:
            ref.setdefault((c, t), []).extend(pts)
        new = []
        for c, t, pts in polys:
            if (c, t) not in ref:
                new.append((c, t, pts))
                continue
            ra = np.asarray(ref[(c, t)], float)
            cand = []
            for x, y in pts:
                d = np.hypot(ra[:, 0] - x, ra[:, 1] - y)
                k = int(np.argmin(d))
                cand.append((float(ra[k, 0]), float(ra[k, 1])) if d[k] <= r else (x, y))
            ded = [q for i, q in enumerate(cand) if q != cand[i - 1]]
            ded = pv.drop_collinear(ded) if len(ded) >= 3 else ded
            if len(ded) >= 3 and pv.is_simple(ded) and abs(pv.area(ded)) >= 0.3:
                stats["snap_points"] += sum(1 for a, b in zip(cand, pts) if a != b)
                new.append((c, t, [(round(x, 2), round(y, 2)) for x, y in ded]))
            else:
                stats["snap_rejected"] += 1
                new.append((c, t, pts))
        out.append(new)
    return out


def check(lab, polys, ss):
    """Rasterung der Polygone (Zielauflösung) gegen das Kennbild an den Pixelmitten."""
    h, w = lab.shape[0] // ss, lab.shape[1] // ss
    ref = lab[ss // 2::ss, ss // 2::ss][:h, :w]
    img = np.full((h, w), -1, np.int32)
    for c, t, pts in polys:
        pv.raster(img, pts, c + 16 * t)
    m = (ref >= 0) | (img >= 0)
    bad = (ref != img) & m
    return img, float(bad.sum()) / max(1, int(m.sum())), int(bad.sum())


def to_rgb(img, pal, bg="#000000"):
    cols = np.array([[int(h[i:i + 2], 16) for i in (1, 3, 5)] for h in pal + [bg]], np.uint8)
    idx = np.where(img >= 0, img % 16, len(pal))
    return cols[idx]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("passes")
    ap.add_argument("--only", default="")
    ap.add_argument("--preview", default="")
    ap.add_argument("--out", default=str(ENTRY / "demo/data/scenes.json"))
    a = ap.parse_args()
    pdir = pathlib.Path(a.passes)
    ids = json.load(open(pdir / "ids.json"))
    frames = json.load(open(pdir / "frames.json"))
    shots_def = json.load(open(ENTRY / "blender/shots.json"))
    ss = frames["ss"]
    out = {"palettes": PALETTES, "tags": TAGS, "scene_px": frames["scene_px"], "shots": {}}
    stats = {"retries": 0, "dropped_nonsimple": 0, "dropped_tiny": 0, "snap_points": 0, "snap_rejected": 0,
             "images": {}}
    prev = pathlib.Path(a.preview) if a.preview else None
    if prev:
        prev.mkdir(parents=True, exist_ok=True)
    t0 = time.time()
    for shot, sdef in shots_def["shots"].items():
        if a.only and shot not in a.only.split(","):
            continue
        fi = frames["shots"][shot]
        so = {"layers": {}, "clips": {}, "anchors": {k: [round(v[0], 2), round(v[1], 2)]
                                                      for k, v in fi["anchors"].items()}}
        pal = PALETTES[shot]
        comp_img = None
        for layer in shots_def["layers"]:
            base = pdir / f"{shot}_{layer}"
            lab = label_map(shot, ids, str(base), ss)
            polys = vectorize(lab, ss, EPS["bg"], MIN_AREA["bg"], stats, EPS_GROW["bg"])
            img, err, nbad = check(lab, polys, ss)
            stats["images"][f"{shot}_{layer}"] = {"polygons": len(polys), "points": sum(len(p[2]) for p in polys),
                                                  "mismatch": round(err, 4)}
            print(f"{shot}_{layer}: {len(polys)} Polygone, {sum(len(p[2]) for p in polys)} Ecken, "
                  f"Abweichung {err * 100:.2f} % ({nbad} px)  [{time.time() - t0:.1f}s]")
            so["layers"][layer] = [[c, t, [v for xy in pts for v in xy]] for c, t, pts in polys]
            if comp_img is None:
                comp_img = img.copy()
            else:
                comp_img[img >= 0] = img[img >= 0]
        for cname, cl in fi["clips"].items():
            fr = []
            kind = f"badger_{shot}"
            labs, raw = [], []
            for i, t in enumerate(cl["times"]):
                base = pdir / f"{shot}_{cname}_{i:02d}"
                labs.append(label_map(shot, ids, str(base), ss))
                raw.append(vectorize(labs[-1], ss, EPS[kind], MIN_AREA[kind], stats, EPS_GROW[kind]))
            if cname in SNAP:
                raw = snap_frames(raw, SNAP[cname], stats)
            for i, (lab, polys) in enumerate(zip(labs, raw)):
                img, err, nbad = check(lab, polys, ss)
                stats["images"][f"{shot}_{cname}_{i:02d}"] = {"polygons": len(polys),
                                                              "points": sum(len(p[2]) for p in polys),
                                                              "mismatch": round(err, 4)}
                fr.append([[c, t, [v for xy in pts for v in xy]] for c, t, pts in polys])
                if prev and i == 0:
                    comp2 = comp_img.copy()
                    comp2[img >= 0] = img[img >= 0]
                    Image.fromarray(to_rgb(comp2, pal, "#5a5a8a")).resize(
                        (comp2.shape[1] * 3, comp2.shape[0] * 3), Image.NEAREST).save(prev / f"{shot}_{cname}.png")
            n = len(fr)
            print(f"{shot}_{cname}: {n} Phasen, im Mittel {np.mean([len(f) for f in fr]):.1f} Polygone  "
                  f"[{time.time() - t0:.1f}s]")
            so["clips"][cname] = {"times": cl["times"], "at": cl["at"], "foot_px": [round(v, 3) for v in cl["foot_px"]],
                                  "px_per_m_x": [round(v, 4) for v in cl["px_per_m_x"]],
                                  "px_per_m_up": round(cl["px_per_m_up"], 4), "feet": cl.get("feet", []),
                                  "frames": fr}
        if prev and comp_img is not None:
            Image.fromarray(to_rgb(comp_img, pal, "#5a5a8a")).resize(
                (comp_img.shape[1] * 3, comp_img.shape[0] * 3), Image.NEAREST).save(prev / f"{shot}_bg.png")
        out["shots"][shot] = so
    outp = pathlib.Path(a.out)
    outp.parent.mkdir(parents=True, exist_ok=True)
    if a.only and outp.exists():
        old = json.load(open(outp))
        old["shots"].update(out["shots"])
        old["palettes"] = PALETTES
        out = old
    outp.write_text(json.dumps(out, separators=(",", ":")))
    st = {k: v for k, v in stats.items() if k != "images"}
    st["images"] = stats["images"]
    (ENTRY / "assets").mkdir(exist_ok=True)
    (ENTRY / "assets/vector_stats.json").write_text(json.dumps(st, indent=1, ensure_ascii=False))
    print("Wiederholungen", stats["retries"], "verworfen (nicht einfach)", stats["dropped_nonsimple"],
          "verworfen (winzig)", stats["dropped_tiny"], "eingerastete Ecken", stats["snap_points"],
          "Einrasten abgelehnt", stats["snap_rejected"], f"-> {outp} ({outp.stat().st_size // 1024} KB)")


if __name__ == "__main__":
    main()
