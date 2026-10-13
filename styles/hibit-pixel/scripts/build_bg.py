#!/usr/bin/env python3
"""Hintergrund für hibit-pixel: KI-Bild -> 640×360-Raster, Ebenen, Normal Maps, Wasser- und Lichtdaten.

    .venv/bin/python styles/hibit-pixel/scripts/build_bg.py

Eingaben: assets/raw/bg.png (Hintergrund), assets/raw/mask.png (dasselbe Bild „durchgepaust“: Himmel magenta,
Wasser cyan, Fernes gelb, Nahes unverändert).
Unterwegs: Fern-Inseln ohne Kontakt zu Himmel/Wasser (gelbes Glas, das die Maske als Fernes las) -> Nahes;
gemaltes Licht gedämpft (Fenster- und Laternenglas auf mittleren Bernsteinton, warmer Schein auf den Steinen um
das Fenster zur Mauerfarbe), damit PointLight2D und Lichthof das Leuchten liefern statt es zu verdoppeln.
Ausgaben (assets/ und demo/art/):
  bg_full.png        640×360, die eingerastete Szene als ein Bild (Ansicht, Vergleich)
  sky.png            Himmel, deckend (unter Fernem und Nahem zeilenweise aufgefüllt)
  far.png/_n.png     Fernes (Hügel, Inselchen, Landzunge mit Leuchtturm) + Normal Map
  water.png          Wasser, unter Booten, Steg und Felsen zeilenweise aufgefüllt (nur Quelle für den Zeilenversatz;
                     deckend macht der Shader es nur, wo layers.png Wasser zeigt)
  near.png/_n.png    Nahes (Häuschen, Kai, Steg, Boote, Requisiten) + Normal Map
  layers.png         Klassen als RGB-Maske (R Himmel, G Wasser, B Fernes) – Masken nie im Alpha
  bg.json            Lichtpunkte, Wasserzeilen, Palette, Messwerte
"""
import json, pathlib, sys

import numpy as np
from PIL import Image

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from hblib import (box_blur, dist_inside, encode_normals, kmeans, nearest, normals_from_height, oklab,
                   oklab_to_rgb, save_rgb, save_rgba)

ROOT = pathlib.Path(__file__).resolve().parents[1]
RAW = ROOT / "assets" / "raw"
OUT_A = ROOT / "assets"
OUT_D = ROOT / "demo" / "art"
OUT_D.mkdir(parents=True, exist_ok=True)

W, H = 640, 360
CROP_Y0 = 36                # 1536×864-Ausschnitt ab Zeile 36 (Schornstein 20 px unter dem Rand, Platz für Rauch)
SCALE = 1536 / W            # 2,4 Bildpixel je Zielpixel
K = 120                     # Farben der Hintergrundpalette
SKY, WATER, FAR, NEAR = 1, 2, 3, 0


def classify(mask):
    m = mask.astype(np.int32)
    d = lambda c: np.sqrt(((m - np.array(c)) ** 2).sum(-1))
    return np.select([d((255, 0, 255)) < 110, d((0, 255, 255)) < 110, d((255, 255, 0)) < 110],
                     [SKY, WATER, FAR], NEAR).astype(np.int64)


def retouch_smoke(rgb, cls):
    """Gemalten Schornsteinrauch durch Himmel derselben Zeilen 100 px weiter rechts ersetzen."""
    x0, x1, y0, y1 = 106, 197, 0, 85
    sky = cls[y0:y1, x0:x1] == SKY
    src = rgb[y0:y1, x0 + 100:x1 + 100]
    patch = rgb[y0:y1, x0:x1]
    patch[sky] = src[sky]
    return rgb


