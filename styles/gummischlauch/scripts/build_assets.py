"""Baut alle Spiel-Assets aus den KI-Rohbildern und schreibt sie nach assets/ und demo/art/.

Eingänge (assets/raw/):
  bg_b.png     Hintergrundplatte (agy, 1264×848), Versuch 2 mit Versuch 1 als Lagereferenz
  props.png    Requisitenbogen (Codex, echter Alphakanal): Häuschen, Leuchtturm, Laternenpfahl, Fässer,
               Kisten, Tau, zwei Boote
  badger.png   Teilebogen des Dachses (Codex, echter Alphakanal): Rumpf seitlich und von vorn ohne Arme und
               Beine, vier Handschuhe, Paket

Ausgänge:
  assets/bg.png                 1280×720, Zeilen 120–830 der Platte, hinter dem Steg mit Wasser aufgefüllt
  assets/props/<name>.png       Requisite auf Spielgröße, mit durchsichtigem Rand für das Biegen im Takt;
                                props/jetty.png ist der aus der Platte freigestellte Steg
  assets/badger/<name>.png      Teile des Dachses auf Spielgröße (Faktor 0,14); im Winkhandschuh ist der
                                überzählige kleine Finger entfernt (patch_glove_wave)
  assets/scene.json             Lage, Anker und Merkpunkte (Schornstein, Fenster, Lampe, Laterne, Schultern,
                                Hüften, Handschuhanker) in Texturpixeln, Bildschirmlage der Requisiten
  assets/fx/glow.png            weicher Lichthof (für additive Lichter)

    .venv/bin/python styles/gummischlauch/scripts/build_assets.py
"""
import json
import pathlib
import shutil

import numpy as np
from PIL import Image

import gs_util as g

HERE = pathlib.Path(__file__).resolve().parent.parent
RAW = HERE / "assets" / "raw"
OUT = HERE / "assets"
ART = HERE / "demo" / "art"

# Bildausschnitt der Platte: Zeilen CROP_TOP .. CROP_TOP+711 (16:9 bei 1264 px Breite), Faktor 1280/1264
CROP_TOP = 120
BG_K = 1280 / 1264

# Requisiten: Bogenrechteck (Komponente), Maßstab, Bildschirmlage des Ankers, Biegeweite und Stauchung
# Anker = Mitte der Standfläche (bei Booten: Mitte der Wasserlinie). Merkpunkte in Bogenkoordinaten:
# Schornstein = Mitte der obersten deckenden Zeilen, Fenster/Lampe/Laterne = Schwerpunkt der hellen warmen
# Glaspixel (R > 0,9, G > 0,62, B < 0,62) im jeweiligen Glasbereich, gemessen im Bogen.
PROPS = {
    # Maßstab Häuschen/Fässer/Kisten gegenüber der ersten Fassung (0,52/0,42/0,46) um etwa 1,4 vergrößert und der
    # Dachs von 0,19 auf 0,14 verkleinert: Die Tür (Rahmen samt Sturz) erreicht so etwa 0,7 der Dachshöhe.
    "cottage": dict(box=(82, 193, 601, 590), s=0.73, at=(165, 548), bend=18.0, squash=0.06,
                    points={"chimney": (182, 196), "window": (434, 484)}),
    "lighthouse": dict(box=(656, 48, 931, 596), s=0.37, at=(1160, 229), bend=14.0, squash=0.04,
                       points={"lamp": (794, 140)}),
    "lantern": dict(box=(1167, 124, 1391, 593), s=0.62, at=(868, 566), bend=17.0, squash=0.035,
                    anchor_x=1199, points={"lamp": (1342, 356)}),
    "barrels": dict(box=(18, 730, 318, 937), s=0.57, at=(1046, 562), bend=8.0, squash=0.09, points={}),
    "crates": dict(box=(339, 679, 573, 941), s=0.62, at=(1180, 566), bend=12.0, squash=0.07, points={}),
    "rope": dict(box=(592, 829, 857, 945), s=0.40, at=(792, 580), bend=0.0, squash=0.07, points={}),
    # Boote: Rumpf in Bogenzeile cut abgeschnitten (untere Tuschelinie verschwindet unter der Wasserlinie).
    # Wegen des größeren Häuschens beide rechts vom Steg (boat_a liegt am Steg, sein Heck dahinter).
    "boat_a": dict(box=(854, 637, 1186, 921), s=0.55, at=(625, 452), cut=910, points={}),
    "boat_b": dict(box=(1224, 700, 1519, 922), s=0.46, at=(805, 446), cut=911, points={}),
}

