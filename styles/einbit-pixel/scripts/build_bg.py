#!/usr/bin/env python3
"""Baut aus dem KI-Hintergrund (1-Bit-Pixelbild mit Pseudo-Raster) und der durchgepausten Maske die Tonkarte
für die Godot-Demo: 400×240, je Pixel Tonstufe (0–16), Musterfamilie und Bereich.

Das Bildmodell zeichnet 1-Bit-Pixel-Art, aber nicht auf einem festen Raster (Konturen 3–4 Bildpixel, Raster-
punkte 2 Bildpixel, im Wasser feiner). Statt die Pixel abzutasten (Moiré), wird je Zielpixel gemessen:
  * Bereich (Himmel / Wasser / Gegenstand) per Mehrheit aus der Maske, Gegenstände ab 40 % Anteil;
  * Gegenstände: dicke schwarze Striche (Öffnen mit 3×3) ab 40 % Anteil → Kontur (Stufe 0), dicke weiße
    Flächen ab 50 % → Stufe 16, sonst der mittlere Grauwert der Gegenstandspixel → eine von fünf Stufen
    (0, 4, 8, 12, 16 = schwarz, 25 %, 50 %, 75 %, weiß), danach Einzelpixel durch die Nachbarn ersetzt;
  * Himmel: Helligkeitsverlauf je Zeile (Median) → Zeilenraster (LINES); Wolken (Schachbrett im KI-Bild,
    erkannt an waagrechter Musterenergie) → Bayer-Stufen; Sterne als Einzelpixel;
  * Wasser: Helligkeit je Zeile → Strichraster (DASH), im Spiel zeilenweise verschoben.
Alle Muster setzt erst der Shader (bzw. onebit.render für die Vorschau) – so sind sie auf dem Bildraster exakt.

Ausgabe:
  demo/art/bg_tone.png   R = Stufe·15, G = Familie·85, B = Bereichscode (siehe REGION), deckend
  assets/bg_tone.png     Kopie
  assets/bg_preview.png  1-Bit-Vorschau in 400×240 (ohne Animation)
  demo/art/bg.json       Lage von Laterne, Fenster, Leuchtfeuer, Schornstein, Horizont, Kai (für main.gd)
  demo/art/patterns.png  Schwellenmatrizen der drei Musterfamilien (16×24, für den Shader)
  demo/art/boat_a/b.png  Boote als eigene 1-Bit-Sprites

    .venv/bin/python styles/einbit-pixel/scripts/build_bg.py
"""
import json, pathlib, sys

import numpy as np
from PIL import Image

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import onebit as ob  # noqa: E402
import props  # noqa: E402

ROOT = pathlib.Path(__file__).resolve().parents[1]
RAW = ROOT / "assets" / "raw"
W, R0, H = 400, 14, 240                 # Zielbreite, erste Zeile des Ausschnitts (im 400er-Raster), Höhe
OUTLINE = 0.35                          # Anteil dicker schwarzer Striche, ab dem ein Zielpixel Kontur wird
ROCKS = (300, 80, 400, 160)               # Felsnase im Ausschnitt (x0, y0, x1, y1) für den Mehrheitsfilter
OY = 22 - R0                             # Gegenstände (props) sind für den Ausschnitt ab Zeile 22 gesetzt
QUAY_ROWS = (146 + OY, 177 + OY)         # Kaifläche: hintere Kante bis Vorderkante (im Ausschnitt)
BOATS = [{"x0": 174, "x1": 211, "yw": 136 + OY, "bow_right": False}, {"x0": 246, "x1": 282, "yw": 139 + OY, "bow_right": True}]
TONE_CENTRES = [0.017, 0.359, 0.478, 0.611, 0.797]   # Flächenwerte der Tonplatte (k-means)
REGION = {"object": 0, "sky": 1, "water": 2, "ground": 3, "glass": 4, "star": 5, "lamp": 6, "window": 7}


def lum(p):
    a = np.asarray(Image.open(p).convert("RGB")).astype(np.float64) / 255
    return a @ [0.299, 0.587, 0.114]


