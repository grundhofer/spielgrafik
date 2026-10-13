#!/usr/bin/env python3
"""Zerlegt die KI-Figur in Puppenteile und schreibt Texturen + rig.json für die Godot-Demo.

Quellen (alle agy, 848x1264):
  raw/badger.png        Gesamtfigur (C1). Liefert nahen Arm, Paket und Bein; deckungsgleich mit:
  raw/badger_head.png   Teilbild "nur Kopf": das Modell behielt den ganzen Körper, malte aber Kopf ohne Schal
                        und eine Hals-Lasche. Daraus wird der Kopf nach Farbe und Zusammenhang geschnitten.
  raw/badger_body.png   Rumpf ohne Kopf, Arme und Beine, Schalende getrennt (Nachbesserung über eine grob
                        zerlegte Vorlage). Größer und verschoben: über die drei Westenknöpfe auf C1 eingepasst.

Alle Koordinaten unten sind C1-Pixel. Ausgabe im Texturmaßstab TEX (2x Bildschirmmaßstab), in Godot mit 0.5
gezeichnet. Schatten je Teil als weichgezeichnetes Alpha (schwarz).

    .venv/bin/python styles/papier-collage/scripts/prep_puppet.py
"""
import json, pathlib
from collections import deque
import numpy as np
from PIL import Image, ImageDraw, ImageFilter

from pc_util import despill_magenta, kill_magenta

HERE = pathlib.Path(__file__).resolve().parent.parent
RAW = HERE / "assets" / "raw"
OUT = HERE / "assets" / "puppet"
CHECK = HERE / "assets" / "check"
FIG_H = 190.0                 # Figurenhöhe im Bild (Mützenspitze bis Sohle), px
C1_TOP, C1_SOLE = 100, 1165   # in C1 gemessen
SCREEN = FIG_H / (C1_SOLE - C1_TOP)
TAB_TOP = 930                 # Oberkante der verdeckten Beinlasche (C1)
FAR = (30, -6)                # fernes Bein gegenüber dem nahen (C1-Pixel)
FAR_ARM = (60, -12)           # ferne Schulter gegenüber der nahen: so erreicht die ferne Pfote das Paket
ELBOW, ELBOW_R = (340, 700), 56   # Ellbogen 15 px über der Aufschlag-Unterkante, Scheibe unter dem Aufschlag
TEX = 2 * SCREEN


def load(name):
    rgba = np.asarray(Image.open(RAW / f"{name}.png").convert("RGBA")).astype(np.float64)
    return rgba


def components(mask):
    """Zusammenhangskomponenten (4er-Nachbarschaft), größte zuerst: Liste von Indexarrays."""
    H, W = mask.shape
    lab = np.zeros((H, W), np.int32)
    comps = []
    ys, xs = np.nonzero(mask)
    for y0, x0 in zip(ys, xs):
        if lab[y0, x0]:
            continue
        n = len(comps) + 1
        q = deque([(y0, x0)]); lab[y0, x0] = n; pts = []
        while q:
            y, x = q.popleft(); pts.append((y, x))
            for v, u in ((y + 1, x), (y - 1, x), (y, x + 1), (y, x - 1)):
                if 0 <= v < H and 0 <= u < W and mask[v, u] and not lab[v, u]:
                    lab[v, u] = n; q.append((v, u))
        comps.append(np.array(pts))
    comps.sort(key=len, reverse=True)
    return comps


def comp_mask(shape, pts):
    m = np.zeros(shape, bool)
    m[pts[:, 0], pts[:, 1]] = True
    return m


def fill_holes(m):
    """Löcher füllen: alles, was vom Rand aus nicht erreichbar ist."""
    outside = comps_from_border(~m)
    return ~outside


def comps_from_border(free):
    H, W = free.shape
    seen = np.zeros_like(free)
    q = deque()
    for x in range(W):
        for y in (0, H - 1):
            if free[y, x] and not seen[y, x]:
                seen[y, x] = True; q.append((y, x))
    for y in range(H):
        for x in (0, W - 1):
            if free[y, x] and not seen[y, x]:
                seen[y, x] = True; q.append((y, x))
    while q:
        y, x = q.popleft()
        for v, u in ((y + 1, x), (y - 1, x), (y, x + 1), (y, x - 1)):
            if 0 <= v < H and 0 <= u < W and free[v, u] and not seen[v, u]:
                seen[v, u] = True; q.append((v, u))
    return seen