def reduce_layers(rgb, cls, lbl):
    """Je Zielzelle: Klasse per Mehrheit, Farbe = häufigster Paletten-Index nur unter Pixeln dieser Klasse."""
    Hs, Ws = lbl.shape
    sx, sy = Ws / W, Hs / H
    inset = 0.2
    out_i = np.zeros((H, W), np.int64)
    out_c = np.zeros((H, W), np.int64)
    for y in range(H):
        y0 = int(np.floor((y + inset) * sy)); y1 = max(y0 + 1, int(np.ceil((y + 1 - inset) * sy)))
        for x in range(W):
            x0 = int(np.floor((x + inset) * sx)); x1 = max(x0 + 1, int(np.ceil((x + 1 - inset) * sx)))
            c = cls[y0:y1, x0:x1].ravel()
            l = lbl[y0:y1, x0:x1].ravel()
            win = np.bincount(c, minlength=4).argmax()
            out_c[y, x] = win
            out_i[y, x] = np.bincount(l[c == win], minlength=K).argmax()
    return out_i, out_c


def absorb_enclosed_far(lay):
    """Fern-Flächen, die weder Himmel noch Wasser berühren, gehören zum Nahen.

    Die Maske lässt Nahes unverändert; helles gelbes Glas (Fenster, Laterne) liegt farblich nahe am Masken-Gelb
    und wurde als Fernes erkannt (164 Pixel in 30 Inseln). Echte Fern-Flächen grenzen immer an Himmel oder Wasser.
    """
    from collections import deque
    far = lay == FAR
    open_ = (lay == SKY) | (lay == WATER)
    seen = np.zeros_like(far)
    out = lay.copy()
    moved = 0
    for y0, x0 in zip(*np.nonzero(far)):
        if seen[y0, x0]:
            continue
        q, pts, touch = deque([(y0, x0)]), [], False
        seen[y0, x0] = True
        while q:
            y, x = q.popleft()
            pts.append((y, x))
            for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                v, u = y + dy, x + dx
                if 0 <= v < H and 0 <= u < W:
                    if far[v, u] and not seen[v, u]:
                        seen[v, u] = True
                        q.append((v, u))
                    elif open_[v, u]:
                        touch = True
        if not touch:
            ys, xs = zip(*pts)
            out[list(ys), list(xs)] = NEAR
            moved += len(pts)
    return out, moved


# Gemaltes Licht dämpfen (das Licht kommt in der Demo von PointLight2D und Lichthöfen):
# Glas auf einen mittleren Warmton, Schein auf den Steinen um das Fenster zur Mauerfarbe zurück.
WIN_GLASS = (84, 109, 159, 207)      # x0, x1, y0, y1 (Glas mit Sprossen)
WIN_OUTER = (81, 111, 156, 208)      # mit Rahmen
LANTERN_GLASS = (204, 222, 148, 167)
GLASS_DL = 0.17                      # Glas: so viel dunkler (Oklab-L), Licht und Lichthof bringen es zurück
GLOW_R = 22                          # Reichweite des gemalten Scheins um den Fensterrahmen (px)


