#!/usr/bin/env python3
"""Zerlegt das KI-Scherenschnittbild (assets/raw/bg.png) in Tiefenebenen für Godot.

Das Bild hat fünf flache Töne: Weiß (Himmel, See, Schnitte), Hellgrau (Ferne), Grau 94 (Landzunge,
Leuchtturm), Grau 68 (Steg, Boote) und Schwarz (Kai, Haus, Laterne, Fässer). Jeder Ton wird eine Ebene,
die Godot einzeln einfärbt (Nebel nach Tiefe). Ablauf:

1. Rot des Leuchtturmbands auf Grau 94 setzen (Bandmaske merken), gemalte Rauchfahne löschen.
2. Auf 2x vergrößern (bikubisch) und Töne zuordnen: "Kernpixel" (ruhige 3x3-Umgebung) zum nächsten Ton,
   Kantenpixel nur zu Tönen, deren Kernpixel in der Nähe liegen (sonst würden Kanten Schwarz/Weiß als
   graue Säume in die Mittelebenen fallen).
3. Hintere Ebenen 3 px (Quellmaß) unter die vorderen ziehen, damit an Ebenengrenzen keine Lichtnaht entsteht.
4. Wolken und Boote als eigene Sprites ausschneiden (driften bzw. schaukeln), Fensterscheiben, Laternenglas
   und Lampenraum als Lichtmasken (eingeschlossene weiße Löcher).
5. Auf 1280x720 verkleinern (Zeilen 80..791 der Quelle, Faktor 1280/1264): Flächenmittel ergibt die Kantenglättung.

    .venv/bin/python styles/silhouette-scherenschnitt/scripts/prep_bg.py
"""
import json, pathlib, collections
import numpy as np
from PIL import Image, ImageDraw, ImageFilter

SD = pathlib.Path(__file__).resolve().parents[1]
RAW = SD / "assets" / "raw" / "bg.png"
OUT = SD / "assets" / "layers"
DEMO = SD / "demo" / "art"
CHECK = SD / "assets" / "check"
for d in (OUT, DEMO, CHECK):
    d.mkdir(parents=True, exist_ok=True)

K = 2                      # Arbeitsauflösung = 2x Quelle
CROP_Y0, CROP_H = 80, 711  # Quellzeilen für 16:9
W_OUT, H_OUT = 1280, 720
S = W_OUT / 1264.0         # Quelle -> Bild

TONES = np.array([255, 188, 94, 68, 1], float)   # Index = Ebene: 0 weiß, 1 fern, 2 Landzunge, 3 Steg, 4 vorn
NAMES = ["white", "far", "head", "jetty", "front"]


def to_disp(x, y):
    return x * S, (y - CROP_Y0) * S


