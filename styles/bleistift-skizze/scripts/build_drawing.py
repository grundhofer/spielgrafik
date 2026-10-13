#!/usr/bin/env python3
"""Bereitet die KI-Bleistiftzeichnung (assets/raw/bg.png) als Zeichenebene für die Demo auf.

    .venv/bin/python styles/bleistift-skizze/scripts/build_drawing.py

Schritte:
  1. Papierweiß auf 1,0 ziehen (Mittel des leeren Himmels oben).
  2. Farbe nur dort behalten, wo Buntstift gewollt ist (Laternenglas, Fenster, Leuchtturm mit rotem Band,
     orangefarbener Horizontstreifen samt Spiegelung); überall sonst die leichte Sepialasur des Bildmodells
     (Holz, Fässer, Pfosten) auf Grafitgrau setzen.
  3. Grafit statt Tusche: Absorption linear auf das dunkelste Grafit (#33343C) begrenzen, Buntstift ebenso.
  4. Ausschnitt in den gezeichneten Rahmen (scripts/layout.json) mit Lanczos verkleinern.
Ergebnis: assets/drawing.png und demo/art/drawing.png (RGB, Papier = Weiß) sowie demo/art/layout.json mit den
Ankerpunkten der Effekte in Bildschirmkoordinaten.
"""
import json, pathlib, shutil
import numpy as np
from PIL import Image, ImageFilter

ROOT = pathlib.Path(__file__).resolve().parents[1]
L = json.loads((ROOT / "scripts/layout.json").read_text())
G_DARK = np.array([0x33, 0x34, 0x3C], np.float32) / 255.0


def soft_rect_mask(h, w, rects, feather):
    m = Image.new("L", (w, h), 0)
    px = np.zeros((h, w), np.float32)
    for x0, y0, x1, y1 in rects:
        px[y0:y1, x0:x1] = 1.0
    m = Image.fromarray((px * 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(feather))
    return np.asarray(m, np.float32) / 255.0


def main():
    a = np.asarray(Image.open(ROOT / "assets/raw/bg.png").convert("RGB"), np.float32) / 255.0
    h, w, _ = a.shape
    white = a[20:120, 200:1300].reshape(-1, 3).mean(0)
    a = np.clip(a / white, 0, 1)
    gray = (a * np.array([0.30, 0.59, 0.11], np.float32)).sum(2, keepdims=True)
    chroma = a.max(2) - a.min(2)
    full = soft_rect_mask(h, w, L["color_keep_full"], 4)            # Lichter: Farbe ganz behalten
    horizon = soft_rect_mask(h, w, L["color_keep_chroma"], 18)      # Horizont: nur kräftige Farbe
    sel = np.clip((chroma - 0.10) / 0.10, 0, 1)
    keep = np.maximum(full, horizon * sel)[..., None]
    rgb = gray + (a - gray) * keep
    out = 1.0 - (1.0 - rgb) * (1.0 - G_DARK)
    fx, fy, fw, fh = L["frame"]
    cx0, cy0, cx1, cy1 = L["crop"]
    img = Image.fromarray((np.clip(out, 0, 1) * 255 + 0.5).astype(np.uint8))
    img = img.crop((cx0, cy0, cx1, cy1)).resize((fw, fh), Image.LANCZOS)
    img.save(ROOT / "assets/drawing.png")
    (ROOT / "demo/art").mkdir(parents=True, exist_ok=True)
    shutil.copy(ROOT / "assets/drawing.png", ROOT / "demo/art/drawing.png")

    s = fw / (cx1 - cx0)

    def to_screen(p):
        return [round(fx + (p[0] - cx0) * s, 1), round(fy + (p[1] - cy0) * s, 1)]

    anchors = {k: to_screen(v) for k, v in L["anchors_src"].items()}
    lay = {"frame": L["frame"], "scale": s, "anchors": anchors,
           "water_y": [to_screen([0, L["water_src"][0]])[1], to_screen([0, L["water_src"][1]])[1]],
           "walk": L["walk"]}
    (ROOT / "demo/art/layout.json").write_text(json.dumps(lay, indent=1))
    print("ok", ROOT / "assets/drawing.png", img.size, "scale", round(s, 4))
    print(json.dumps(anchors))


if __name__ == "__main__":
    main()