def tone_down_painted_light(idx, lay, cent):
    lab = cent[idx]
    Lc, C = lab[..., 0], np.hypot(lab[..., 1], lab[..., 2])
    hue = np.degrees(np.arctan2(lab[..., 2], lab[..., 1]))
    near = lay == NEAR
    warm = (hue > 20) & (hue < 100) & (C > 0.045)
    used_near = np.unique(idx[near])
    pc = cent[used_near]
    pc_C = np.hypot(pc[:, 1], pc[:, 2])
    pc_h = np.degrees(np.arctan2(pc[:, 2], pc[:, 1]))
    amber_pal = used_near[(pc_h > 38) & (pc_h < 70) & (pc_C > 0.08)]   # Bernstein, kein Oliv/Gelbgrün
    yy, xx = np.mgrid[0:H, 0:W]
    out = idx.copy()
    stats = {}

    def snap(targets, allowed):
        d = ((targets[:, None, :] - cent[allowed][None]) ** 2).sum(-1)
        return allowed[d.argmin(1)]

    # 1) Glas: helle warme Pixel im Fenster- und Laternenglas -> mittlerer Bernsteinton (L um GLASS_DL dunkler)
    glass = np.zeros((H, W), bool)
    for x0, x1, y0, y1 in (WIN_GLASS, LANTERN_GLASS):
        glass[y0:y1, x0:x1] = True
    glass &= near & warm & (Lc > 0.55)
    t = lab[glass].copy()
    t[:, 0] -= GLASS_DL
    out[glass] = snap(t, amber_pal)
    stats["glass_px"] = int(glass.sum())

    # 2) Schein auf den Steinen: warme, helle Pixel nahe am Fensterrahmen -> Farbton/Sättigung der Mauer
    x0, x1, y0, y1 = WIN_OUTER
    dx = np.maximum(np.maximum(x0 - xx, xx - (x1 - 1)), 0)
    dy = np.maximum(np.maximum(y0 - yy, yy - (y1 - 1)), 0)
    d = np.hypot(dx, dy)
    zone = near & (d > 0) & (d <= GLOW_R)
    wall_ref = near & (yy >= 120) & (yy < 250) & (xx < 140) & (d > GLOW_R + 4) & (Lc > 0.45)
    ref_ab = np.median(lab[wall_ref][:, 1:], axis=0)
    glow = zone & warm & (Lc > 0.40)
    w = np.clip(1.0 - d / GLOW_R, 0, 1) ** 0.6
    t = lab[glow].copy()
    ww = w[glow][:, None]
    t[:, 1:] = t[:, 1:] + ww * (ref_ab[None] - t[:, 1:])
    t[:, 0] = t[:, 0] - 0.04 * ww[:, 0]
    out[glow] = snap(t, used_near)
    stats["glow_px"] = int(glow.sum())
    stats["wall_ref_ab"] = [round(float(v), 3) for v in ref_ab]
    return out, stats


def fill_rows(img, have):
    """Fehlende Pixel je Zeile mit dem nächsten vorhandenen Pixel derselben Zeile füllen (links/rechts)."""
    out = img.copy()
    for y in range(img.shape[0]):
        xs = np.flatnonzero(have[y])
        if xs.size == 0:
            continue
        miss = np.flatnonzero(~have[y])
        if miss.size == 0:
            continue
        j = np.searchsorted(xs, miss)
        left = xs[np.clip(j - 1, 0, len(xs) - 1)]
        right = xs[np.clip(j, 0, len(xs) - 1)]
        pick = np.where(np.abs(miss - left) <= np.abs(right - miss), left, right)
        out[y, miss] = img[y, pick]
    return out


def fill_cols_up(img, have):
    """Fehlende Pixel mit dem nächsten vorhandenen Pixel darüber füllen (Himmel hinter Fernem/Nahem)."""
    out = img.copy()
    ok = have.copy()
    for y in range(1, img.shape[0]):
        m = ~ok[y] & ok[y - 1]
        out[y][m] = out[y - 1][m]
        ok[y] |= m
    return out


