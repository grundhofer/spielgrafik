#!/usr/bin/env python3
"""Plakatbild (gpt-image, assets/raw/bg2.png) und Farbcode-Maske (assets/raw/mask.png) für die Demo aufbereiten.

    .venv/bin/python styles/jugendstil/scripts/build_bg.py

bg_far.png  bg.png auf die Fensterbreite der Totale verkleinert (Lanczos; Faktor aus assets/frame.json).
bg.png      bg2 mit PAD Zeilen Himmel oben angesetzt (die Bogenecke des Rahmens verdeckt sonst den Schornstein;
            die Szene sitzt deshalb PAD Zeilen tiefer im Fenster). Die angesetzten Zeilen sind die gespiegelten
            obersten Zeilen des Bildes, Sterne darin durch die Himmelsfarbe ersetzt.
mask.png    R = Code * 32 (0 Himmel, 1 Wolken, 2 Sonne, 3 Wasser, 4 Boote, 5 Lichter, 6 Rest),
            G = Licht-Nummer * 64 (1 Fenster, 2 Laterne, 3 Leuchtfeuer),
            B = Abstand eines Wasserpixels zum nächsten Nicht-Wasser-Pixel in px * 16 (höchstens 15 px):
                damit blendet der Wellen-Shader die Verschiebung an Horizont, Kai, Booten und Pfählen aus.
            Je Pixel der nächste Code (RGB-Abstand), danach zweimal 3x3-Mehrheit; Lichter nach Lage getrennt.
scene.json  Lagen in Pixeln von bg.png (also schon um PAD verschoben): Lichter, Schornstein, Horizont, Kai.
stars.png   eigene Sternmaske (RGB, nicht im Alphakanal): R = Gewicht 0..255 (Helligkeit über dem Himmel, an den
            kantengeglätteten Rändern weich), G = Phase des Sterns 1..255 (je Stern eine), B = 0.
            Sterne sind kleine, isolierte helle Goldflecken des Plakats: Zusammenhangskomponenten heller, gesättigter
            Goldpixel (Helligkeit > 0,45, R > B + 0,15, Sättigung > 0,25) mit höchstens STAR_MAX_PX Pixeln, oberhalb
            des Horizonts, deren Umgebungsring (3 px) zu mindestens 70 % die Himmelsfarbe hat und deren hellstes
            Pixel über 0,75 liegt. Wolkenspiralen und Wolkenbänder fallen damit heraus, egal welchen Code die
            KI-Maske dort hat (sie hat Innenflächen von Wolkenspiralen als Himmel eingetragen).
"""
import json, pathlib
import numpy as np
from PIL import Image

ROOT = pathlib.Path(__file__).resolve().parents[1]
OUTS = [ROOT / "assets", ROOT / "demo/art"]
PAD = 40
CODES = np.array([[0, 0, 255], [0, 255, 255], [255, 255, 0], [0, 255, 0], [255, 0, 0], [255, 255, 255], [0, 0, 0]])
SKY, CLOUD, SUN, WATER, BOAT, LIGHT, REST = range(7)
CHIMNEY_TOP = (125.0, 97.0)     # Mitte der Schornsteinkrone in bg2, an 4-fach vergrößertem Ausschnitt abgelesen
STAR_MAX_PX = 120               # größter Stern (vierzackig) hat 71 px; Wolkenflecken sind größer oder nicht isoliert
STAR_SEED = 19001012


def majority(lab, n, passes=2):
    for _ in range(passes):
        h, w = lab.shape
        pad = np.pad(lab, 1, mode="edge")
        cnt = np.zeros((n, h, w), np.int16)
        for dy in range(3):
            for dx in range(3):
                win = pad[dy:dy + h, dx:dx + w]
                for k in range(n):
                    cnt[k] += win == k
        lab = cnt.argmax(0)
    return lab


