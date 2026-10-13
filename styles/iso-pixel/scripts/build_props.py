"""KI-Requisitenblatt (agy, über der Blender-Vorlage gemalt) -> einzelne Pixel-Sprites auf der iso-pixel-Palette.

  .venv/bin/python styles/iso-pixel/scripts/build_props.py

Je Objekt:
  1. Rasterlage suchen: Teilung (3,25 bis 3,34 Bildpixel je Kunstpixel) und Versatz (±2 Kunstpixel, 1/8-Schritte),
     so dass die Deckung des KI-Bildes in den Zellmitten am besten mit der Blender-Vorlage übereinstimmt (IoU).
  2. Je Kunstpixel die Farbe aus dem Zellinneren (Mittel der inneren 2×2 Bildpixel, die JPEG-Quelle rauscht),
     Deckung als Mehrheit der inneren 3×3 (ohne Magenta-Saum), Farbe nur aus deckenden Pixeln; auf die nächste Farbe
     der Tagespalette (Oklab, ohne die grünen Leitern; grün- oder magentastichige Saumreste auf die Metal-Leiter)
     setzen und dann wie alle Assets in die Dämmerung schieben (isopal.dusk, Glas und Auge ausgenommen). Wo die
     Vorlage Glas zeigt und die KI hell gemalt hat (Oklab L ab 0,66), die Glas-Leiter nach Helligkeit.
  3. Einzelpixel ohne gleichfarbigen Nachbarn, deren Nachbarn sich einig sind, angleichen; Außenkontur schließen.
Schreibt demo/art/props/<name>.png, assets/props/<name>.png (gleich) und demo/art/props.json (Ankerpunkt je Objekt
= Bodenpunkt aus Blender, in Sprite-Pixeln) sowie assets/props/compare.png (Vorlage | KI | Ergebnis, ×3).
"""
import json
import pathlib
import sys

import numpy as np
from PIL import Image

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import isopal  # noqa: E402
import pixelize3d  # noqa: E402

ENTRY = HERE.parent
RAW = ENTRY / "assets/raw/props.png"
LAYOUT = ENTRY / "assets/ref/props_layout.json"
LAYOUT1 = ENTRY / "assets/ref/props_layout_1x.png"
OUT_DEMO = ENTRY / "demo/art/props"
OUT_ASSETS = ENTRY / "assets/props"


def srgb_to_oklab(c):
    c = np.asarray(c, np.float64) / 255.0
    c = np.where(c <= 0.04045, c / 12.92, ((c + 0.055) / 1.055) ** 2.4)
    M1 = np.array([[0.4122214708, 0.5363325363, 0.0514459929],
                   [0.2119034982, 0.6806995451, 0.1073969566],
                   [0.0883024619, 0.2817188376, 0.6299787005]])
    lms = np.cbrt(c @ M1.T)
    M2 = np.array([[0.2104542553, 0.7936177850, -0.0040720468],
                   [1.9779984951, -2.4285922050, 0.4505937099],
                   [0.0259040371, 0.7827717662, -0.8086757660]])
    return lms @ M2.T


# Die KI malt in Tageslichtfarben der Vorlage: erst auf die Tagespalette setzen, dann jede Farbe wie die Kacheln
# in die Dämmerung schieben (isopal.dusk). So bleibt die Tonfolge der KI erhalten.
# Keine Requisite hat Gras oder grünen Stoff: die grünen Leitern stehen nicht zur Wahl. Grün- oder magentastichige
# Abtastungen (Reste der Freistellung, z. B. in den Lücken des Leuchtturmgeländers) kommen nach Helligkeit auf die
# Metal-Leiter. Glas und Auge werden wie in isopal.RAMPS nicht in die Dämmerung geschoben.
NO_GREEN = ("Grass", "Cap", "Vest")
_GREEN_DAY = {c for k in NO_GREEN for c in isopal.RAMPS_DAY[k]}
PALETTE = np.array([c for c in isopal.all_colors(day=True) if c not in _GREEN_DAY], np.float64)
PAL_LAB = srgb_to_oklab(PALETTE)
METAL_DAY = np.array(isopal.RAMPS_DAY["Metal"], np.float64)
METAL_L = srgb_to_oklab(METAL_DAY)[:, 0]
_KEEP = {isopal.OUTLINE} | set(isopal.RAMPS_DAY["Glass"]) | set(isopal.RAMPS_DAY["Eye"])
_DUSK = {tuple(c): (tuple(c) if tuple(c) in _KEEP else isopal.dusk(tuple(c))) for c in PALETTE.astype(int)}