def main():
    rgb = np.asarray(Image.open(RAW).convert("RGB")).astype(np.float32)
    H, W = rgb.shape[:2]
    lum = rgb[..., 0] * 0.299 + rgb[..., 1] * 0.587 + rgb[..., 2] * 0.114
    sat = rgb.max(2) - rgb.min(2)
    red = (sat > 40) & (rgb[..., 0] > rgb[..., 1] + 40)
    red_soft = np.asarray(Image.fromarray((red * 255).astype(np.uint8)).filter(ImageFilter.MaxFilter(3))) > 0
    lum[red_soft & (lum < 200)] = TONES[2]
    # gemalte Rauchfahne über dem Schornstein (Topfoberkante Zeile 167) entfernen
    smoke = np.zeros_like(red)
    smoke[100:166, 100:330] = True
    lum[smoke] = 255.0
    lum[166, 100:268] = 255.0
    lum[166, 296:330] = 255.0

    # 2x bikubisch
    L = np.asarray(Image.fromarray(lum.clip(0, 255).astype(np.uint8)).resize((W * K, H * K), Image.BICUBIC)).astype(np.float32)
    Li = Image.fromarray(L.astype(np.uint8))
    rng = np.asarray(Li.filter(ImageFilter.MaxFilter(5))).astype(np.float32) - np.asarray(Li.filter(ImageFilter.MinFilter(5)))
    core = rng < 22
    near = np.abs(L[..., None] - TONES[None, None, :])
    nearest = near.argmin(2)
    label = np.full(L.shape, -1, int)
    label[core] = nearest[core]
    cand = []
    for t in range(5):
        m = Image.fromarray(((label == t) * 255).astype(np.uint8)).filter(ImageFilter.MaxFilter(9))
        cand.append(np.asarray(m) > 0)
    cand = np.stack(cand, 2)
    big = np.where(cand, near, 1e9)
    edge_lab = big.argmin(2)
    none = ~cand.any(2)
    edge_lab[none] = nearest[none]
    label[~core] = edge_lab[~core]
    # Steg und Boote (links von x 900) sind im KI-Bild teils Grau 94 statt 68: dort alles Mittelgrau = Steg
    mid_left = np.zeros(label.shape, bool)
    mid_left[:, :900 * K] = True
    label[mid_left & (label == 2)] = 3

    # Ferne und Landzunge sind große Flächen: vereinzelte Pixel dieser Töne ohne eigenen Kern in der Nähe
    # sind Kantenglättung dünner Schnitte im Schwarz (Dachschuppen, Fugen) -> Loch oder Papier.
    for t in (1, 2):
        stray = (label == t) & ~cand[..., t]
        label[stray] = np.where(L[stray] > 128, 0, 4)

    # Lichtlöcher: weiße Pixel, die nicht mit dem Außenraum verbunden sind
    # .copy(): floodfill auf einem Bild aus Image.fromarray ändert sonst nichts (geteilter Speicher)
    white = Image.fromarray(((label == 0) * 255).astype(np.uint8)).copy()
    ImageDraw.floodfill(white, (5, 5), 128)            # Himmel
    ImageDraw.floodfill(white, (800 * K, 600 * K), 128)  # See (vom Horizontstrich eingeschlossen)
    holes = np.asarray(white) == 255

    def box(x0, y0, x1, y1):
        m = np.zeros(label.shape, bool)
        m[int(y0 * K):int(y1 * K), int(x0 * K):int(x1 * K)] = True
        return m

    lights = {
        "window": holes & box(196, 450, 296, 560),
        "lantern": holes & box(790, 380, 846, 455),
        "lamp": holes & box(1092, 170, 1150, 218),
    }

    # Wolken = helle Töne oberhalb Zeile 240, in Zusammenhangskomponenten
    yy, xx = np.mgrid[0:label.shape[0], 0:label.shape[1]]
    cloud_all = (label == 1) & (yy < 240 * K)
    clouds = components(cloud_all, min_px=400)

    # Boote: Grau-68-Pixel in den Bootsbereichen; rechtes Boot ab x 668 bzw. unterhalb der Pfostenunterkante
    jetty_all = label == 3
    boat_l = jetty_all & box(420, 370, 580, 512) & ~box(512, 488, 532, 512)
    rb = box(636, 372, 792, 600)
    boat_r = jetty_all & rb & ((xx >= 668 * K) | (yy >= 546 * K))
    # Linkes Boot: der vordere Pfosten (x 515..528) gehört zum Steg
    post = jetty_all & box(512, 488, 532, 600)
    boat_l &= ~post

    masks = {
        "far": (label == 1) & ~cloud_all,
        "head": label == 2,
        "jetty": jetty_all & ~boat_l & ~boat_r,
        "front": label == 4,
    }
    # hintere Ebenen 3 px (Quellmaß) unter die vorderen ziehen
    order = ["far", "head", "jetty", "front"]
    nearer_of = {"far": [2, 3, 4], "head": [3, 4], "jetty": [4]}
    for name in ("far", "head", "jetty"):
        m = masks[name]
        grown = np.asarray(Image.fromarray((m * 255).astype(np.uint8)).filter(ImageFilter.MaxFilter(2 * 3 * K + 1))) > 0
        nearer = np.isin(label, nearer_of[name])
        masks[name] = m | (grown & nearer)
    band = np.asarray(Image.fromarray((red_soft * 255).astype(np.uint8)).resize((W * K, H * K), Image.NEAREST)) > 0

    meta = {"size": [W_OUT, H_OUT], "source": "assets/raw/bg.png", "crop_rows": [CROP_Y0, CROP_Y0 + CROP_H],
            "scale": S, "work_scale": K}

    def full(m, name):
        im = mask_to_disp(m)
        save_white_alpha(im, name)
        return im

    for name in order:
        full(masks[name], f"layer_{name}")
    meta["layer_band"] = crop_saved(full(band & (label == 2), "layer_band"), "layer_band")
    for name, m in lights.items():
        grown = np.asarray(Image.fromarray((m * 255).astype(np.uint8)).filter(ImageFilter.MaxFilter(2 * 2 * K + 1))) > 0
        lpos = crop_saved(full(grown, f"light_{name}"), f"light_{name}")
        ys, xs = np.where(m)
        cx, cy = to_disp(xs.mean() / K, ys.mean() / K)
        meta[f"light_{name}"] = {"center": [round(cx, 1), round(cy, 1)], "px_src": int(m.sum() / K / K),
                                 "bbox": [round(v, 1) for v in (*to_disp(xs.min() / K, ys.min() / K), *to_disp(xs.max() / K, ys.max() / K))],
                                 **lpos}

    # Sprites mit Position (oben links in Bildkoordinaten)
    meta["clouds"] = []
    for i, c in enumerate(clouds):
        c = taper_cut_ends(c)
        meta["clouds"].append(save_sprite(c, f"cloud_{i}"))
    meta["boat_l"] = save_sprite(boat_l, "boat_l")
    meta["boat_r"] = save_sprite(boat_r, "boat_r")
    # Wasserlinien: unterste Rumpfzeile je Boot (Bildmaß)
    for k, m in (("boat_l", boat_l), ("boat_r", boat_r)):
        ys, xs = np.where(m)
        meta[k]["keel_y"] = round(to_disp(0, ys.max() / K)[1], 1)
        meta[k]["center_x"] = round(to_disp(np.median(xs) / K, 0)[0], 1)

    # Messwerte für die Szene
    meta["horizon_y"] = round(to_disp(0, 355)[1], 1)
    fr = label == 4
    col = fr[:, int(600 * K)]
    meta["quay_y"] = round(to_disp(0, np.argmax(col) / K)[1], 1)
    meta["chimney_top"] = [round(v, 1) for v in to_disp(281, 167)]
    # Wasserlinie der Landzunge je 16-px-Spalte (für die Spiegelung im Wasser), 0 = keine Landzunge
    ha = np.asarray(Image.open(OUT / "layer_head.png"))[..., 3]
    wl = []
    for cx in range(8, W_OUT, 16):
        rows = np.where(ha[:, cx] > 128)[0]
        wl.append(float(rows.max() + 1) if len(rows) and rows.max() > meta["horizon_y"] else 0.0)
    meta["head_waterline16"] = wl
    meta["counts_src_px"] = {n: int((label == i).sum() / K / K) for i, n in enumerate(NAMES)}
    meta["edge_px_share"] = round(float((~core).mean()), 4)
    (SD / "assets" / "scene.json").write_text(json.dumps(meta, indent=1))
    (DEMO / "scene.json").write_text(json.dumps(meta, indent=1))

    # Prüfbild: Ebenen in Falschfarben
    pal = np.array([[255, 255, 255], [120, 200, 120], [90, 120, 220], [220, 90, 90], [0, 0, 0]], np.uint8)
    vis = pal[label]
    for m, c in ((cloud_all, (40, 160, 40)), (boat_l, (240, 160, 0)), (boat_r, (240, 160, 0))):
        vis[m] = c
    for m in lights.values():
        vis[m] = (255, 220, 0)
    Image.fromarray(vis).resize((W_OUT, int(H * S)), Image.LANCZOS).save(CHECK / "layers_falschfarben.png")
    print(json.dumps({k: meta[k] for k in ("horizon_y", "quay_y", "counts_src_px", "edge_px_share")}, indent=1))
    print("Wolken:", len(clouds), "Lichter:", {k: meta[f'light_{k}']['px_src'] for k in lights})