def components(b):
    h, w = b.shape
    lab = np.zeros((h, w), np.int32)
    out = []
    cur = 0
    for y0, x0 in zip(*np.nonzero(b)):
        if lab[y0, x0]:
            continue
        cur += 1
        st = [(y0, x0)]
        lab[y0, x0] = cur
        pts = []
        while st:
            y, x = st.pop()
            pts.append((y, x))
            for yy, xx in ((y + 1, x), (y - 1, x), (y, x + 1), (y, x - 1)):
                if 0 <= yy < h and 0 <= xx < w and b[yy, xx] and not lab[yy, xx]:
                    lab[yy, xx] = cur
                    st.append((yy, xx))
        out.append(np.array(pts))
    return out, lab


def grow(b, n):
    for _ in range(n):
        g = b.copy(); g[1:] |= b[:-1]; g[:-1] |= b[1:]; g[:, 1:] |= b[:, :-1]; g[:, :-1] |= b[:, 1:]; b = g
    return b


def star_mask(img, horizon):
    """Sterne als eigene Maske: kleine, isolierte, helle Goldflecken über dem Horizont (siehe Kopf)."""
    f = img.astype(np.float32) / 255.0
    r, g, b = f[..., 0], f[..., 1], f[..., 2]
    mx, mn = f.max(-1), f.min(-1)
    sat = (mx - mn) / np.maximum(mx, 1e-4)
    lum = 0.299 * r + 0.587 * g + 0.114 * b
    cand = (lum > 0.45) & (r > b + 0.15) & (sat > 0.25)
    cand[horizon - 40:] = False
    comps, _ = components(cand)
    sky = np.median(f[PAD + 20:PAD + 80, 300:900].reshape(-1, 3), 0)
    sky_lum = float(0.299 * sky[0] + 0.587 * sky[1] + 0.114 * sky[2])
    out = np.zeros(img.shape, np.uint8)
    rng = np.random.default_rng(STAR_SEED)
    stars = []
    for pts in comps:
        if len(pts) > STAR_MAX_PX:
            continue
        ys, xs = pts[:, 0], pts[:, 1]
        y0, y1, x0, x1 = max(0, ys.min() - 5), ys.max() + 6, max(0, xs.min() - 5), xs.max() + 6
        sub = np.zeros((y1 - y0, x1 - x0), bool)
        sub[ys - y0, xs - x0] = True
        ring = grow(sub, 3) & ~sub
        share = float((np.abs(f[y0:y1, x0:x1][ring] - sky).sum(-1) < 0.25).mean())
        peak = float(lum[ys, xs].max())
        if share < 0.7 or peak < 0.75:
            continue
        reg = grow(sub, 2)                               # mit kantengeglättetem Rand
        w = np.clip((lum[y0:y1, x0:x1] - sky_lum) / (peak - sky_lum), 0, 1) * reg
        ph = int(rng.integers(1, 256))
        o = out[y0:y1, x0:x1]
        o[..., 0] = np.maximum(o[..., 0], (w * 255 + 0.5).astype(np.uint8))
        o[..., 1] = np.where(reg, ph, o[..., 1])
        stars.append({"centre": [round(float(xs.mean()), 1), round(float(ys.mean()), 1)], "px": int(len(pts)),
                      "ring_sky": round(share, 2), "phase": ph})
    return out, stars