def poly_mask(shape, poly):
    im = Image.new("L", (shape[1], shape[0]), 0)
    ImageDraw.Draw(im).polygon(poly, fill=255)
    return np.asarray(im) > 0


def disc_mask(shape, c, r):
    yy, xx = np.mgrid[0:shape[0], 0:shape[1]]
    return (xx - c[0]) ** 2 + (yy - c[1]) ** 2 <= r * r


def classes(rgb):
    r, g, b = rgb[..., 0], rgb[..., 1], rgb[..., 2]
    L = rgb.mean(-1)
    sat = rgb.max(-1) - rgb.min(-1)
    return dict(
        green=(g > r + 22) & (g > b + 12),
        cream=(r > 195) & (g > 185) & (r - b > 18) & (sat < 70),
        brown=(r > g + 22) & (g > b + 5) & (r < 215) & ~((r > 140) & (g < 100) & (r - g > 70)),
        red=(r > 140) & (g < 100) & (r - g > 70),
        yellow=(r > 170) & (g > 130) & (b < 110) & (r - b > 90),
        dark=(L < 100) & (sat < 30),
        grey=(L >= 100) & (L < 200) & (sat < 26),
        white=(L >= 200) & (sat < 26),
        L=L,
    )


def buttons(rgb, alpha, ymin):
    c = classes(rgb)
    m = c["yellow"] & alpha
    m[:ymin] = False
    pts = [p for p in components(m) if len(p) > 80][:3]
    cents = sorted([p.mean(0)[::-1] for p in pts], key=lambda v: v[1])
    return np.array(cents)