# Steg: aus der Platte freigestellt (Holz und Tuschelinie im Rechteck, größte Komponente, Löcher gefüllt),
# tanzt mit kleinem Ausschlag; dahinter wird die Platte zeilenweise mit Wasser aufgefüllt.
JETTY = dict(box=(385, 372, 554, 493), bend=4.0, squash=0.03)

# Dachs: ein Maßstab für alle Teile (0,14; erste Fassung 0,19, Puppe skaliert mit K in puppet.gd).
# Anker in Bogenkoordinaten.
BS = 0.14
BADGER = {
    "body_side": dict(box=(56, 83, 627, 953), anchor=(270, 953),
                      points={"sleeve": (92, 546), "hip_near": (296, 906), "hip_far": (250, 900),
                              "shoulder_far": (300, 560), "eye": (418, 240)}),
    "body_front": dict(box=(611, 84, 1188, 953), anchor=(900, 953),
                       points={"sleeve_l": (646, 546), "sleeve_r": (1150, 537), "hip_l": (846, 905),
                               "hip_r": (954, 905), "eye_l": (840, 304), "eye_r": (983, 302)}),
    # Handschuhe: Anker = Mitte der Stulpenöffnung, Achse = Richtung vom Handgelenk zu den Fingern
    "glove_open": dict(box=(1244, 62, 1464, 234), anchor=(1254, 150), axis=(1, 0)),
    "glove_fist": dict(box=(1253, 258, 1433, 395), anchor=(1262, 312), axis=(1, 0)),
    "glove_wave": dict(box=(1244, 412, 1430, 622), anchor=(1350, 592), axis=(0, -1)),  # nach patch_glove_wave
    "glove_grip": dict(box=(1250, 633, 1429, 773), anchor=(1262, 702), axis=(1, 0)),
    "parcel": dict(box=(1218, 801, 1484, 975), anchor=(1351, 888)),
}


def cut_component(rgba, lab, box):
    """Komponente, deren Rechteck box ist, mit gereinigtem Alpha ausschneiden (Nachbarn bleiben draußen)."""
    x0, y0, x1, y1 = box
    sub = lab[y0:y1, x0:x1]
    ids, counts = np.unique(sub[sub > 0], return_counts=True)
    cid = ids[np.argmax(counts)]
    # Maske der Komponente um 2 px weiten, damit die Kantenglättung mitkommt
    m = sub == cid
    for _ in range(2):
        m = m | np.roll(m, 1, 0) | np.roll(m, -1, 0) | np.roll(m, 1, 1) | np.roll(m, -1, 1)
    part = rgba[y0:y1, x0:x1].copy()
    part[..., 3] = np.where(m, g.clean_alpha(part[..., 3]), 0.0)
    return part