def components(mask, min_px=100):
    """Zusammenhangskomponenten (8er-Nachbarschaft) per Flutfüllung in PIL."""
    img = Image.fromarray((mask * 255).astype(np.uint8))
    out = []
    ys, xs = np.where(mask)
    seen = np.zeros(mask.shape, bool)
    for y, x in zip(ys[::50], xs[::50]):
        if seen[y, x]:
            continue
        tmp = img.copy()
        ImageDraw.floodfill(tmp, (int(x), int(y)), 77)
        comp = np.asarray(tmp) == 77
        seen |= comp
        if comp.sum() >= min_px:
            out.append(comp)
    out.sort(key=lambda m: np.where(m)[1].min())
    return out


def taper_cut_ends(m, T=90 * K):
    """Wolken, die das KI-Bild am Rand abschneidet, laufen spitz aus (sie driften später ins Bild)."""
    ys, xs = np.where(m)
    W = m.shape[1]
    out = m.copy()
    for edge, inside in ((xs.min() <= 1, lambda x: x - xs.min()), (xs.max() >= W - 2, lambda x: xs.max() - x)):
        if not edge:
            continue
        for x in range(xs.min(), xs.max() + 1):
            d = inside(x)
            if d >= T:
                continue
            col = np.where(m[:, x])[0]
            if not len(col):
                continue
            yc, hh = (col.min() + col.max()) / 2, (col.max() - col.min()) / 2
            keep = hh * (d / T) ** 0.7
            yy = np.arange(m.shape[0])
            out[:, x] &= np.abs(yy - yc) <= keep
    return out


