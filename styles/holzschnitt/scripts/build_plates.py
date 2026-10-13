#!/usr/bin/env python3
"""Farbauszug des KI-Hintergrunds in drei Druckplatten + Bereichsmaske für die Effekte.

    .venv/bin/python styles/holzschnitt/scripts/build_plates.py

Eingang:  assets/raw/bg2.png  (gpt-image, dreifarbiger Holz-/Linolschnitt)
          assets/raw/mask.png (gpt-image, Farbcode-Maske mit bg2.png als Referenz, deckungsgleich)
Ausgang (assets/ und demo/art/):
  plates_bg.png  1160x580 RGB: R = Schwarzstock, G = Petrol, B = Zinnober (Deckung, an Kanten weich; der
                 Druck-Shader schneidet sie nach dem Wackeln wieder scharf). Mit gestochenem Rand (Schwarz).
  regions.png    1160x580 RGB, Nearest: R = Wasser, G = Himmel, B = Code (64 Laternenglas, 128 Leuchtfeuer,
                 192 Fenster, 255 Schornstein)
  scene.json     Lage der Lichter, des Schornsteins und der Laufzeile in Druckstock-Koordinaten
  ref/sep_preview.png  Vorschau des Farbauszugs mit flachen Druckfarben (nur zur Prüfung)
"""
import json, pathlib
import numpy as np
from PIL import Image

import inklib

ROOT = pathlib.Path(__file__).resolve().parents[1]
RAW = ROOT / "assets/raw"
OUTS = [ROOT / "assets", ROOT / "demo/art"]

# Ausschnitt im KI-Bild und Größe des Druckstocks auf dem Bildschirm (Faktor 1160/1476 = 0,786)
CROP = (30, 120, 1506, 858)
SIZE = (1160, 580)

# Farben im KI-Bild (k-means über raw/bg2.png, 10 Gruppen) -> Platten (K, T, O).
# Das Modell hat außer den drei Druckfarben noch Holzbraun und Steingrau gemalt. Holzbraun druckt im Zinnober,
# aber nur auf Holz und Booten (Maske), sonst Schwarz bzw. Papier: so werden Fässer, Kisten, Laternenpfahl und
# Boote orange, die Kantsteine und die Kaimauer bleiben Papier mit schwarzen Schnitten.
SEP = [
    ("black",     (7, 8, 7),       (1, 0, 0)),
    ("black2",    (18, 19, 17),    (1, 0, 0)),
    ("paper",     (238, 199, 150), (0, 0, 0)),
    ("paper2",    (245, 213, 165), (0, 0, 0)),
    ("teal",      (44, 107, 114),  (0, 1, 0)),
    ("teal_dark", (25, 68, 73),    (0, 1, 0)),
    ("orange",    (240, 102, 30),  (0, 0, 1)),
    ("tan",       (192, 155, 111), (0, 0, 0)),
    ("brown",     (86, 58, 37),    None),      # Holz: O, sonst K
    ("lbrown",    (133, 99, 66),   None),      # Holz: O, sonst Papier
]
MASK_CODES = {"sky": (0, 0, 255), "water": (0, 255, 255), "boats": (255, 0, 255), "wood": (255, 255, 255),
              "window": (255, 255, 0), "lantern": (255, 128, 0), "lamp": (255, 0, 0), "chimney": (0, 255, 0),
              "other": (0, 0, 0)}


def mask_index(m):
    names = list(MASK_CODES)
    cen = np.array([MASK_CODES[n] for n in names])
    d = ((m[:, :, None, :].astype(int) - cen[None, None]) ** 2).sum(-1)
    return names, d.argmin(-1)


def largest_component(b):
    """Größte 4-zusammenhängende Fläche einer Bool-Maske (Mischpixel an Codegrenzen fallen weg)."""
    h, w = b.shape
    lab = np.zeros((h, w), np.int32)
    best, best_n, cur = None, 0, 0
    ys, xs = np.nonzero(b)
    for y0, x0 in zip(ys, xs):
        if lab[y0, x0]:
            continue
        cur += 1
        stack, pts = [(y0, x0)], []
        lab[y0, x0] = cur
        while stack:
            y, x = stack.pop()
            pts.append((y, x))
            for yy, xx in ((y + 1, x), (y - 1, x), (y, x + 1), (y, x - 1)):
                if 0 <= yy < h and 0 <= xx < w and b[yy, xx] and not lab[yy, xx]:
                    lab[yy, xx] = cur
                    stack.append((yy, xx))
        if len(pts) > best_n:
            best_n, best = len(pts), cur
    return lab == best if best else np.zeros_like(b)


def resize_f(a, size, resample=Image.BOX):
    return np.asarray(Image.fromarray(a.astype(np.float32), "F").resize(size, resample))