def patch_glove_wave(rgba):
    """Winkhandschuh: Codex malte trotz „four fingers“ Daumen, drei Finger und einen kleinen Finger rechts (fünf).
    Der 1930er-Handschuh hat Daumen und drei Finger: den kleinen Finger in Bogenauflösung entfernen und die
    Kontur als Tuschebogen von der rechten Kante des dritten Fingers zur Handballenkante schließen.
    Kontur x_c(y) als Hermite-Kurve von (1416 | 474) nach (1415 | 541) mit den Steigungen der vorhandenen
    Kontur an beiden Enden (−0,33 bzw. −0,3 px je Zeile, gemessen) und 4 px Wölbung nach außen (sin², ändert
    die Endsteigungen nicht). Innen werden nur dunkle Pixel (die alte Fingerfuge) mit Handschuhweiß übermalt."""
    ya, yb = 474, 541
    xa, xb, ma, mb = 1416.0, 1415.0, -0.33, -0.30
    ink_w = 6.5
    x_lo, x_hi = 1392, 1480
    sub = rgba[ya:yb + 1, x_lo:x_hi].copy()
    # Füllfarbe: Median der hellen Handschuhfläche im Handballen links der Kontur
    pal = rgba[515:532, 1394:1408]
    pal = pal[(pal[..., 3] > 0.9) & (pal[..., :3].min(axis=2) > 0.6)]
    fill = np.median(pal[:, :3], axis=0)
    ink = np.array([0.016, 0.008, 0.004])
    ys = np.arange(ya, yb + 1)[:, None].astype(np.float32)
    xs = np.arange(x_lo, x_hi)[None, :].astype(np.float32) + 0.5
    u = (ys - ya) / (yb - ya)
    n = float(yb - ya)
    xc = (xa * (2 * u**3 - 3 * u**2 + 1) + ma * n * (u**3 - 2 * u**2 + u) + xb * (-2 * u**3 + 3 * u**2)
          + mb * n * (u**3 - u**2) + 4.0 * np.sin(np.pi * u) ** 2)
    d = xs - xc                      # > 0 außerhalb (rechts), < 0 innen
    half = ink_w / 2
    a_out = np.clip(half + 0.5 - d, 0.0, 1.0)          # Deckung bis zur Außenkante der Kontur
    t_ink = np.clip(d + half + 0.5, 0.0, 1.0)          # 1 auf und außerhalb der Kontur, 0 tief innen
    # innen: dunkle Pixel (Fingerfuge samt Kantenglättung) anteilig mit Handschuhweiß übermalen
    lum = sub[..., :3].mean(axis=2)
    w_dark = np.clip((float(fill.mean()) - lum) / (float(fill.mean()) - 0.3), 0.0, 1.0)
    # entlang der alten Fuge (1399|508 → 1418|476) auch den hellen Saum der Kantenglättung übermalen
    p0, p1 = np.array([1399.0, 508.0]), np.array([1418.0, 476.0])
    v = p1 - p0
    tt = np.clip(((xs - p0[0]) * v[0] + (ys - p0[1]) * v[1]) / (v @ v), 0.0, 1.0)
    dist = np.hypot(xs - (p0[0] + tt * v[0]), ys - (p0[1] + tt * v[1]))
    w_dark = np.maximum(w_dark, np.clip(7.0 - dist, 0.0, 1.0))[..., None]
    inner = sub[..., :3] * (1 - w_dark) + fill[None, None, :] * w_dark
    inner = np.where(sub[..., 3:4] > 0.5, inner, fill[None, None, :])
    rgb = inner * (1 - t_ink[..., None]) + ink[None, None, :] * t_ink[..., None]
    sub[..., :3] = rgb
    sub[..., 3] = a_out
    rgba[ya:yb + 1, x_lo:x_hi] = sub
    return rgba


def scale_part(part, s):
    h, w = part.shape[:2]
    size = (max(1, round(w * s)), max(1, round(h * s)))
    return g.premul_resize(part, size), (size[0] / w, size[1] / h)


def build_bg():
    im = Image.open(RAW / "bg_b.png").convert("RGB")
    h = round(1264 * 9 / 16)
    im = im.crop((0, CROP_TOP, 1264, CROP_TOP + h)).resize((1280, 720), Image.LANCZOS)
    im.save(OUT / "bg.png")
    return {"crop_top": CROP_TOP, "rows": h, "scale": BG_K}