def crop_saved(a_img, name, pad=2):
    """Kleine Ebenen (Lichter, Leuchtturmband) auf ihren Umriss zuschneiden: spart Überzeichnung."""
    a = np.asarray(a_img)
    ys, xs = np.where(a > 0)
    x0, y0 = max(0, xs.min() - pad), max(0, ys.min() - pad)
    x1, y1 = min(a.shape[1], xs.max() + pad + 1), min(a.shape[0], ys.max() + pad + 1)
    save_white_alpha(Image.fromarray(a[y0:y1, x0:x1]), name)
    return {"file": f"{name}.png", "pos": [int(x0), int(y0)], "size": [int(x1 - x0), int(y1 - y0)]}


def mask_to_disp(m):
    """2x-Maske (volle Quelle) -> 1280x720 mit Flächenmittel."""
    im = Image.fromarray((m * 255).astype(np.uint8))
    im = im.crop((0, CROP_Y0 * K, im.width, (CROP_Y0 + CROP_H) * K))
    return im.resize((W_OUT, H_OUT), Image.BOX)


def save_white_alpha(a_img, name):
    a = np.asarray(a_img)
    rgba = np.zeros(a.shape + (4,), np.uint8)
    rgba[..., :3] = 255
    rgba[..., 3] = a
    Image.fromarray(rgba).save(OUT / f"{name}.png", optimize=True)
    Image.fromarray(rgba).save(DEMO / f"{name}.png", optimize=True)


def save_sprite(m, name, pad=4):
    """Sprite aus 2x-Maske: auf Bildmaß verkleinert, Position der linken oberen Ecke im Bild."""
    ys, xs = np.where(m)
    x0, x1 = max(0, xs.min() - pad * K), min(m.shape[1], xs.max() + pad * K)
    y0, y1 = max(0, ys.min() - pad * K), min(m.shape[0], ys.max() + pad * K)
    # an das Bildraster der Ausgabe ausrichten, damit nichts verschoben wird
    f = S / K
    dx0, dy0 = int(np.floor(x0 * f)), int(np.floor((y0 - CROP_Y0 * K) * f))
    dx1, dy1 = int(np.floor(x1 * f)), int(np.floor((y1 - CROP_Y0 * K) * f))
    sx0, sy0 = dx0 / f, dy0 / f + CROP_Y0 * K
    sx1, sy1 = dx1 / f, dy1 / f + CROP_Y0 * K
    im = Image.fromarray((m * 255).astype(np.uint8)).resize((dx1 - dx0, dy1 - dy0), Image.BOX, box=(sx0, sy0, sx1, sy1))
    save_white_alpha(im, name)
    return {"file": f"{name}.png", "pos": [dx0, dy0], "size": [dx1 - dx0, dy1 - dy0]}


if __name__ == "__main__":
    main()