def greenish(rgb):
    """Saumreste der Freistellung: grünstichig (HSV-Farbton 0,2 bis 0,45, Sättigung über 0,25; Gegenfarbe nach dem
    Entfernen des Magenta-Saums) oder Magenta (Farbton 0,78 bis 0,92, Sättigung über 0,5, Helligkeit ab 60; Schlüsselfarbe im
    Schatten zwischen Geländerstäben). Beides kommt in keinem Material der Requisiten vor. Dunklere magentastichige
    Pixel sind die gemalte Kontur (JPEG mischt sie mit dem Magenta) und landen ohnehin auf Kontur/Auge."""
    c = rgb.reshape(-1, 3) / 255.0
    mx, mn = c.max(1), c.min(1)
    sat = np.where(mx > 0, (mx - mn) / np.maximum(mx, 1e-9), 0)
    r, g, b = c[:, 0], c[:, 1], c[:, 2]
    dlt = np.maximum(mx - mn, 1e-9)
    hue = np.where(mx == r, ((g - b) / dlt) % 6, np.where(mx == g, (b - r) / dlt + 2, (r - g) / dlt + 4)) / 6.0
    green = (hue >= 0.2) & (hue <= 0.45) & (sat > 0.25)
    magenta = (hue >= 0.78) & (hue <= 0.92) & (sat > 0.5) & (mx >= 60 / 255)
    return (green | magenta) & (mx > mn)


def to_palette(rgb):
    flat = rgb.reshape(-1, 3)
    lab = srgb_to_oklab(flat)
    d = ((lab[:, None, :] - PAL_LAB[None, :, :]) ** 2).sum(-1)
    day = PALETTE[d.argmin(1)].astype(int)
    g = greenish(flat)
    if g.any():
        day[g] = METAL_DAY[np.abs(lab[g, :1] - METAL_L[None, :]).argmin(1)].astype(int)
    out = np.array([_DUSK[tuple(c)] for c in day], np.uint8)
    return out.reshape(rgb.shape)


# Leuchtflächen aus der Vorlage: Das Modell malt Fenster und Lampen mal satt gelb, mal blass oder als graues Glas.
# Wo die Blender-Vorlage Glas zeigt und die KI hell gemalt hat, kommt die Glas-Leiter (nach Helligkeit, ohne
# Dämmerung); dunkle Sprossen und Rahmen der KI bleiben.
GLASS_DAY = np.array(isopal.RAMPS_DAY["Glass"], np.float64)
GLASS_L = srgb_to_oklab(GLASS_DAY)[:, 0]
GLASS_MIN_L = 0.66


def lit_glass(rgb, col, a, ref_rgb):
    glass_ref = np.zeros(a.shape, bool)
    for c in isopal.RAMPS_DAY["Glass"]:
        glass_ref |= (ref_rgb == np.array(c)).all(-1)
    L = srgb_to_oklab(col.reshape(-1, 3))[:, 0].reshape(a.shape)
    sel = glass_ref & a & (L >= GLASS_MIN_L)
    step = np.abs(L[..., None] - GLASS_L[None, None, :]).argmin(-1)
    out = rgb.copy()
    out[sel] = np.array(isopal.RAMPS["Glass"], np.uint8)[step[sel]]
    return out, int(sel.sum())


def sample(img, x0, y0, p, w, h):
    """Kunstpixel (w×h) ab Bildpunkt (x0, y0) mit Teilung p: Farbe (Mittel innen 2×2) und Deckung (Mehrheit 3×3)."""
    H, W = img.shape[:2]
    cx = x0 + (np.arange(w) + 0.5) * p
    cy = y0 + (np.arange(h) + 0.5) * p
    col = np.zeros((h, w, 3))
    alp = np.zeros((h, w))
    for dy in (-1, 0, 1):
        for dx in (-1, 0, 1):
            yy = np.clip(np.floor(cy + dy * 0.9).astype(int), 0, H - 1)
            xx = np.clip(np.floor(cx + dx * 0.9).astype(int), 0, W - 1)
            px = img[yy][:, xx]
            r, g, b = (px[..., i].astype(int) for i in range(3))
            fringe = (r > 140) & (b > 140) & (g < r - 70) & (g < b - 70)     # Magenta-Saum der Freistellung
            alp += (px[..., 3] > 127) & ~fringe
    # Farbe nur aus deckenden Bildpixeln ohne Magenta-Saum: transparente Pixel behalten im RGBA-Bild ihre
    # Magenta-Farbe und würden Randzellen sonst rot oder lila färben.
    wsum = np.zeros((h, w))
    col_all = np.zeros((h, w, 3))
    for dy in (-0.5, 0.5):
        for dx in (-0.5, 0.5):
            yy = np.clip(np.floor(cy + dy).astype(int), 0, H - 1)
            xx = np.clip(np.floor(cx + dx).astype(int), 0, W - 1)
            px = img[yy][:, xx]
            r, g, b = (px[..., i].astype(int) for i in range(3))
            fringe = (r > 140) & (b > 140) & (g < r - 70) & (g < b - 70)
            wt = ((px[..., 3] > 127) & ~fringe).astype(float)
            col += px[..., :3] * wt[..., None]
            wsum += wt
            col_all += px[..., :3]
    col = np.where(wsum[..., None] > 0, col / np.maximum(wsum, 1)[..., None], col_all / 4.0)
    return col, alp >= 5


