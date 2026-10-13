#!/usr/bin/env python3
"""Plakatbild, Farbcode-Maske und Bootsplatte für die Art-déco-Demo.

    .venv/bin/python styles/art-deco/scripts/build_bg.py

Eingang: assets/raw/bg2.png (Plakat, gpt-image), assets/raw/mask.png (Farbcode-Maske, gpt-image mit bg2 als
Referenz, deckungsgleich).
Ausgang (assets/ und demo/art/):
  bg.png      Plakatbild 1536x1024 unverändert (Weltkoordinaten der Demo = Pixel dieses Bildes)
  mask.png    Maske mit exakten Codes (RGB, ohne Alpha), je Pixel der nächste Code, dann 3x3-Mehrheit;
              Lichter nach Lage getrennt: Fenster, Laterne, Leuchtfeuer, Sterne
  plate.png   Plakat ohne Boote: Bootpixel (Maske 2 px erweitert) zeilenweise aus dem Wasser links und rechts
              linear aufgefüllt (das Wasser besteht aus waagrechten Bändern, deshalb reicht das). Für das
              Schaukeln der Boote im Shader.
  scene.json  Lagen (Sonne, Lichter, Schornstein, Boote, Horizont, Kai) in Bildpixeln
"""
import json, pathlib
import numpy as np
from PIL import Image

ROOT = pathlib.Path(__file__).resolve().parents[1]
OUTS = [ROOT / "assets", ROOT / "demo/art"]

# Eingangscodes des KI-Bildes
IN_CODES = {"sky": (0, 0, 255), "cloud": (0, 255, 255), "sun": (255, 255, 0), "sea": (0, 255, 0),
            "boat": (255, 0, 0), "light": (255, 255, 255), "rest": (0, 0, 0)}
# Ausgangscodes (Shader: art/mask.png, filter_nearest)
OUT_CODES = {"sky": (0, 0, 255), "cloud": (0, 255, 255), "sun": (255, 255, 0), "sea": (0, 255, 0),
             "boat": (255, 0, 0), "window": (255, 128, 0), "lantern": (255, 0, 255), "lamp": (128, 0, 255),
             "star": (255, 255, 255), "rest": (0, 0, 0)}
# Lichter nach Lage (Rechtecke in Bildpixeln, von Hand aus den Zusammenhangsflächen der Maske abgelesen)
LIGHT_BOXES = {"window": (140, 480, 180, 592), "lantern": (1090, 536, 1130, 576), "lamp": (1335, 98, 1370, 127)}
BOAT_BOXES = [(805, 540, 965, 700), (1125, 525, 1320, 695)]


def mode_filter(lab, n):
    """3x3-Mehrheit über Labels 0..n-1 (bei Gleichstand gewinnt das bisherige Label)."""
    h, w = lab.shape
    pad = np.pad(lab, 1, mode="edge")
    counts = np.zeros((n, h, w), np.int16)
    for dy in range(3):
        for dx in range(3):
            win = pad[dy:dy + h, dx:dx + w]
            for k in range(n):
                counts[k] += win == k
    best = counts.argmax(0)
    keep = counts[lab, np.arange(h)[:, None], np.arange(w)[None, :]] >= counts.max(0)
    return np.where(keep, lab, best)


def dilate(b, r):
    out = b.copy()
    for dy in range(-r, r + 1):
        for dx in range(-r, r + 1):
            if dx * dx + dy * dy <= r * r:
                out |= np.roll(np.roll(b, dy, 0), dx, 1)
    return out