def main():
    bg = np.asarray(Image.open(RAW / "bg.png").convert("RGB")).copy()
    cls = classify(np.asarray(Image.open(RAW / "mask.png").convert("RGB")))
    bg = retouch_smoke(bg, cls)
    y1 = CROP_Y0 + round(H * SCALE)
    bg, cls = bg[CROP_Y0:y1], cls[CROP_Y0:y1]

    lab = oklab(bg.reshape(-1, 3))
    rng = np.random.default_rng(3)
    smp = lab[rng.choice(len(lab), 150000, replace=False)]
    cent = kmeans(smp, K, iters=20, seed=3)
    lbl = nearest(lab, cent).reshape(bg.shape[:2])
    pal = np.clip(np.round(oklab_to_rgb(cent)), 0, 255).astype(np.uint8)
    idx, lay = reduce_layers(bg, cls, lbl)
    lay, moved = absorb_enclosed_far(lay)
    idx, retouch = tone_down_painted_light(idx, lay, cent)
    retouch["far_to_near_px"] = moved
    rgb = pal[idx]
    save_rgb(rgb, OUT_A / "bg_full.png")

    sky_m, water_m, far_m, near_m = (lay == SKY), (lay == WATER), (lay == FAR), (lay == NEAR)
    # Himmel deckend: unter Fernem/Nahem von oben fortsetzen
    sky = fill_cols_up(rgb, sky_m)
    save_rgb(sky, OUT_D / "sky.png")
    # Wasser: nur Wasserzeilen, unter Objekten je Zeile auffüllen
    rows = water_m.any(1)
    water = fill_rows(rgb, water_m)
    wa = np.zeros((H, W), np.uint8)
    first_water_row = int(np.flatnonzero(rows)[0])
    wa[first_water_row:, :] = 255
    wa[~rows] = 0
    save_rgba(np.dstack([water, wa]), OUT_D / "water.png")

    def layer(mask, name, strength, bevel):
        a = np.where(mask, 255, 0).astype(np.uint8)
        save_rgba(np.dstack([rgb, a]), OUT_D / f"{name}.png")
        L = oklab(rgb.reshape(-1, 3))[:, 0].reshape(H, W)
        # Höhe aus Helligkeit (fein + grob) plus Wölbung zum Rand jeder Ebene hin
        h = 0.65 * box_blur(L, 1) + 0.35 * box_blur(L, 3)
        h = h * 6.0 + bevel * np.minimum(dist_inside(mask, 4), 4) / 4.0
        h[~mask] = 0
        n = normals_from_height(h, strength)
        n[~mask] = (0, 0, 1)
        return n

    n_far = layer(far_m, "far", 1.4, 0.6)
    n_near = layer(near_m, "near", 2.2, 1.0)
    # Kai-Oberfläche: Fläche zeigt nach oben (Licht von der Laterne fällt von oben darauf)
    floor = np.zeros((H, W), bool)
    floor[QUAY_TOP[0]:QUAY_TOP[1], :] = True
    floor &= near_m
    tilt = np.array([0.0, 0.62, 0.78])
    nn = n_near[floor]
    nn = nn * 0.55 + tilt * 0.45
    n_near[floor] = nn / np.linalg.norm(nn, axis=1, keepdims=True)
    # Glanzkarte (Spekular): nasser Kai – helle Plattenoberseiten glänzen, Fugen nicht; sonst kein Glanz
    Lq = oklab(rgb.reshape(-1, 3))[:, 0].reshape(H, W)
    spec = np.zeros((H, W))
    spec[floor] = np.clip((Lq[floor] - 0.42) / 0.25, 0, 1) * 0.8
    save_rgb(np.dstack([spec, spec, spec]) * 255, OUT_D / "near_s.png")
    save_rgb(encode_normals(n_far), OUT_D / "far_n.png")
    save_rgb(encode_normals(n_near), OUT_D / "near_n.png")
    save_rgb(np.dstack([sky_m, water_m, far_m]).astype(np.uint8) * 255, OUT_D / "layers.png")

    info = {
        "size": [W, H], "crop_y0": CROP_Y0, "scale": SCALE, "palette_size": int(len(np.unique(idx))),
        "first_water_row": first_water_row, "quay_top": QUAY_TOP, "retouch": retouch,
        "share": {k: round(float(m.mean()), 3) for k, m in
                  (("sky", sky_m), ("water", water_m), ("far", far_m), ("near", near_m))},
    }
    (OUT_D / "bg.json").write_text(json.dumps(info, indent=1))
    for n in ("sky", "far", "far_n", "near", "near_n", "near_s", "water", "layers"):   # Kopie in assets/
        (OUT_A / f"{n}.png").write_bytes((OUT_D / f"{n}.png").read_bytes())
    print(json.dumps(info))


QUAY_TOP = (262, 292)

if __name__ == "__main__":
    main()