def main():
    bg = np.asarray(Image.open(ROOT / "assets/raw/bg2.png").convert("RGB"))
    m = np.asarray(Image.open(ROOT / "assets/raw/mask.png").convert("RGB")).astype(np.int32)
    H, W = bg.shape[:2]
    d = ((m[:, :, None, :] - CODES[None, None]) ** 2).sum(-1)
    lab = majority(d.argmin(-1), len(CODES))

    # Himmel oben ansetzen
    top = bg[:PAD][::-1].copy()
    sky = np.median(bg[:PAD].reshape(-1, 3), 0)
    t = top.astype(np.int32)
    star = (t[..., 0] > sky[0] + 40) | (np.abs(t - sky).sum(-1) > 90)
    # Sterne samt 3 px Rand durch Himmelsfarbe ersetzen
    sb = star.copy()
    for _ in range(3):
        g = sb.copy(); g[1:] |= sb[:-1]; g[:-1] |= sb[1:]; g[:, 1:] |= sb[:, :-1]; g[:, :-1] |= sb[:, 1:]; sb = g
    top[sb] = sky.astype(np.uint8)
    big = np.concatenate([top, bg], 0)
    lab = np.concatenate([np.full((PAD, W), SKY), lab], 0)

    # Lichter trennen
    comps, _ = components(lab == LIGHT)
    groups = {}
    lid = np.zeros(lab.shape, np.uint8)
    for pts in comps:
        if len(pts) < 8:
            lab[pts[:, 0], pts[:, 1]] = REST
            continue
        cy, cx = pts[:, 0].mean(), pts[:, 1].mean()
        if cx < 400:
            name, k = "window", 1
        elif cx < 900:
            name, k = "lantern", 2
        elif cy < 400:
            name, k = "lamp", 3                 # Laternenraum: Scheiben zwischen den Sprossen, mehrere Teile
        else:
            lab[pts[:, 0], pts[:, 1]] = REST     # Fensterchen des Wärterhauses: kein eigenes Licht
            continue
        lid[pts[:, 0], pts[:, 1]] = k
        groups.setdefault(name, []).append(pts)
    lights = {}
    for name, parts in groups.items():
        pts = np.concatenate(parts)
        y0, x0 = pts.min(0)
        y1, x1 = pts.max(0)
        lights[name] = {"centre": [round(float(pts[:, 1].mean()), 1), round(float(pts[:, 0].mean()), 1)],
                        "box": [int(x0), int(y0), int(x1), int(y1)], "px": int(len(pts)), "parts": len(parts)}

    # Abstand im Wasser zum Rand (Chebyshev, bis 15 px)
    water = lab == WATER
    dist = np.zeros(lab.shape, np.int32)
    cur = water.copy()
    for k in range(1, 16):
        dist[cur] = k
        e = cur.copy()
        e[1:] &= cur[:-1]; e[:-1] &= cur[1:]; e[:, 1:] &= cur[:, :-1]; e[:, :-1] &= cur[:, 1:]
        cur = e
    mask = np.zeros(lab.shape + (3,), np.uint8)
    mask[..., 0] = (lab * 32).astype(np.uint8)
    mask[..., 1] = lid * 64
    mask[..., 2] = np.clip(dist * 16, 0, 255).astype(np.uint8)

    # Horizont (oberste Wasserzeile in der Bildmitte) und hintere Kaikante (unterste Wasserzeile links vom Steg)
    wc = np.flatnonzero(water[:, 500:620].any(1))
    horizon = int(wc.min())
    quay_back = int(np.flatnonzero(water[:, 320:560].any(1)).max())
    stars_img, stars = star_mask(big, horizon)
    info = {"pad": PAD, "size": [W, H + PAD], "horizon_y": horizon, "quay_back_y": quay_back, "lights": lights,
            "stars": {"count": len(stars), "px": int((stars_img[..., 0] > 0).sum()), "list": stars},
            "chimney_top": [CHIMNEY_TOP[0], CHIMNEY_TOP[1] + PAD],
            "share": {n: round(float((lab == i).mean()), 4) for i, n in
                      enumerate(["sky", "cloud", "sun", "water", "boat", "light", "rest"])}}
    # Totale: dasselbe Bild vorab in Zielgröße verkleinert (Lanczos), damit Godot nicht unterabtastet
    lay = json.loads((ROOT / "assets/frame.json").read_text())["window"]
    zf = (lay["x1"] - lay["x0"] + 1) / W
    far = Image.fromarray(big).resize((round(W * zf), round((H + PAD) * zf)), Image.LANCZOS)
    info["far"] = {"zoom": zf, "size": list(far.size)}
    for o in OUTS:
        o.mkdir(parents=True, exist_ok=True)
        Image.fromarray(big).save(o / "bg.png")
        far.save(o / "bg_far.png")
        Image.fromarray(mask).save(o / "mask.png")
        Image.fromarray(stars_img).save(o / "stars.png")
        (o / "scene.json").write_text(json.dumps(info, indent=1))
    print(json.dumps(info, indent=1))


if __name__ == "__main__":
    main()