def piece(rgb, alpha, mask, name, pivots, origin=(0, 0)):
    """Schneidet ein Teil aus (C1-Raum), verkleinert auf TEX und speichert Textur + Schatten.

    pivots: Name -> (x, y) in C1-Pixeln. Rückgabe: Metadaten mit Drehpunkten in Texturpixeln."""
    ys, xs = np.nonzero(mask)
    pad = 24
    x0, y0, x1, y1 = xs.min() - pad, ys.min() - pad, xs.max() + pad + 1, ys.max() + pad + 1
    H, W = mask.shape
    canvas = np.zeros((y1 - y0, x1 - x0, 4))
    sx0, sy0 = max(x0, 0), max(y0, 0)
    sx1, sy1 = min(x1, W), min(y1, H)
    sub = np.zeros((sy1 - sy0, sx1 - sx0, 4))
    a = alpha[sy0:sy1, sx0:sx1] * mask[sy0:sy1, sx0:sx1]
    sub[..., :3] = rgb[sy0:sy1, sx0:sx1] * a[..., None]   # vormultipliziert verkleinern
    sub[..., 3] = a
    canvas[sy0 - y0:sy1 - y0, sx0 - x0:sx1 - x0] = sub
    w, h = canvas.shape[1], canvas.shape[0]
    tw, th = max(1, round(w * TEX)), max(1, round(h * TEX))
    chans = [Image.fromarray(canvas[..., i].astype(np.float32), "F").resize((tw, th), Image.LANCZOS)
             for i in range(4)]
    arr = np.stack([np.asarray(c) for c in chans], -1)
    A = np.clip(arr[..., 3], 0, 1)
    rgbo = np.where(A[..., None] > 1e-3, arr[..., :3] / np.maximum(A[..., None], 1e-3), 0)
    A = np.where(A > 0.985, 1.0, A)
    out = np.dstack([np.clip(rgbo, 0, 255), A * 255]).round().astype(np.uint8)
    Image.fromarray(out, "RGBA").save(OUT / f"{name}.png")
    # Schatten: Alpha, um 1,5 px (Bildschirm) weich, schwarz
    sh = Image.fromarray((A * 255).astype(np.uint8), "L")
    padw = 12
    big = Image.new("L", (tw + 2 * padw, th + 2 * padw), 0)
    big.paste(sh, (padw, padw))
    big = big.filter(ImageFilter.GaussianBlur(3.2))
    shadow = np.zeros((th + 2 * padw, tw + 2 * padw, 4), np.uint8)
    shadow[..., 3] = np.asarray(big)
    Image.fromarray(shadow, "RGBA").save(OUT / f"{name}_shadow.png")
    meta = {"file": f"{name}.png", "shadow": f"{name}_shadow.png", "size": [tw, th], "shadow_pad": padw,
            "origin_c1": [int(x0), int(y0)], "pivots": {}}
    for k, (px, py) in pivots.items():
        meta["pivots"][k] = [round((px - x0) * TEX, 2), round((py - y0) * TEX, 2)]
    return meta, out


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    CHECK.mkdir(parents=True, exist_ok=True)
    c1 = load("badger"); hd = load("badger_head"); bd = load("badger_body")
    shape = c1.shape[:2]
    rgb1, a1 = c1[..., :3], c1[..., 3] / 255.0
    a1 = kill_magenta(rgb1, a1, blue_over_green=40)
    rgb1 = despill_magenta(rgb1, a1)
    cl1 = classes(rgb1)

    # --- Rumpf (badger_body) auf C1 einpassen: Ähnlichkeit aus den drei Westenknöpfen
    rgbB, aB = bd[..., :3], bd[..., 3] / 255.0
    aB = kill_magenta(rgbB, aB, blue_over_green=40)
    rgbB = despill_magenta(rgbB, aB)
    kb1 = buttons(rgb1, a1 > 0.5, 400)
    kbB = buttons(rgbB, aB > 0.5, 300)
    mu1, muB = kb1.mean(0), kbB.mean(0)
    s = np.sqrt(((kb1 - mu1) ** 2).sum() / ((kbB - muB) ** 2).sum())
    t = mu1 - s * muB
    resid = np.abs((kbB * s + t) - kb1).max()
    print(f"Rumpf: Maßstab {s:.4f}, Versatz {t.round(1)}, Restfehler Knöpfe {resid:.1f} px")
    # Rumpfbild in C1-Raum transformieren (bikubisch, vormultipliziert)
    inv = (1 / s, 0, -t[0] / s, 0, 1 / s, -t[1] / s)
    pm = np.dstack([rgbB * aB[..., None], aB * 255])
    chans = [Image.fromarray(pm[..., i].astype(np.float32), "F").transform(
        (shape[1], shape[0]), Image.AFFINE, inv, resample=Image.BICUBIC) for i in range(4)]
    bw = np.stack([np.asarray(c) for c in chans], -1)
    aBw = np.clip(bw[..., 3] / 255.0, 0, 1)
    rgbBw = np.where(aBw[..., None] > 1e-3, bw[..., :3] / np.maximum(aBw[..., None], 1e-3), 0)
    compsB = components(aBw > 0.5)
    body_m = comp_mask(shape, compsB[0])
    scarf_m = comp_mask(shape, compsB[1])
    body_m = fill_holes(body_m)
    # Kante weich: Alpha selbst behalten, nur auf die Komponente beschränken (1 px geweitet)
    grow = lambda m: np.asarray(Image.fromarray(m.astype(np.uint8) * 255).filter(ImageFilter.MaxFilter(3))) > 0

    # --- Kopf aus badger_head (deckungsgleich mit C1)
    rgbH, aH = hd[..., :3], hd[..., 3] / 255.0
    aH = kill_magenta(rgbH, aH, blue_over_green=40)
    rgbH = despill_magenta(rgbH, aH)
    cH = classes(rgbH)
    yy, xx = np.mgrid[0:shape[0], 0:shape[1]]
    excl = (cH["green"] & (yy > 300)) | cH["cream"] | (cH["brown"] & (yy > 300)) | (cH["yellow"] & (yy > 320))
    cand = (aH > 0.5) & ~excl & (yy < 600)
    head_c = [p for p in components(cand) if ((p[:, 0] == 300) & (p[:, 1] == 450)).any()]
    head_m = comp_mask(shape, head_c[0] if head_c else components(cand)[0])
    head_m = fill_holes(head_m)

    # --- naher Arm aus C1
    roi = poly_mask(shape, [(236, 640), (242, 512), (284, 484), (356, 478), (412, 494), (432, 540), (434, 726),
                            (454, 790), (474, 860), (460, 930), (348, 930), (314, 872), (266, 792), (248, 728)])
    arm_c = roi & (a1 > 0.5) & (cl1["cream"] | cl1["dark"] | cl1["grey"] | cl1["white"])
    arm_m = fill_holes(comp_mask(shape, components(arm_c)[0]))
    # Am Ärmelrand teilen: Oberarm = Ärmel mit Aufschlag (Unterkante je Spalte, um Zeile 714-720), Unterarm =
    # Fell und Pfote darunter, oben mit einer Scheibe um den Ellbogen, die unter dem Aufschlag verborgen bleibt
    # (verdeckter Teil mit gespiegelten Fellzeilen von unterhalb des Aufschlags gefüllt).
    cream_arm = arm_m & cl1["cream"]
    split = np.full(shape[1], 716)
    for x in range(255, 406):
        ys = np.nonzero(cream_arm[690:730, x])[0]
        if len(ys):
            split[x] = 690 + ys.max()
    below = yy > split[None, :]
    uarm_m = arm_m & ~below
    farm_m = arm_m & below
    farm_rgb, farm_a = rgb1.copy(), a1.copy()
    elbow_disc = disc_mask(shape, ELBOW, ELBOW_R)
    for x in range(ELBOW[0] - ELBOW_R, ELBOW[0] + ELBOW_R + 1):
        for y in range(ELBOW[1] - ELBOW_R, split[x] + 7):     # samt gemaltem Aufschlag-Schatten darunter
            if elbow_disc[y, x]:
                src = split[x] + 10 + (split[x] - y) % 16      # unterhalb des Aufschlag-Schattens
                farm_rgb[y, x], farm_a[y, x] = rgb1[src, x], 1.0
    farm_m = farm_m | elbow_disc

    # --- Paket aus C1
    roi = (xx > 594) & (xx < 742) & (yy > 582) & (yy < 782)
    par_c = roi & (a1 > 0.5) & ~cl1["green"] & ~cl1["yellow"]
    parcel_m = fill_holes(comp_mask(shape, components(par_c)[0]))

    # --- nahes Bein aus C1: Unterschenkel + Fuß (heller als das ferne Bein), Lasche nach oben verlängert
    roi = (xx > 300) & (xx < 540) & (yy > 1050) & (yy < 1180)
    leg_c = roi & (a1 > 0.5) & (cl1["L"] >= 116) & (cl1["L"] < 235) & ~cl1["green"]
    leg_m = fill_holes(comp_mask(shape, components(leg_c)[0]))
    leg_rgb = rgb1.copy()
    leg_a = a1.copy()
    # Lasche: Zeilen ab 1064 nach oben spiegeln bis 930 (unter dem Hüftfell verborgen, Hüftstift bei 958)
    band_top = 1064
    cols = np.where(leg_m[band_top + 6])[0]
    xa, xb = cols.min(), cols.max()
    for y in range(TAB_TOP, band_top):
        src = band_top + (band_top - y) % 14
        leg_rgb[y, xa:xb + 1] = rgb1[src, xa:xb + 1]
        leg_a[y, xa:xb + 1] = 1.0
        leg_m[y, xa:xb + 1] = True
    # oben abrunden
    cx, cy, rr = (xa + xb) / 2, TAB_TOP + (xb - xa) / 2, (xb - xa) / 2
    leg_m &= ~((yy < cy) & ((xx - cx) ** 2 + (yy - cy) ** 2 > rr * rr))
    # Fuß und Schienbein am Knöchel trennen
    ankle = (int(round(cx)), 1100)
    disc = disc_mask(shape, ankle, 34)
    shin_m = leg_m & ((yy < ankle[1]) | disc)
    foot_m = leg_m & (yy >= ankle[1] - 34)
    hip = (cx, 958)

    # Drehpunkte (C1-Pixel)
    neck = (430, 470)
    SCARF_ATTACH = (276, 442)   # hintere Schalwicklung in C1, wo das Schalende darunter steckt
    shoulder = (334, 528)
    scarf_root = None
    ys, xs = np.nonzero(scarf_m)
    k = np.argmax(xs - 0.25 * ys)        # rechtes oberes Ende des Schalendes
    scarf_root = (float(xs[k]) - 10, float(ys[k]) + 14)

    meta = {"screen_scale": SCREEN, "tex_scale": TEX, "fig_h": FIG_H, "sole_c1": C1_SOLE,
            "body_fit": {"scale": s, "offset": t.tolist(), "button_residual_px": float(resid)}, "parts": {}}
    P = meta["parts"]
    P["body"], body_img = piece(rgbBw, aBw, grow(body_m) & (aBw > 0.02), "body",
                                {"root": hip, "neck": neck, "shoulder": shoulder, "hip_n": hip,
                                 "hip_f": (hip[0] + FAR[0], hip[1] + FAR[1]), "scarf": SCARF_ATTACH, "parcel": (600, 600)})
    P["scarf"], _ = piece(rgbBw, aBw, grow(scarf_m) & (aBw > 0.02), "scarf", {"root": scarf_root})
    P["head"], _ = piece(rgbH, aH, grow(head_m) & (aH > 0.02), "head", {"root": neck})
    P["upper_arm"], _ = piece(rgb1, a1, grow(uarm_m) & ~below & (a1 > 0.02), "upper_arm",
                              {"root": shoulder, "elbow": ELBOW})
    P["forearm"], _ = piece(farm_rgb, farm_a, (grow(farm_m) & (farm_a > 0.02)) & (below | elbow_disc), "forearm",
                            {"root": ELBOW})
    P["parcel"], _ = piece(rgb1, a1, grow(parcel_m) & (a1 > 0.02), "parcel", {"root": (600, 600)})
    P["shin"], _ = piece(leg_rgb, leg_a, shin_m, "shin", {"root": hip, "ankle": ankle})
    P["foot"], _ = piece(leg_rgb, leg_a, foot_m, "foot", {"root": ankle})
    meta["c1"] = {"neck": neck, "shoulder": shoulder, "elbow": ELBOW, "far_arm_shift": list(FAR_ARM),
                  "hip_n": hip, "hip_f": (hip[0] + FAR[0], hip[1] + FAR[1]),
                  "ankle_n": ankle, "scarf": SCARF_ATTACH, "scarf_root_body_img": scarf_root, "parcel": (600, 600), "sole": C1_SOLE,
                  "far_leg_shift": list(FAR)}
    (OUT / "rig.json").write_text(json.dumps(meta, indent=1))

    # Prüfbild: Ruhelage aus den Teilen neben C1 (C1-Raum, verkleinert)
    def put(canvas, m, rgb, a, dark=1.0, shift=(0, 0)):
        mm = np.roll(np.roll(m, shift[1], 0), shift[0], 1)
        rr = np.roll(np.roll(rgb, shift[1], 0), shift[0], 1)
        aa = np.roll(np.roll(a, shift[1], 0), shift[0], 1) * mm
        canvas[...] = canvas * (1 - aa[..., None]) + rr * dark * aa[..., None]
    comp = np.full(shape + (3,), 235.0)
    sh = (int(round(SCARF_ATTACH[0] - scarf_root[0])), int(round(SCARF_ATTACH[1] - scarf_root[1])))
    put(comp, scarf_m, rgbBw, aBw, 1.0, sh)
    put(comp, foot_m, leg_rgb, leg_a, 0.8, FAR); put(comp, shin_m, leg_rgb, leg_a, 0.8, FAR)
    put(comp, foot_m, leg_rgb, leg_a); put(comp, shin_m, leg_rgb, leg_a)
    put(comp, parcel_m, rgb1, a1)
    put(comp, head_m, rgbH, aH)
    put(comp, body_m, rgbBw, aBw)
    put(comp, farm_m, farm_rgb, farm_a)
    put(comp, uarm_m, rgb1, a1)
    ref = np.full(shape + (3,), 235.0)
    ref = ref * (1 - a1[..., None]) + rgb1 * a1[..., None]
    side = np.concatenate([ref, comp], 1).clip(0, 255).astype(np.uint8)
    im = Image.fromarray(side)
    d = ImageDraw.Draw(im)
    for nm, p in [("neck", neck), ("shoulder", shoulder), ("hip", hip), ("ankle", ankle), ("scarf", scarf_root)]:
        x, y = p[0] + shape[1], p[1]
        d.ellipse([x - 6, y - 6, x + 6, y + 6], outline=(255, 0, 0), width=3)
    im.save(CHECK / "rig_rest.png")
    print("ok", {k: v["size"] for k, v in P.items()})


if __name__ == "__main__":
    main()