def save(name, img):
    for d in OUTS:
        d.mkdir(parents=True, exist_ok=True)
        img.save(d / name)
    print("ok", name, img.size)


def main():
    bg = np.asarray(Image.open(RAW / "bg2.png").convert("RGB"))
    mk = np.asarray(Image.open(RAW / "mask.png").convert("RGB"))
    names, midx = mask_index(mk)
    is_wood = (midx == names.index("wood")) | (midx == names.index("boats"))

    idx = inklib.majority3(inklib.classify(bg, SEP), len(SEP))
    lut = np.array([s[2] if s[2] else (0, 0, 0) for s in SEP], np.float32)
    pl = lut[idx]
    brown, lbrown = idx == 8, idx == 9
    pl[brown & is_wood] = (0, 0, 1)
    pl[brown & ~is_wood] = (1, 0, 0)
    pl[lbrown & is_wood] = (0, 0, 1)
    shares = {s[0]: round(float((idx == i).mean()), 4) for i, s in enumerate(SEP)}

    # Ausschnitt und Verkleinern je Platte (Flächenmittel = Deckung)
    x0, y0, x1, y1 = CROP
    pl = pl[y0:y1, x0:x1]
    W, H = SIZE
    out = np.stack([resize_f(pl[..., c], SIZE) for c in range(3)], -1)

    # Stockrand: 5 px Schwarz, innen unregelmäßig wie mit dem Messer geschnitten (fester Seed)
    rng = np.random.default_rng(1921)
    def jag(n):
        v = np.cumsum(rng.normal(0, 0.35, n))
        v = v - np.convolve(v, np.ones(41) / 41, mode="same")
        return 4.5 + np.clip(v, -1.6, 1.6)
    yy, xx = np.mgrid[0:H, 0:W]
    top, bot, lef, rig = jag(W), jag(W), jag(H), jag(H)
    border = (yy < top[xx]) | (yy > H - 1 - bot[xx]) | (xx < lef[yy]) | (xx > W - 1 - rig[yy])
    out[border] = (1, 0, 0)
    save("plates_bg.png", Image.fromarray(np.clip(out * 255 + 0.5, 0, 255).astype(np.uint8)))

    # Bereichsmaske (Nearest auf Stockgröße)
    mc = midx[y0:y1, x0:x1]
    small = np.asarray(Image.fromarray(mc.astype(np.uint8)).resize(SIZE, Image.NEAREST))
    reg = np.zeros((H, W, 3), np.uint8)
    reg[..., 0] = np.where(small == names.index("water"), 255, 0)
    reg[..., 1] = np.where(small == names.index("sky"), 255, 0)
    inner = ~(border | np.roll(border, 3, 0) | np.roll(border, -3, 0) | np.roll(border, 3, 1) | np.roll(border, -3, 1))
    reg[..., 0] *= inner
    reg[..., 1] *= inner          # Effekte schneiden nicht in den Stockrand
    scene = {"block": {"x": 60, "y": 18, "w": W, "h": H}, "crop": CROP, "scale": W / (x1 - x0), "ai_shares": shares}
    for code, val in (("lantern", 64), ("lamp", 128), ("window", 192), ("chimney", 255)):
        comp = largest_component(small == names.index(code))
        reg[..., 2][comp] = val
        ys, xs = np.nonzero(comp)
        scene[code] = {"cx": round(float(xs.mean()), 1), "cy": round(float(ys.mean()), 1),
                       "x0": int(xs.min()), "y0": int(ys.min()), "x1": int(xs.max()), "y1": int(ys.max()),
                       "px": int(comp.sum())}
    # Horizont: oberste Wasserzeile in der Bildmitte
    water_rows = np.nonzero(reg[:, W // 2, 0])[0]
    scene["horizon_y"] = int(water_rows.min()) if len(water_rows) else None
    save("regions.png", Image.fromarray(reg))
    for d in OUTS:
        (d / "scene.json").write_text(json.dumps(scene, indent=1))
    print(json.dumps({k: v for k, v in scene.items() if k != "ai_shares"}))

    # Vorschau mit flachen Druckfarben
    P = np.array([0.937, 0.878, 0.757]); T = np.array([0.17, 0.42, 0.45]); O = np.array([0.92, 0.38, 0.12])
    K = np.array([0.07, 0.065, 0.06])
    c = np.ones((H, W, 3)) * P
    c *= 1 - out[..., 1:2] * 0.95 * (1 - T)
    c *= 1 - out[..., 2:3] * 0.95 * (1 - O)
    c *= 1 - out[..., 0:1] * 0.95 * (1 - K)
    Image.fromarray((c * 255).astype(np.uint8)).save(ROOT / "assets/ref/sep_preview.png")


if __name__ == "__main__":
    main()