def build_jetty():
    """Steg aus der fertigen Platte (assets/bg.png) freistellen und die Platte dahinter auffüllen.
    Maske: Holz (R − B > 0,10) oder Tusche (alle Kanäle < 0,42) im Rechteck JETTY["box"], größte Komponente,
    Löcher gefüllt, 1 px geweitet (Kantenglättung des Aquarells kommt mit). Auffüllen: Maske 3 px weiter, je Zeile
    linear zwischen den Wasserfarben links und rechts (Mittel aus 3 px) – das Wasser der Platte ist waagrecht
    gestrichen, und sichtbar werden nur wenige Pixel, wenn der Steg im Takt biegt."""
    im = np.asarray(Image.open(OUT / "bg.png").convert("RGB")).astype(np.float32) / 255.0
    x0, y0, x1, y1 = JETTY["box"]
    sub = im[y0:y1, x0:x1]
    cand = ((sub[..., 0] - sub[..., 2]) > 0.10) | (sub.max(axis=2) < 0.42)
    lab, comps = g.label(cand, min_px=50)
    m = lab == comps[0][2]
    hlab, hcomps = g.label(~m, min_px=0)
    H, W = m.shape
    for _, (bx0, by0, bx1, by1), cid in hcomps:
        if bx0 > 0 and by0 > 0 and bx1 < W and by1 < H:  # berührt den Rand nicht: Loch
            m |= hlab == cid

    def grow(mask, n):
        for _ in range(n):
            mask = mask | np.roll(mask, 1, 0) | np.roll(mask, -1, 0) | np.roll(mask, 1, 1) | np.roll(mask, -1, 1)
        return mask

    pad = 6
    full = np.zeros(im.shape[:2], bool)
    full[y0:y1, x0:x1] = m
    sprite_mask = grow(full, 1)
    sprite_mask[y1:] = False                     # unten nicht in den Kai wachsen
    fill_mask = grow(sprite_mask, 3)
    fill_mask[y1:] = False
    # Sprite
    bend = JETTY["bend"]
    ys, xs = np.nonzero(sprite_mask)
    sx0, sy0, sx1, sy1 = xs.min(), ys.min(), xs.max() + 1, ys.max() + 1
    w, h = sx1 - sx0, sy1 - sy0
    padx = int(np.ceil(bend * 1.6 + 0.08 * w + pad))
    padt = int(np.ceil(0.14 * h + pad))
    canvas = np.zeros((h + padt + 2, w + 2 * padx, 4), np.float32)
    canvas[padt:padt + h, padx:padx + w, :3] = im[sy0:sy1, sx0:sx1]
    canvas[padt:padt + h, padx:padx + w, 3] = sprite_mask[sy0:sy1, sx0:sx1]
    canvas = g.bleed(canvas)
    g.save_rgba(canvas, OUT / "props" / "jetty.png")
    # Platte auffüllen (zeilenweise)
    out = im.copy()
    for y in range(fill_mask.shape[0]):
        cols = np.nonzero(fill_mask[y])[0]
        if cols.size == 0:
            continue
        xl, xr = cols.min() - 1, cols.max() + 1
        cl = im[y, max(0, xl - 2):xl + 1].mean(axis=0)
        cr = im[y, xr:xr + 3].mean(axis=0)
        for x in cols:
            t = (x - xl) / (xr - xl)
            out[y, x] = cl * (1 - t) + cr * t
    Image.fromarray((np.clip(out, 0, 1) * 255 + 0.5).astype(np.uint8), "RGB").save(OUT / "bg.png")
    # Anker: Mitte der untersten Maskenzeilen, ganzzahlig, damit der Steg in Ruhe pixelgenau auf der Platte liegt
    bottom_rows = sprite_mask[sy1 - 6:sy1]
    bc = np.nonzero(bottom_rows.any(axis=0))[0]
    ax = int(round((bc.min() + bc.max() + 1) / 2)) - sx0
    anchor = [float(padx + ax), float(padt + h)]
    meta = {"file": "props/jetty.png", "size": [canvas.shape[1], canvas.shape[0]], "anchor": anchor,
            "content_h": int(h), "at": [int(sx0 + ax), int(sy1)], "bend": bend, "squash": JETTY["squash"],
            "points": {}}
    print(f"jetty      {w}x{h} -> {canvas.shape[1]}x{canvas.shape[0]} anchor {anchor} at {meta['at']}")
    return meta


def build_props():
    rgba = g.load_rgba(RAW / "props.png")
    lab, _ = g.label(g.clean_alpha(rgba[..., 3]) > 0.5, min_px=50)
    (OUT / "props").mkdir(exist_ok=True)
    meta = {}
    for name, p in PROPS.items():
        x0, y0, x1, y1 = p["box"]
        part = cut_component(rgba, lab, p["box"])
        if "cut" in p:  # Boot: unter der Wasserlinie abschneiden
            part[p["cut"] - y0:, :, 3] = 0.0
            part = part[: p["cut"] - y0 + 1]
        small, (kx, ky) = scale_part(part, p["s"])
        h, w = small.shape[:2]
        # durchsichtiger Rand fürs Biegen und Strecken: seitlich Biegeweite + 15 %, oben 14 %
        bend = p.get("bend", 0.0)
        padx = int(np.ceil(bend * 1.6 + 0.08 * w + 6))
        padt = int(np.ceil(0.14 * h + 6))
        padb = 2
        canvas = np.zeros((h + padt + padb, w + 2 * padx, 4), np.float32)
        canvas[padt:padt + h, padx:padx + w] = small
        canvas = g.bleed(canvas)
        g.save_rgba(canvas, OUT / "props" / f"{name}.png")
        # Anker: Mitte der Standfläche (unterste deckende Zeilen) oder vorgegebenes x
        a = small[..., 3] > 0.5
        rows = np.nonzero(a.any(axis=1))[0]
        bottom = rows.max() + 1
        if "anchor_x" in p:
            ax = (p["anchor_x"] - x0) * kx
        elif "cut" in p:
            ax = w / 2
        else:
            cols = np.nonzero(a[max(0, bottom - 6):bottom].any(axis=0))[0]
            ax = (cols.min() + cols.max() + 1) / 2
        # ganzzahlig: Sprite-Ecke = at − anchor liegt dann auf ganzen Pixeln, in Ruhe keine Halbpixel-Unschärfe
        ax = float(round(ax))
        anchor = [float(padx + ax), float(padt + bottom)]
        pts = {k: [float(padx + (vx - x0) * kx), float(padt + (vy - y0) * ky)] for k, (vx, vy) in p["points"].items()}
        meta[name] = {"file": f"props/{name}.png", "size": [canvas.shape[1], canvas.shape[0]],
                      "anchor": [round(v, 2) for v in anchor], "content_h": int(bottom),
                      "at": list(p["at"]), "bend": bend, "squash": p.get("squash", 0.0),
                      "points": {k: [round(v, 2) for v in xy] for k, xy in pts.items()}}
        print(f"{name:10s} {w}x{h} -> {canvas.shape[1]}x{canvas.shape[0]} anchor {anchor}")
    return meta