def main():
    L = lum(RAW / "bg_direct.png")
    T = lum(RAW / "tone.png")
    m = np.asarray(Image.open(RAW / "mask.png").convert("RGB")).astype(int)
    H0, W0 = L.shape
    Ht = round(H0 * W / W0)
    sky = (m[..., 0] > 180) & (m[..., 1] < 90) & (m[..., 2] > 180)
    wat = (m[..., 0] < 90) & (m[..., 1] > 180) & (m[..., 2] > 180)
    obj = ~(sky | wat)

    cs, cw, co = (ob.cell_mean(x, W, Ht) for x in (sky, wat, obj))
    region = np.where(co >= 0.4, REGION["object"], np.where(cs >= cw, REGION["sky"], REGION["water"]))
    lev = np.zeros((Ht, W), int)
    fam = np.zeros((Ht, W), int)
    Lb = ob.box_mean(L, 7)                      # Rasterpunkte des 1-Bit-Bildes zu Grauwerten gemittelt

    # --- Gegenstände: Formen aus der Tonplatte, Ton aus dem 1-Bit-Bild
    # Tonplatte auf ihre fünf Flächenwerte; zusammenhängende Flächen gleicher Stufe (innerhalb der Konturen)
    # bekommen den mittleren Grauwert des 1-Bit-Bildes in dieser Fläche, auf 0/4/8/12/16 gerundet.
    cent = np.array(TONE_CENTRES)
    tl = np.abs(T[..., None] - cent).argmin(-1)
    comp = components(np.where(obj, tl, -1))
    n = comp.max() + 1
    sums = np.bincount(comp.ravel(), weights=Lb.ravel(), minlength=n)
    cnts = np.bincount(comp.ravel(), minlength=n)
    comp_tone = sums / np.maximum(cnts, 1)
    src_lev = np.clip((comp_tone[comp] * 4).round(), 0, 4).astype(int) * 4
    src_lev = np.where(tl == 0, 0, src_lev)
    covs = np.stack([ob.cell_mean((src_lev == k) & obj, W, Ht) for k in (0, 4, 8, 12, 16)], -1)
    lev_o = np.array([0, 4, 8, 12, 16])[covs.argmax(-1)]
    cb = covs[..., 0] / np.maximum(co, 1e-6)
    lev_o = np.where(cb >= OUTLINE, 0, lev_o)
    lev_o = despeckle(lev_o, region == REGION["object"])
    obj_t = region == REGION["object"]
    lev[obj_t] = lev_o[obj_t]
    fam[obj_t] = ob.BAYER

    # --- Himmel: eigener Stufenverlauf zum Horizont (Zeilenraster), Wolken aus der Tonplatte, Sterne
    hz = horizon_row(sky, wat, H0, Ht)
    sky_t = region == REGION["sky"]
    yy = np.arange(Ht)[:, None] + np.zeros((1, W), int)
    d = hz - yy
    sky_lev = sky_level(d)
    lev[sky_t] = sky_lev[sky_t]
    fam[sky_t] = ob.LINES
    cloud = ob.cell_mean(sky & (tl >= 3), W, Ht) >= 0.5
    cl = sky_t & cloud
    cl_tone = ob.cell_mean(Lb * sky, W, Ht) / np.maximum(cs, 1e-6)
    lev[cl] = np.array([4, 6, 8])[np.clip(((cl_tone[cl] - 0.3) / 0.15).round().astype(int), 0, 2)]
    fam[cl] = ob.BAYER
    # Wolkenunterkante vom Glutband angestrahlt: unterste Wolkenzeile weiß
    edge = cl & ~np.roll(cl, -1, 0) & (d < 60)
    lev[edge] = 16
    # Sterne: im dunklen Himmel gesetzt (die Sterne des Modells liegen fast alle oberhalb des Ausschnitts),
    # einzelne Pixel, wenige Kreuze; fester Seed
    rng = np.random.default_rng(11)
    st = np.zeros_like(sky_t)
    cand = sky_t & ~cl & (d > 40) & (yy >= R0 + 1)
    ok = cand.copy()
    for _ in range(400):
        y, x = int(rng.integers(R0 + 1, Ht)), int(rng.integers(2, W - 2))
        if not ok[y, x] or st[max(0, y - 6):y + 7, max(0, x - 10):x + 11].any():
            continue
        st[y, x] = True
        if rng.random() < 0.15 and ok[y - 1:y + 2, x - 1:x + 2].all():
            st[y - 1, x] = st[y + 1, x] = st[y, x - 1] = st[y, x + 1] = True
        if st.sum() > 70:
            break
    lev[st] = 16
    region = np.where(st, REGION["star"], region)

    # --- Wasser: eigener Verlauf (hell unter dem Glutband, dunkel zum Kai), Strichraster
    wat_t = region == REGION["water"]
    dw = yy - hz
    wat_lev = water_level(dw)
    lev[wat_t] = wat_lev[wat_t]
    fam[wat_t] = ob.DASH

    # Horizontlinie des Modells (schwarzer Strich zwischen Himmel und Wasser) wird Glutband
    for x in range(W):
        for y in range(hz - 3, hz + 3):
            if region[y, x] == REGION["object"] and lev[y, x] == 0:
                up = region[max(0, y - 3):y, x]
                dn = region[y + 1:y + 4, x]
                if (up == REGION["sky"]).any() and (dn == REGION["water"]).any():
                    region[y, x], lev[y, x], fam[y, x] = REGION["sky"], 16, ob.LINES
    # kleine Gegenstandsinseln im Wasser (Strichreste des Modells) werden Wasser
    cmp = components(np.where(region == REGION["object"], 1, -1))
    sizes = np.bincount(cmp.ravel())
    small = (cmp > 0) & (sizes[cmp] <= 6) & (np.abs(yy - hz) < 60)
    ring = np.zeros_like(small)
    for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1)):
        ring |= np.roll(region == REGION["water"], (dy, dx), (0, 1))
    small &= ring
    region[small], lev[small], fam[small] = REGION["water"], wat_lev[small], ob.DASH

    # Ausschnitt
    lev, fam, region = (a[R0:R0 + H].copy() for a in (lev, fam, region))
    # Felsnase: Mehrheitsfilter glättet die Musterflecken der Umrechnung (nur Gegenstandspixel)
    rocks = np.zeros_like(lev, bool)
    rocks[ROCKS[1]:ROCKS[3], ROCKS[0]:ROCKS[2]] = True
    lev = majority(lev, rocks & (region == REGION["object"]), 2)
    info = place_fixtures(lev, fam, region, int(hz - R0))

    out = np.zeros((H, W, 4), np.uint8)
    out[..., 0] = lev * 15
    out[..., 1] = fam * 85
    out[..., 2] = region * 30
    out[..., 3] = 255
    (ROOT / "demo" / "art").mkdir(parents=True, exist_ok=True)
    Image.fromarray(out).save(ROOT / "demo" / "art" / "bg_tone.png")
    Image.fromarray(out).save(ROOT / "assets" / "bg_tone.png")
    prev = ob.to_rgb(ob.render(lev, fam))
    Image.fromarray(prev).save(ROOT / "assets" / "bg_preview.png")
    info.update({"size": [W, H], "crop_row": R0, "rows_source": Ht, "levels": "R/15", "family": "G/85", "region": "B/30",
                 "regions": REGION})
    info["boats"] = make_boats()
    for pdir in (ROOT / "demo" / "art", ROOT / "assets"):
        Image.fromarray(ob.pattern_texture(), "L").save(pdir / "patterns.png")
    (ROOT / "demo" / "art" / "bg.json").write_text(json.dumps(info, indent=1))
    cnt = {k: int((region == v).sum()) for k, v in REGION.items()}
    print("Bereiche", cnt, "Horizont", info["horizon"], "Flächen", n)