def despeckle(rgb, a):
    out = rgb.copy()
    H, W = a.shape
    for y in range(1, H - 1):
        for x in range(1, W - 1):
            if not a[y, x]:
                continue
            c = tuple(rgb[y, x])
            nb = [(y - 1, x), (y + 1, x), (y, x - 1), (y, x + 1)]
            cols = [tuple(rgb[j, i]) if a[j, i] else None for j, i in nb]
            if c in cols:
                continue
            vals = [v for v in cols if v is not None]
            if len(vals) == 4 and len(set(vals)) == 1:
                out[y, x] = vals[0]
    return out


def main():
    img = np.asarray(Image.open(RAW).convert("RGBA"))
    lay = json.load(open(LAYOUT))
    lay1 = np.asarray(Image.open(LAYOUT1).convert("RGBA"))
    OUT_DEMO.mkdir(parents=True, exist_ok=True)
    OUT_ASSETS.mkdir(parents=True, exist_ok=True)
    meta = {}
    comp_rows = []
    sx_nom = img.shape[1] / lay["canvas"][0]
    for name, b in lay["boxes"].items():
        m = 2
        bx, by, bw, bh = b["x"] - m, b["y"] - m, b["w"] + 2 * m, b["h"] + 2 * m
        ref_rgb = lay1[by:by + bh, bx:bx + bw, :3].astype(int)
        ref_a = np.abs(ref_rgb - np.array([255, 0, 255])).sum(-1) > 30      # Vorlage: Magenta = leer
        best = None
        for p in np.arange(3.25, 3.345, 0.005):
            for ox in np.arange(-2, 2.01, 0.125):
                for oy in np.arange(-2, 2.01, 0.125):
                    _, a = sample(img, (bx + ox) * p, (by + oy) * p, p, bw, bh)
                    iou = (a & ref_a).sum() / max(1, (a | ref_a).sum())
                    if best is None or iou > best[0]:
                        best = (iou, p, ox, oy)
        iou, p, ox, oy = best
        col, a = sample(img, (bx + ox) * p, (by + oy) * p, p, bw, bh)
        rgb = to_palette(col)
        n_green = int((greenish(col).reshape(a.shape) & a).sum())
        rgb, n_glass = lit_glass(rgb, col, a, ref_rgb)
        rgb = despeckle(rgb, a)
        rgba = np.zeros((bh, bw, 4), np.uint8)
        rgba[..., :3] = rgb
        rgba[..., 3] = np.where(a, 255, 0)
        # Außenkontur schließen: Randpixel, die nicht schon dunkel sind, bekommen außen die Konturfarbe
        rgba = pixelize3d.add_outline(rgba)
        ys, xs = np.nonzero(rgba[..., 3])
        x0, x1, y0, y1 = xs.min(), xs.max() + 1, ys.min(), ys.max() + 1
        spr = rgba[y0:y1, x0:x1]
        Image.fromarray(spr).save(OUT_DEMO / f"{name}.png")
        Image.fromarray(spr).save(OUT_ASSETS / f"{name}.png")
        anchor = [b["anchor"][0] + m - int(x0), b["anchor"][1] + m - int(y0)]
        meta[name] = {"size": [int(x1 - x0), int(y1 - y0)], "anchor": anchor,
                      "fit": {"iou": round(float(iou), 3), "pitch": round(float(p), 3), "dx": float(ox), "dy": float(oy)},
                      "colors": int(len(np.unique(spr[spr[..., 3] > 0][:, :3], axis=0))),
                      "fringe_to_metal": n_green, "glass_from_layout": n_glass}
        print(name, meta[name])
        # Vergleich: Vorlage | KI (nächster Nachbar) | Ergebnis
        ref = lay1[by:by + bh, bx:bx + bw].copy()
        ref[..., 3] = np.where(ref_a, 255, 0)
        ai = np.zeros((bh, bw, 4), np.uint8)
        ai[..., :3] = np.clip(col, 0, 255)
        ai[..., 3] = np.where(a, 255, 0)
        comp_rows.append((ref, ai, rgba))
    json.dump(meta, open(OUT_DEMO.parent / "props.json", "w"), indent=1)
    f = 3
    W = sum(max(r[0].shape[1], 1) for r in comp_rows) * 3 * f + 40 * len(comp_rows)
    H = max(r[0].shape[0] for r in comp_rows) * f
    sheet = Image.new("RGBA", (W // 3 + 200, H * 3 + 20), (52, 46, 70, 255))
    x = 0
    for ref, ai, res in comp_rows:
        for row, im in enumerate((ref, ai, res)):
            sheet.alpha_composite(Image.fromarray(im).resize((im.shape[1] * f, im.shape[0] * f), Image.NEAREST),
                                  (x, row * (H + 6)))
        x += ref.shape[1] * f + 12
    sheet.save(OUT_ASSETS / "compare.png")


if __name__ == "__main__":
    main()
