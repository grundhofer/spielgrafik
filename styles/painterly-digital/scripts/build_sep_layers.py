#!/usr/bin/env python3
"""Getrennt erzeugte Ebenen (Bildaufträge 2, 4-7, Codex mit echtem Alphakanal) für die Godot-Demo aufbereiten.

Quelle: assets/raw/{backdrop,headland,harbour,boats,foreground}.png (je 1536x1024, master.png als Referenz).
Die Ebenen passen nicht deckungsgleich zum Hauptbild; sie werden in Godot neu komponiert. Lage und Maßstab stehen
hier (Rohbild-Koordinaten gemessen an Lupenbildern mit Raster) und werden als assets/sep/layout.json ausgegeben;
main.tscn/main.gd verwenden dieselben Zahlen.

  sky_sea.png    Himmel + Meer (Faktor 0,9), Horizont waagerecht bei Rohzeile 486,5
  head_sep.png   Landzunge mit Leuchtturm (Faktor 0,44), Ausschnitt um die deckenden Pixel
  harbour_sep.png Spielebene: Kai mit Mauer, Hütte, Laterne, Steg, Fässer, Kisten (Faktor 0,92)
  boat_row.png / boat_mast.png  die beiden Boote einzeln (Faktor 0,27), schaukeln in Godot
  fg_left.png / fg_right.png    Vordergrund geteilt (Faktor 0,7, Gauß 1,8 px als Tiefenunschärfe); die Teile
                 liegen in den unteren Ecken, an der Schnittkante läuft der Bodenstreifen weich aus
  stars.json     Lage der gemalten Sterne in sky_sea.png (zum Funkeln)

Alpha: Codex liefert höchstens 254; Werte ab 250 werden auf 255 gesetzt (sonst scheint der Hintergrund minimal
durch). Alles Lanczos, vormultipliziert verkleinert (keine dunklen Säume). Zwei Läufe ergeben bitgleiche Dateien.
"""
import json, pathlib, shutil
import numpy as np
from PIL import Image, ImageFilter

S = pathlib.Path(__file__).resolve().parent.parent
RAW = S / "assets" / "raw"
OUT = S / "assets" / "sep"
ART = S / "demo" / "art"

SKY_S, SKY_POS = 0.9, (-40, -88)            # Sprite in SkyPar (scroll 0, Parallaxe im Shader)
HORIZON_RAW = 486.5
HEAD_S, HEAD_CROP, HEAD_POS = 0.44, (250, 120, 1536, 930), (805, 89)
LAMP_RAW = (989.5, 212.0)                   # Mitte der Lampe im Leuchtturm (Rohbild headland.png)
HARB_S, HARB_CROP, HARB_POS = 0.92, (0, 260, 1536, 860), (0, 194)
BOAT_S = 0.27
BOATS = {   # Ausschnitt im Rohbild, Wasserlinie (Rohzeile), Mitte x (Rohspalte), Lage der Wasserlinie in der Welt
    "boat_row": {"crop": (32, 560, 749, 830), "water_raw": 772, "cx_raw": 392, "world": (695, 576)},
    "boat_mast": {"crop": (834, 279, 1515, 830), "water_raw": 778, "cx_raw": 1172, "world": (998, 588)},
}
FG_S, FG_BLUR = 0.7, 1.8
FG_PARTS = {"fg_left": (0, 440, 760, 1024), "fg_right": (760, 440, 1536, 1024)}
FG_POS = {"fg_left": (20, 346), "fg_right": (857, 346)}   # in FgPar (scroll 1,5)
FG_FADE_PX = 70                               # Bodenstreifen läuft an der Schnittkante über so viele px aus


def load(name):
    return Image.open(RAW / f"{name}.png").convert("RGBA")


def fix_alpha(im):
    a = np.asarray(im).copy()
    al = a[..., 3]
    al[al >= 250] = 255
    return Image.fromarray(a, "RGBA")


def shrink(im, s):
    """Vormultipliziert mit Lanczos verkleinern (keine dunklen oder bunten Säume an weichen Kanten)."""
    a = np.asarray(im).astype(np.float32) / 255.0
    pm = a.copy()
    pm[..., :3] *= pm[..., 3:4]
    w, h = round(im.width * s), round(im.height * s)
    ch = [np.asarray(Image.fromarray(pm[..., c]).resize((w, h), Image.LANCZOS)) for c in range(4)]
    out = np.dstack(ch)
    out[..., 3] = np.clip(out[..., 3], 0, 1)
    rgb = np.where(out[..., 3:4] > 1e-4, out[..., :3] / np.maximum(out[..., 3:4], 1e-4), 0)
    out[..., :3] = np.clip(rgb, 0, 1)
    return Image.fromarray(np.round(out * 255).astype(np.uint8), "RGBA")


def gauss(a, r):
    """Trennbarer Gauß (sigma r) in NumPy; Pillow kann Gleitkommabilder nicht weichzeichnen."""
    n = int(np.ceil(3 * r))
    k = np.exp(-0.5 * (np.arange(-n, n + 1) / r) ** 2)
    k /= k.sum()
    p = np.pad(a, ((n, n), (n, n)), mode="edge")
    p = sum(k[i] * p[:, i:i + a.shape[1]] for i in range(2 * n + 1))
    return sum(k[i] * p[i:i + a.shape[0], :] for i in range(2 * n + 1))


