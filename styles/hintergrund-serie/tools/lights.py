#!/usr/bin/env python3
"""Findet Lichtquellen-Kandidaten (Fenster, Laternen, Lampen, Glut) in den geschnittenen Hintergründen.

Aufruf aus dem Projektordner:
    .venv/bin/python styles/hintergrund-serie/tools/lights.py [--out DIR] [ort ...]

Hilfe zum Eintragen der Effekt-Lagen in demo/locations.gd (glows, flames, beams, smoke, sweeps …): sucht in
demo/art/bg_<ort>.png kleine, helle, warme Flecken (Lab: L > 60, Buntheit > 18, Farbton orange bis gelb),
verwirft große Flächen (z. B. das Horizontband) und schreibt je Ort
  <out>/lights_<ort>.png   Hintergrund mit nummerierten Kandidaten, Hilfslinien für Augenhöhe und Laufstreifen
  <out>/lights.json        Kandidaten mit Mittelpunkt, Größe und Helligkeit (Bildschirmpixel 1280x720)
Standard für --out ist der Temp-Ordner des Eintrags. Die Kandidaten sind Vorschläge: im Bild prüfen, welche
Lichtquelle welcher Fleck ist, und die Lage in locations.gd übernehmen.
"""
import argparse, json, pathlib, sys, tempfile

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

SD = pathlib.Path(__file__).resolve().parent.parent
sys.dont_write_bytecode = True                                # kein __pycache__ im Eintragsordner
sys.path.insert(0, str(SD / "tools"))
import prep  # noqa: E402  (Farbräume, Zusammenhangskomponenten, Bildaufbau)

LOCS = prep.LOCS


def candidates(img, max_n=12):
    sc = 4
    small = np.asarray(Image.fromarray(img).resize((img.shape[1] // sc, img.shape[0] // sc), Image.BOX), np.float64)
    lab = prep.srgb_to_lab(small)
    L, a, b = lab[..., 0], lab[..., 1], lab[..., 2]
    chroma = np.hypot(a, b)
    hue = np.degrees(np.arctan2(b, a)) % 360
    mask = (L > 60) & (chroma > 18) & (hue > 30) & (hue < 100)
    mask[prep.UI_TOP // sc:] = False                          # unter der Textbox zählt nichts
    # benachbarte Flecken (Fensterscheiben, Laterne mit Lichthof) zu einer Lichtquelle zusammenfassen
    grown = np.asarray(Image.fromarray(mask.astype(np.uint8) * 255).filter(ImageFilter.MaxFilter(5))) > 0
    comp = prep.label_components(grown) * mask
    out = []
    total = mask.size
    for i in range(1, comp.max() + 1):
        ys, xs = np.nonzero(comp == i)
        area = len(ys)
        if area < 2 or area > total * 0.02:
            continue
        w = xs.max() - xs.min() + 1
        h = ys.max() - ys.min() + 1
        if w > 0.25 * mask.shape[1]:                          # breite Bänder (Horizont) verwerfen
            continue
        out.append({"pos": [int(round((xs.mean() + 0.5) * sc)), int(round((ys.mean() + 0.5) * sc))],
                    "size": [int(w * sc), int(h * sc)], "area_px": int(area * sc * sc),
                    "L_max": round(float(L[ys, xs].max()), 1), "score": float(L[ys, xs].max() * np.sqrt(area))})
    out.sort(key=lambda c: -c["score"])
    for c in out:
        c.pop("score")
    return out[:max_n]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("locs", nargs="*", default=LOCS)
    ap.add_argument("--out", default=str(pathlib.Path(tempfile.gettempdir()) / "hintergrund-serie" / "lights"))
    a = ap.parse_args()
    out = pathlib.Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    res = {}
    font = ImageFont.load_default(size=18)
    for loc in a.locs:
        img = np.asarray(Image.open(prep.ART / f"bg_{loc}.png").convert("RGB"))
        cands = candidates(img)
        res[loc] = cands
        ov = Image.fromarray(img).convert("RGB")
        d = ImageDraw.Draw(ov)
        for yy, col in ((prep.screen_row(prep.LAYOUT["eye"]), (255, 200, 120)),
                        (prep.screen_row(prep.LAYOUT["walk"][0]), (240, 230, 200)),
                        (prep.screen_row(prep.LAYOUT["walk"][1]), (240, 230, 200)), (prep.UI_TOP, (120, 200, 255))):
            for x in range(0, prep.W, 16):
                d.line([x, yy, x + 7, yy], fill=col, width=1)
        for k, c in enumerate(cands):
            x, y = c["pos"]
            r = max(10, max(c["size"]) // 2 + 4)
            d.ellipse([x - r, y - r, x + r, y + r], outline=(0, 255, 255), width=2)
            d.text((x + r + 3, y - 10), str(k), font=font, fill=(0, 255, 255))
        ov.save(out / f"lights_{loc}.png")
        print(f"{loc}: " + ", ".join(f"{k}:{tuple(c['pos'])}" for k, c in enumerate(cands)))
    (out / "lights.json").write_text(json.dumps(res, indent=1) + "\n")
    print(out)


if __name__ == "__main__":
    main()