def build_badger():
    rgba = patch_glove_wave(g.load_rgba(RAW / "badger.png"))
    lab, _ = g.label(g.clean_alpha(rgba[..., 3]) > 0.5, min_px=50)
    (OUT / "badger").mkdir(exist_ok=True)
    meta = {"scale": BS}
    for name, p in BADGER.items():
        x0, y0, x1, y1 = p["box"]
        part = cut_component(rgba, lab, p["box"])
        small, (kx, ky) = scale_part(part, BS)
        pad = 4
        canvas = np.zeros((small.shape[0] + 2 * pad, small.shape[1] + 2 * pad, 4), np.float32)
        canvas[pad:-pad, pad:-pad] = small
        canvas = g.bleed(canvas)
        g.save_rgba(canvas, OUT / "badger" / f"{name}.png")

        def tx(xy):
            return [round(pad + (xy[0] - x0) * kx, 2), round(pad + (xy[1] - y0) * ky, 2)]

        m = {"file": f"badger/{name}.png", "size": [canvas.shape[1], canvas.shape[0]], "anchor": tx(p["anchor"])}
        if "axis" in p:
            m["axis"] = list(p["axis"])
        if "points" in p:
            m["points"] = {k: tx(v) for k, v in p["points"].items()}
        meta[name] = m
        print(f"{name:11s} {canvas.shape[1]}x{canvas.shape[0]} anchor {m['anchor']}")
    # Fellfarbe der Gliedmaßen: Median des dunklen Fells am Rumpfboden (Seitenansicht)
    fur = rgba[880:930, 200:340]
    sel = (fur[..., 3] > 0.9) & (fur[..., :3].max(axis=2) < 0.35) & (fur[..., :3].max(axis=2) > 0.08)
    meta["fur"] = [round(float(v), 4) for v in np.median(fur[sel][:, :3], axis=0)]
    ink = rgba[..., :3][(rgba[..., 3] > 0.9) & (rgba[..., :3].max(axis=2) < 0.06)]
    meta["ink"] = [round(float(v), 4) for v in np.median(ink, axis=0)]
    print("fur", meta["fur"], "ink", meta["ink"])
    return meta


def build_glow():
    (OUT / "fx").mkdir(exist_ok=True)
    n = 128
    y, x = np.mgrid[0:n, 0:n]
    r = np.hypot(x - (n - 1) / 2, y - (n - 1) / 2) / (n / 2)
    a = np.clip(1 - r, 0, 1) ** 2.2
    img = np.zeros((n, n, 4), np.float32)
    img[..., :3] = 1.0
    img[..., 3] = a
    g.save_rgba(img, OUT / "fx" / "glow.png")


def main():
    scene = {"bg": build_bg(), "props": build_props(), "badger": build_badger()}
    scene["props"]["jetty"] = build_jetty()
    build_glow()
    (OUT / "scene.json").write_text(json.dumps(scene, indent=1))
    # nach demo/art kopieren
    if ART.exists():
        for f in ART.rglob("*.png"):
            f.unlink()
    for sub in ["props", "badger", "fx"]:
        (ART / sub).mkdir(parents=True, exist_ok=True)
        for f in (OUT / sub).glob("*.png"):
            shutil.copy2(f, ART / sub / f.name)
    shutil.copy2(OUT / "bg.png", ART / "bg.png")
    shutil.copy2(OUT / "scene.json", ART / "scene.json")
    print("ok")


if __name__ == "__main__":
    main()
