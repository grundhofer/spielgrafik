#!/usr/bin/env python3
"""Baut aus den gereinigten Cels (scripts/ink_paint.py) die Sprite-Blätter der Demo.

    .venv/bin/python styles/zeichentrick-cel/scripts/build_sprites.py

Dachs (assets/badger_cels.png, 13 Bilder à 154x256, Abendfarbmodell):
  0–7 walk_0 … walk_7, 8 stand, 9 front, 10 front_talk_a (Mund halb offen), 11 front_talk_b (Mund offen),
  12 front_blink (Lider zu).
  Jede Zeichnung bleibt an ihrer Stelle in der Layout-Zelle (so liegt der Fußpunkt der Blender-Vorlage in allen
  Bildern an derselben Stelle), die Sohle wird auf die gemeinsame Grundlinie gesetzt (Quelle y 504, Blatt y 252).
  Sprechen und Blinzeln: Mund und Lider werden auf die gehaltene Vorderansicht gemalt (wie Mund- und Augen-Cels
  über einem gehaltenen Körper-Cel); alle übrigen Pixel bleiben in den vier Vorderbildern gleich.
Boote (assets/boat_a.png, assets/boat_b.png): Komponenten aus boats_dusk.png, verkleinert.
Kontaktschatten (assets/shadow.png): flache Ellipse wie ein Schatten-Cel.
Messwerte und Anker: assets/sprites.json.
"""
import json, pathlib, sys

import numpy as np
from PIL import Image, ImageDraw

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from celutil import downscale_premul, srgb_to_lab  # noqa: E402
from ink_paint import lab_to_srgb  # noqa: E402

ROOT = pathlib.Path(__file__).resolve().parents[1]
CEL = ROOT / "assets/cel"
A = ROOT / "assets"
SCALE = 0.5
CW, CH, BASE = 308, 512, 504
NAMES = [f"walk_{i}" for i in range(8)] + ["stand", "front"]
BOAT_SCALE = {"boat_a": 0.22, "boat_b": 0.17}


def to_dusk(rgb):
    lab = srgb_to_lab(np.array(rgb, np.float64))
    lab = lab * np.array([0.86, 0.82, 0.82]) + np.array([0, 3.0, -7.0])
    return tuple(int(v) for v in lab_to_srgb(lab).round())


def figure_canvas(img, comp, fig_id, cell):
    m = (comp == fig_id) & (img[..., 3] > 0)
    ys, xs = np.where(m)
    bottom = ys.max()
    canvas = np.zeros((CH, CW, 4), np.uint8)
    dy = BASE - bottom
    sel = img.copy()
    sel[~m] = 0
    x0 = cell["x"]
    src = sel[:, x0:x0 + CW] if x0 + CW <= sel.shape[1] else np.pad(sel[:, x0:], ((0, 0), (0, x0 + CW - sel.shape[1]), (0, 0)))
    # Teile außerhalb der Zelle (z. B. Schalende) gehören zur Komponente: Zelle notfalls verbreitern ist nicht nötig,
    # es wird geprüft, dass nichts abgeschnitten wird.
    lost = m.sum() - (src[..., 3] > 0).sum()
    ys2 = slice(max(0, -dy), min(CH - dy, img.shape[0]))
    tgt = slice(ys2.start + dy, ys2.stop + dy)
    canvas[tgt] = src[ys2]
    return canvas, int(lost), int(bottom)


def draw_mouth(im, depth):
    """Offener Mund unter der Nase (Quellkoordinaten der Vorderansicht im Blatt)."""
    d = ImageDraw.Draw(im)
    top = [(1375, 673), (1383, 677), (1392, 680), (1402, 681), (1412, 680), (1421, 677), (1429, 672), (1434, 667)]
    k = depth
    bot = [(1430, 670 + k * 0.3), (1424, 678 + k * 0.75), (1414, 681 + k), (1402, 681 + k), (1391, 679 + k * 0.8),
           (1382, 676 + k * 0.45)]
    poly = top + bot
    ink = to_dusk((30, 20, 16))
    d.polygon(poly, fill=to_dusk((92, 30, 34)))
    if depth >= 10:  # Zunge
        d.ellipse((1396, 681 + k - 7, 1418, 681 + k + 1), fill=to_dusk((214, 104, 108)))
        d.polygon(poly, outline=None)
    d.line(top + top[-1:], fill=ink, width=3, joint="curve")
    d.line(top[-1:] + bot + top[:1], fill=ink, width=3, joint="curve")
    # Nasenunterkante bleibt, Philtrum-Strich weg (liegt jetzt im Mund)


def draw_blink(im, fur):
    d = ImageDraw.Draw(im)
    ink = to_dusk((30, 20, 16))
    for cx, cy, rx, ry in [(1369, 643, 11, 10), (1426, 639, 11, 10)]:
        d.ellipse((cx - rx, cy - ry, cx + rx, cy + ry), fill=fur)
        d.arc((cx - rx + 1, cy - ry - 4, cx + rx - 1, cy + ry - 2), 20, 160, fill=ink, width=3)