def blur_pm(im, r):
    a = np.asarray(im).astype(np.float32) / 255.0
    pm = a.copy()
    pm[..., :3] *= pm[..., 3:4]
    out = np.dstack([gauss(pm[..., c], r) for c in range(4)])
    rgb = np.where(out[..., 3:4] > 1e-4, out[..., :3] / np.maximum(out[..., 3:4], 1e-4), 0)
    out[..., :3] = np.clip(rgb, 0, 1)
    return Image.fromarray(np.round(np.clip(out, 0, 1) * 255).astype(np.uint8), "RGBA")


def stars(sky):
    """Gemalte Sterne: kleine Punkte, deutlich heller als ihre 9x9-Umgebung, nur im oberen Himmel."""
    g = np.asarray(sky.convert("L")).astype(np.float32)
    med = np.asarray(sky.convert("L").filter(ImageFilter.MedianFilter(9))).astype(np.float32)
    d = g - med
    pts = []
    ys, xs = np.nonzero(d[:260] > 28)
    taken = np.zeros_like(d, bool)
    for y, x in sorted(zip(ys, xs), key=lambda p: -d[p[0], p[1]]):
        if taken[max(0, y - 6):y + 7, max(0, x - 6):x + 7].any():
            continue
        taken[y, x] = True
        pts.append([int(x), int(y), round(float(d[y, x]), 1)])
    return pts


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    files, layout = {}, {}

    sky = load("backdrop").convert("RGB").resize((round(1536 * SKY_S), round(1024 * SKY_S)), Image.LANCZOS)
    files["sky_sea"] = sky.convert("RGBA")
    layout["sky_sea"] = {"pos": SKY_POS, "size": sky.size, "horizon_tex": HORIZON_RAW * SKY_S,
                         "horizon_screen": HORIZON_RAW * SKY_S + SKY_POS[1]}

    head = shrink(fix_alpha(load("headland")).crop(HEAD_CROP), HEAD_S)
    files["head_sep"] = head
    lamp = (HEAD_POS[0] + (LAMP_RAW[0] - HEAD_CROP[0]) * HEAD_S, HEAD_POS[1] + (LAMP_RAW[1] - HEAD_CROP[1]) * HEAD_S)
    layout["head_sep"] = {"pos": HEAD_POS, "size": head.size, "lamp": [round(lamp[0], 1), round(lamp[1], 1)],
                          "waterline_screen": round(HEAD_POS[1] + (918 - HEAD_CROP[1]) * HEAD_S, 1)}

    harb = shrink(fix_alpha(load("harbour")).crop(HARB_CROP), HARB_S)
    files["harbour_sep"] = harb

    def hp(x, y):
        return [round(HARB_POS[0] + (x - HARB_CROP[0]) * HARB_S, 1), round(HARB_POS[1] + (y - HARB_CROP[1]) * HARB_S, 1)]
    layout["harbour_sep"] = {"pos": HARB_POS, "size": harb.size, "chimney": hp(352, 276), "window": hp(400, 568),
                             "lantern": hp(601, 556), "quay_back": hp(0, 710)[1], "quay_front": hp(0, 775)[1],
                             "rope_coil_bottom": hp(0, 745)[1]}

    boats = fix_alpha(load("boats"))
    for k, b in BOATS.items():
        im = shrink(boats.crop(b["crop"]), BOAT_S)
        files[k] = im
        px = ((b["cx_raw"] - b["crop"][0]) * BOAT_S, (b["water_raw"] - b["crop"][1]) * BOAT_S)
        layout[k] = {"size": im.size, "pivot": [round(px[0], 2), round(px[1], 2)],
                     "water_v": round(px[1] / im.height, 4), "world": b["world"]}

    fg = fix_alpha(load("foreground"))
    for k, box in FG_PARTS.items():
        im = blur_pm(shrink(fg.crop(box), FG_S), FG_BLUR)
        a = np.asarray(im).copy()
        h, w = a.shape[:2]
        ramp = np.clip(np.arange(w) / FG_FADE_PX, 0, 1) if k == "fg_right" else np.clip((w - 1 - np.arange(w)) / FG_FADE_PX, 0, 1)
        ramp = ramp * ramp * (3 - 2 * ramp)
        a[..., 3] = np.round(a[..., 3] * ramp[None, :]).astype(np.uint8)
        files[k] = Image.fromarray(a, "RGBA")
        layout[k] = {"pos": FG_POS[k], "size": im.size}

    for k, im in files.items():
        im.save(OUT / f"{k}.png", optimize=True)
        print(k, im.size)
    layout["stars_tex"] = stars(sky)
    (OUT / "layout.json").write_text(json.dumps(layout, indent=1))
    print(json.dumps({k: v for k, v in layout.items() if k != "stars_tex"}, indent=1))
    print("Sterne:", len(layout["stars_tex"]), layout["stars_tex"][:12])
    ART.mkdir(parents=True, exist_ok=True)
    for f in OUT.glob("*.png"):
        shutil.copy2(f, ART / f.name)


if __name__ == "__main__":
    main()