def make_boats():
    """Boote als eigene 1-Bit-Sprites (schaukeln im Spiel), Muster im Sprite-Raster."""
    out = []
    for i, b in enumerate(BOATS):
        x0, y0 = b["x0"] - 2, b["yw"] - 16
        w, h = b["x1"] - b["x0"] + 5, 19
        lev = np.full((h, w), -1)
        fam = np.zeros((h, w), int)
        reg = np.zeros((h, w), int)
        props.boat(props.Canvas(lev, fam, reg), b["x0"] - x0, b["x1"] - x0, b["yw"] - y0, bow_right=b["bow_right"])
        rgba = np.zeros((h, w, 4), np.uint8)
        on = lev >= 0
        px = ob.render(np.maximum(lev, 0), np.zeros_like(lev), x0, y0)
        rgba[on, :3] = np.where(px[on], 255, 0)[:, None]
        rgba[on, 3] = 255
        name = "boat_%s.png" % "ab"[i]
        Image.fromarray(rgba).save(ROOT / "demo" / "art" / name)
        Image.fromarray(rgba).save(ROOT / "assets" / name)
        out.append({"file": name, "pos": [x0, y0], "size": [w, h]})
    return out


def boat_shade(lev, region, b):
    """Wasser in einem Ring um den Rumpf (Ellipse, etwas breiter als das Boot, bis 3 px unter die
    Wasserlinie) eine Stufe dunkler: Strichraster 3 → 2 → 1 (Koordinaten des Ausschnitts)."""
    ramp = {16: 12, 12: 8, 8: 6, 6: 4, 4: 3, 3: 2, 2: 1, 1: 1}
    cx, cy = (b["x0"] + b["x1"]) / 2, b["yw"] - 4
    rx, ry = (b["x1"] - b["x0"]) / 2 + 5, 9
    for y in range(int(cy - ry), int(cy + ry) + 1):
        for x in range(int(cx - rx), int(cx + rx) + 1):
            if ((x - cx) / rx) ** 2 + ((y - cy) / ry) ** 2 <= 1 and region[y, x] == REGION["water"]:
                lev[y, x] = ramp.get(int(lev[y, x]), lev[y, x])