def main():
    stats = json.loads((CEL / "cels.json").read_text())
    lay = json.loads((ROOT / "assets/ref/layout.json").read_text())
    poses = json.loads((ROOT / "assets/ref/poses/poses.json").read_text())
    img = np.array(Image.open(CEL / "sheet_dusk.png").convert("RGBA"))
    comp = np.array(Image.open(CEL / "sheet_comp.png"))
    figs = stats["sheet"]["figures"]
    cells = {c["name"]: c for c in lay["cells"]}
    frames, meta = [], {"scale": SCALE, "cell": [CW * SCALE, CH * SCALE], "baseline": BASE * SCALE,
                        "root_x": None, "frames": []}
    fur = tuple(stats["sheet"]["model_dusk"]["fur_dark"]["light"])
    variants = {}
    for name in NAMES:
        cell = cells[name]
        cx = cell["x"] + cell["w"] / 2
        cy = cell["y"] + cell["h"] / 2
        f = min(figs, key=lambda g: (g["cx"] - cx) ** 2 + (g["cy"] - cy) ** 2)
        if name == "front":
            base = Image.fromarray(img)
            for vname, fn in [("front", None), ("front_talk_a", lambda im: draw_mouth(im, 7)),
                              ("front_talk_b", lambda im: draw_mouth(im, 13)),
                              ("front_blink", lambda im: draw_blink(im, fur))]:
                v = base.copy()
                if fn:
                    fn(v)
                arr = np.array(v)
                arr[comp != f["id"]] = 0
                variants[vname] = arr
            for vname, arr in variants.items():
                cnv, lost, bottom = figure_canvas(arr, np.where(arr[..., 3] > 0, f["id"], 0), f["id"], cell)
                frames.append((vname, cnv, lost, bottom, cell))
        else:
            cnv, lost, bottom = figure_canvas(img, comp, f["id"], cell)
            frames.append((name, cnv, lost, bottom, cell))
    root_px = (0 - (-0.012)) * poses["px_per_m"] + poses["w"] / 2  # Fußpunkt der Vorlage in der Zelle
    meta["root_x"] = root_px * SCALE
    out_w, out_h = int(CW * SCALE), int(CH * SCALE)
    sheet = Image.new("RGBA", (out_w * len(frames), out_h), (0, 0, 0, 0))
    for i, (name, cnv, lost, bottom, cell) in enumerate(frames):
        small = downscale_premul(cnv, (out_w, out_h))
        sheet.paste(Image.fromarray(small), (i * out_w, 0))
        ys, xs = np.where(small[..., 3] > 127)
        meta["frames"].append({"name": name, "index": i, "lost_px": lost, "src_bottom": bottom,
                               "bbox": [int(xs.min()), int(ys.min()), int(xs.max()) + 1, int(ys.max()) + 1]})
        if lost:
            print("WARNUNG", name, "abgeschnitten:", lost, "px")
    sheet.save(A / "badger_cels.png")
    # Tagesmodell nur zum Vergleich (nicht in der Demo)
    # Boote
    bimg = np.array(Image.open(CEL / "boats_dusk.png").convert("RGBA"))
    bcomp = np.array(Image.open(CEL / "boats_comp.png"))
    boats = sorted(stats["boats"]["figures"], key=lambda g: g["cx"])
    meta["boats"] = {}
    for key, f in zip(["boat_a", "boat_b"], boats):
        x0, y0, x1, y1 = f["bbox"]
        sel = bimg.copy()
        sel[bcomp != f["id"]] = 0
        crop = sel[y0:y1, x0:x1]
        s = BOAT_SCALE[key]
        size = (round((x1 - x0) * s), round((y1 - y0) * s))
        small = downscale_premul(crop, size)
        Image.fromarray(small).save(A / f"{key}.png")
        # Wasserlinie: unterste Zeile mit Rumpf (im KI-Bild waagerecht abgeschnitten)
        meta["boats"][key] = {"size": list(size), "scale": s, "src_bbox": f["bbox"], "waterline_y": size[1]}
    # Kontaktschatten: flache Ellipse, 4-fach gezeichnet und verkleinert
    sw, sh = 120, 22
    big = Image.new("RGBA", (sw * 4, sh * 4), (0, 0, 0, 0))
    ImageDraw.Draw(big).ellipse((4, 4, sw * 4 - 4, sh * 4 - 4), fill=(28, 18, 40, 255))
    big.resize((sw, sh), Image.LANCZOS).save(A / "shadow.png")
    (A / "sprites.json").write_text(json.dumps(meta, indent=1))
    print("ok", len(frames), "Bilder", sheet.size, "root_x", meta["root_x"])


if __name__ == "__main__":
    main()