def main():
    bg = np.asarray(Image.open(ROOT / "assets/raw/bg2.png").convert("RGB"))
    mk = np.asarray(Image.open(ROOT / "assets/raw/mask.png").convert("RGB")).astype(np.int32)
    names = list(IN_CODES)
    C = np.array([IN_CODES[k] for k in names])
    d = ((mk[:, :, None, :] - C[None, None]) ** 2).sum(-1)
    lab = mode_filter(d.argmin(-1), len(names))
    h, w = lab.shape
    # Sonne nur links (83 verirrte gelbe Randpixel rechts -> Rest)
    sun_i, rest_i = names.index("sun"), names.index("rest")
    stray = (lab == sun_i) & (np.arange(w)[None, :] > 800)
    lab[stray] = rest_i

    out_names = list(OUT_CODES)
    olab = np.full((h, w), out_names.index("rest"), np.int32)
    for k in ("sky", "cloud", "sun", "sea", "boat", "rest"):
        olab[lab == names.index(k)] = out_names.index(k)
    light = lab == names.index("light")
    olab[light] = out_names.index("star")
    for k, (x0, y0, x1, y1) in LIGHT_BOXES.items():
        box = np.zeros_like(light)
        box[y0:y1, x0:x1] = True
        olab[light & box] = out_names.index(k)
    O = np.array([OUT_CODES[k] for k in out_names], np.uint8)
    mask_rgb = O[olab]

    # Bootsplatte
    boat = dilate(lab == names.index("boat"), 2)
    sea = (lab == names.index("sea")) & ~boat
    plate = bg.astype(np.float32).copy()
    for (x0, y0, x1, y1) in BOAT_BOXES:
        for y in range(y0, y1):
            row = boat[y, x0:x1]
            if not row.any():
                continue
            xs = np.nonzero(row)[0] + x0
            l, r = xs.min() - 1, xs.max() + 1
            while l > 0 and not sea[y, l]:
                l -= 1
            while r < w - 1 and not sea[y, r]:
                r += 1
            cl, cr = plate[y, l], plate[y, r]
            for x in xs:
                t = (x - l) / max(1, r - l)
                plate[y, x] = cl * (1 - t) + cr * t
    plate = plate.round().clip(0, 255).astype(np.uint8)

    def centre(k):
        ys, xs = np.nonzero(olab == out_names.index(k))
        return [round(float(xs.mean()), 1), round(float(ys.mean()), 1)]

    stars = []
    star = olab == out_names.index("star")
    ys, xs = np.nonzero(star)
    seen = np.zeros_like(star)
    for y, x in zip(ys, xs):
        if seen[y, x]:
            continue
        stack, pts = [(y, x)], []
        seen[y, x] = True
        while stack:
            a, b = stack.pop()
            pts.append((a, b))
            for c, e in ((a + 1, b), (a - 1, b), (a, b + 1), (a, b - 1)):
                if 0 <= c < h and 0 <= e < w and star[c, e] and not seen[c, e]:
                    seen[c, e] = True
                    stack.append((c, e))
        p = np.array(pts)
        stars.append([round(float(p[:, 1].mean()), 1), round(float(p[:, 0].mean()), 1), len(p)])
    boats = []
    for (x0, y0, x1, y1) in BOAT_BOXES:
        b = lab[y0:y1, x0:x1] == names.index("boat")
        ys, xs = np.nonzero(b)
        boats.append({"box": [int(xs.min() + x0), int(ys.min() + y0), int(xs.max() + x0), int(ys.max() + y0)]})
    scene = {
        "size": [w, h],
        "sun": {"centre": [575.6, 532.0], "ring_r": 171.3, "disc_r": 136.0,
                "note": "Kreis an die Oberkante des Rings angepasst (Maske), Scheibe ab y 396 bei x 573"},
        "horizon_y": 485,
        "quay_back_y": 712, "quay_front_y": 828,
        "window": centre("window"), "lantern": centre("lantern"), "lamp": centre("lamp"),
        "chimney_top": [92, 236],
        "stars": stars, "boats": boats,
        "mask_share": {k: round(float((olab == i).mean()), 4) for i, k in enumerate(out_names)},
    }
    for d in OUTS:
        d.mkdir(parents=True, exist_ok=True)
        Image.fromarray(bg).save(d / "bg.png")
        Image.fromarray(mask_rgb).save(d / "mask.png")
        Image.fromarray(plate).save(d / "plate.png")
        (d / "scene.json").write_text(json.dumps(scene, indent=1))
    print(json.dumps({k: scene[k] for k in ("window", "lantern", "lamp", "boats", "mask_share")}))
    print("Sterne:", len(stars))


if __name__ == "__main__":
    main()