def sky_level(d):
    """Himmel: Stufen nach Abstand d zum Horizont (Zeilen)."""
    d = np.asarray(d)
    return np.select([d > 72, d > 58, d > 45, d > 33, d > 23, d > 15, d > 9, d > 4], [0, 1, 2, 4, 6, 8, 10, 12], 16)


def water_level(dw):
    """Wasser: hell unter dem Glutband, zum Kai dunkler (Strichraster)."""
    dw = np.asarray(dw)
    return np.select([dw < 2, dw < 5, dw < 9, dw < 15, dw < 24], [12, 8, 6, 4, 3], 2)


def horizon_row(sky, wat, H0, Ht):
    """Erste Wasserzeile (Median über die Spalten) im 400er-Raster."""
    ys = [np.where(wat[:, x])[0].min() for x in range(0, sky.shape[1], 8) if wat[:, x].any()]
    return int(round(np.median(ys) * Ht / H0))


def components(cls):
    """4-zusammenhängende Flächen gleicher Klasse (cls ≥ 0); cls < 0 bleibt Fläche 0. Markenweitergabe mit
    Zeigersprung, rein mit NumPy."""
    h, w = cls.shape
    lab = np.arange(h * w).reshape(h, w)
    valid = cls >= 0
    lab = np.where(valid, lab, h * w)
    while True:
        old = lab
        nb = lab.copy()
        for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            sh = np.roll(lab, (dy, dx), (0, 1))
            sc = np.roll(cls, (dy, dx), (0, 1))
            okm = (sc == cls) & valid
            if dy == 1: okm[0, :] = False
            if dy == -1: okm[-1, :] = False
            if dx == 1: okm[:, 0] = False
            if dx == -1: okm[:, -1] = False
            nb = np.where(okm, np.minimum(nb, sh), nb)
        flat = nb.ravel()
        flat = np.where(flat < h * w, flat, h * w)
        ext = np.append(flat, h * w)
        for _ in range(6):                      # Zeigersprung
            ext = ext[ext]
        lab = ext[:-1].reshape(h, w)
        if np.array_equal(lab, old):
            break
    _, inv = np.unique(lab, return_inverse=True)
    inv = inv.reshape(h, w) + 1
    return np.where(valid, inv, 0)


def fill_nan(a):
    idx = np.arange(len(a))
    ok = ~np.isnan(a)
    return np.interp(idx, idx[ok], a[ok])


def majority(lev, valid, rounds=1):
    """3×3-Mehrheitsfilter über die Stufen 0/4/8/12/16 (bei Gleichstand bleibt die Stufe)."""
    lev = lev.copy()
    h, w = lev.shape
    steps = (0, 4, 8, 12, 16)
    for _ in range(rounds):
        p = np.pad(lev, 1, mode="edge")
        nb = np.stack([p[1 + dy:1 + dy + h, 1 + dx:1 + dx + w] for dy in (-1, 0, 1) for dx in (-1, 0, 1)], -1)
        counts = np.stack([(nb == s_).sum(-1) for s_ in steps], -1)
        best = np.array(steps)[counts.argmax(-1)]
        win = counts.max(-1) >= 5
        lev = np.where(valid & win, best, lev)
    return lev


def despeckle(lev, valid, rounds=2):
    """Einzelne Pixel einer Mittelstufe (4, 8, 12), die keinen gleichen Nachbarn haben, durch die häufigste
    Stufe der 8 Nachbarn ersetzen; Konturen (0) und Weiß (16) bleiben."""
    lev = lev.copy()
    h, w = lev.shape
    for _ in range(rounds):
        p = np.pad(lev, 1, mode="edge")
        nb = np.stack([p[1 + dy:1 + dy + h, 1 + dx:1 + dx + w] for dy in (-1, 0, 1) for dx in (-1, 0, 1)
                       if (dy, dx) != (0, 0)], -1)
        same = (nb == lev[..., None]).sum(-1)
        counts = np.stack([(nb == s).sum(-1) for s in (0, 4, 8, 12, 16)], -1)
        mode = np.array([0, 4, 8, 12, 16])[counts.argmax(-1)]
        fix = valid & (same == 0) & np.isin(lev, (4, 8, 12))
        lev[fix] = mode[fix]
    return lev


def place_fixtures(lev, fam, region, hz):
    """Von Hand gesetzte Teile (scripts/props.py) über die umgerechnete KI-Fläche legen."""
    c = props.Canvas(lev, fam, region, OY)
    rng = np.random.default_rng(7)
    ys = np.arange(H)
    sky_l = sky_level(hz - ys)
    wat_l = [int(water_level(y - hz)) if y > hz else None for y in ys]
    quay = QUAY_ROWS[0] - OY                 # in props-Koordinaten
    # Kai-Stufe je Zeile: häufigste Stufe der Kaifläche rechts der Mitte
    gl = [int(np.bincount(lev[y, 180:380]).argmax()) for y in ys]

    def clear(x0, y0, x1, y1):
        c.clear(x0, y0, x1, y1, sky_l, wat_l, QUAY_ROWS[0], gl)

    # Kaifläche als eigener Bereich (Lichtkegel der Laterne). Vor den Gegenständen gesetzt, damit nur die
    # umgerechnete Kaifläche den Lichtkegel bekommt und Konturen von Fass, Sockel und Kisten schwarz bleiben.
    kai = (region == REGION["object"]) & (ys[:, None] >= QUAY_ROWS[0]) & (ys[:, None] <= QUAY_ROWS[1])
    region[kai] = REGION["ground"]
    # Leuchtturm
    clear(350, 22, 380, 86)
    lamp = props.lighthouse(c, 357, 39)
    # Galgenlaterne, Fässer: alte Flächen löschen, dann die Laterne (Pfahl mit Sockel auf dem Kai), dann die
    # Fässer. Früher löschte das clear() der Fässer und Kisten den unteren Teil des Pfahls (Ende bei y≈127).
    clear(88, 62, 126, quay + 3)
    clear(62, 112, 178, quay + 9)
    glass, lantern_c = props.lantern(c, 91, 66, quay + 3, 122, 68)
    props.barrel(c, 66, 128)
    props.barrel(c, 98, 129)
    # Steg (Boote sind eigene Sprites, darunter Wasser)
    clear(170, 112, 286, quay - 1)
    props.jetty(c, quay - 1, 119, (190, 243), (203, 233))
    # das wartende Paket
    props.parcel(c, 160, 160)
    # Tauwerk
    clear(282, quay - 3, 326, quay + 14)
    props.rope_coil(c, 287, quay - 2)
    # Kistenstapel rechts neben dem Tauwerk (im KI-Bild bei x 130–170; versetzt, damit der Dachs vor freiem
    # Wasser stehen bleibt und sich die Grußpfote nicht mit einer Kiste mischt)
    kx = 182
    props.crate(c, 130 + kx, 136, 20, 17, kind="slats_h")
    props.crate(c, 150 + kx, 139, 18, 14, top=3, side=3, kind="brace")
    props.crate(c, 139 + kx, 119, 18, 15, kind="slats_v")
    # Häuschen: Schornstein, Mauer, Tür, Fenster
    clear(4, 0, 40, 26)
    smoke = props.chimney(c, rng)
    window = props.cottage_front(c, rng)
    # Wasser um die Boote eine Stufe dunkler, damit die hellen Rümpfe als Flächen stehen
    for b in BOATS:
        boat_shade(lev, region, b)
    centre = lambda pts: [round(float(np.mean([p[0] for p in pts])), 1), round(float(np.mean([p[1] for p in pts])) + OY, 1)]
    lantern_c = [lantern_c[0], lantern_c[1] + OY]
    smoke = [smoke[0], smoke[1] + OY]
    return {"horizon": hz, "quay_rows": list(QUAY_ROWS), "lamp": centre(lamp), "lantern": list(lantern_c),
            "lantern_glass": centre(glass), "window": centre(window), "chimney": list(smoke),
            "boats": BOATS, "parcel": [160, 160 + OY, 15, 9]}


if __name__ == "__main__":
    main()
