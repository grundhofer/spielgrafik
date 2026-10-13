#!/usr/bin/env python3
"""Bereitet den KI-Hintergrund für die Dialogszene vor.

    .venv/bin/python styles/lebendes-portraet/tools/prep_bg.py [--src assets/raw/bg.png] [--out DIR]

- schneidet 3:2 auf 16:9 (crop_top aus bg_config.json, sonst mittig) und verkleinert auf 1280×720
- Wassermaske: Fläche zwischen Horizont und Kai (Polygon aus bg_config.json), ohne Rümpfe, Steg und Felsen
  (enge Polygone); nur blau-violette und spiegelnde warme Töne gelten als Wasser; dünne Linien (Takelage, Kran,
  Masten) werden über die Farbe ausgenommen (dunkler als das Wasser ringsum oder warm ohne waagerechte
  Spiegelung), weich gezeichnet
- Glitzermaske: helle, warme Spiegelungen im Wasser
- Lichter (Leuchtturmlampe, Laterne, Fenster): hellster warmer Punkt im jeweiligen Suchrechteck
Ausgabe: demo/art/bg.png, demo/art/bg_masks.png, demo/art/bg_layout.json, assets/bg.png, assets/bg_debug.png
"""
import argparse, json, pathlib, sys

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import imgops as ops  # noqa: E402

HERE = pathlib.Path(__file__).resolve().parent.parent
CFG = json.loads((HERE / "tools" / "bg_config.json").read_text())


def brightest_warm(rgb, box):
    x0, y0, x1, y1 = box
    sub = rgb[y0:y1, x0:x1].astype(np.float32) / 255
    lum = sub.mean(-1)
    warm = sub[..., 0] - sub[..., 2]
    score = lum + 0.5 * np.clip(warm, 0, 1)
    sc = np.asarray(Image.fromarray((np.clip(score / 1.5, 0, 1) * 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(2)), np.float32)
    iy, ix = np.unravel_index(int(np.argmax(sc)), sc.shape)
    return [int(x0 + ix), int(y0 + iy)]


def h_open(mask, run):
    """Waagerechtes Öffnen: behält nur Pixel in waagerechten Läufen von mindestens run Pixeln."""
    if run <= 1:
        return mask.copy()
    m = np.pad(mask, ((0, 0), (run, run)))
    w = mask.shape[1]
    er = np.ones_like(mask)
    for d in range(run):
        er &= m[:, run + d:run + d + w]   # Lauf beginnt hier und reicht run px nach rechts
    out = np.zeros_like(mask)
    e = np.pad(er, ((0, 0), (run, run)))
    for d in range(run):
        out |= e[:, run - d:run - d + w]
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", default=str(HERE / "assets/raw/bg.png"))
    ap.add_argument("--out", default=str(HERE / "demo/art"))
    a = ap.parse_args()
    out = pathlib.Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    im = Image.open(a.src).convert("RGB")
    w, h = im.size
    ch = round(w * 9 / 16)
    top = CFG.get("crop_top")
    top = (h - ch) // 2 if top is None else int(top * h / 1024)
    im = im.crop((0, top, w, top + ch)).resize((1280, 720), Image.LANCZOS)
    if CFG.get("blur", 0) > 0:
        im = im.filter(ImageFilter.GaussianBlur(CFG["blur"]))
    rgb = np.asarray(im)
    im.save(out / "bg.png")
    im.save(HERE / "assets" / "bg.png")

    # Wasser
    poly = Image.new("L", (1280, 720), 0)
    ImageDraw.Draw(poly).polygon([tuple(p) for p in CFG["water_poly"]], fill=255)
    for ex in CFG.get("water_exclude", []):
        ImageDraw.Draw(poly).polygon([tuple(p) for p in ex], fill=0)
    region = np.asarray(poly) > 127
    f = rgb.astype(np.float32) / 255
    hsv = np.asarray(im.convert("HSV"), np.float32) / 255
    hue, sat, val = hsv[..., 0], hsv[..., 1], hsv[..., 2]
    bluish = (hue > CFG["water_hue"][0]) & (hue < CFG["water_hue"][1])
    warm = (hue < 0.17) | (hue > 0.95)
    # Spiegelungen sind waagerechte Striche; Masten und angestrahlte Kanten sind senkrecht und schmal.
    # Warme helle Pixel zählen nur als Wasser, wenn sie in einem waagerechten Lauf von mindestens refl_run px liegen.
    warm_refl = h_open(region & (val > CFG["refl_val"]) & warm, CFG.get("refl_run", 4))
    water = region & (bluish | warm_refl | (sat < 0.18))
    water = ops.close(ops.open_(water, 1), 2)
    comps = ops.components(water, min_area=CFG.get("water_min_area", 400))
    wm = np.zeros_like(water)
    for _, m in comps:
        wm |= m
    # Dünne Linien (Takelage, Kran, Masten, Pfahlkanten) statt großer Polygone über die Farbe ausnehmen:
    # deutlich dunkler als das Wasser ringsum oder warm, ohne waagerechte Spiegelung zu sein
    # Bezug: blaues Wasser ohne Spiegelungen (sonst gelten die Lücken zwischen Spiegelstrichen als Linie)
    known = (wm & bluish & ~(warm & (val > 0.4))).astype(np.float32)
    lv = ops.blur(val * known, CFG.get("line_radius", 4)) / np.maximum(ops.blur(known, CFG.get("line_radius", 4)), 1e-3)
    dark = (val < lv - CFG.get("line_dark", 0.1)) & (ops.blur(known, CFG.get("line_radius", 4)) > 0.05)
    # Masten: warme, gesättigte Pixel in senkrechten Läufen (Spiegelstriche sind flach und breit)
    run = CFG.get("mast_run", 8)
    wsat = warm & (sat > 0.3)
    mast = h_open(wsat.T, run).T & ~h_open(wsat, run)
    line = region & (dark | mast)
    line[CFG.get("line_y_max", 720):] = False   # darunter liegen nur Spiegelungen der Rümpfe und Pfähle
    line = ops.dilate(line, 1)
    wm &= ~line
    water_soft = ops.blur(ops.erode(wm, 1).astype(np.float32), 1.2)
    glint = (wm & warm_refl).astype(np.float32)
    glint = ops.blur(ops.dilate(glint > 0, 1).astype(np.float32), 1.0)
    masks = np.zeros((720, 1280, 3), np.uint8)
    masks[..., 0] = (water_soft * 255).astype(np.uint8)
    masks[..., 1] = (glint * 255).astype(np.uint8)
    Image.fromarray(masks).save(out / "bg_masks.png")

    layout = {}
    for k in ("lamp", "lantern", "window"):
        if CFG.get(k):
            layout[k] = CFG[k]
        elif CFG.get(k + "_box"):
            layout[k] = brightest_warm(rgb, CFG[k + "_box"])
    if CFG.get("params_panel"):
        layout["params"] = CFG["params_panel"]
    layout["horizon"] = CFG["horizon"]
    layout["near"] = CFG["near"]
    (out / "bg_layout.json").write_text(json.dumps(layout, indent=1))

    dbg = im.convert("RGBA")
    ov = np.zeros((720, 1280, 4), np.uint8)
    ov[..., 2] = 255
    ov[..., 3] = (water_soft * 110).astype(np.uint8)
    ov[glint > 0.3] = [255, 255, 0, 200]
    ov[line & region] = [255, 0, 0, 160]
    dbg.alpha_composite(Image.fromarray(ov, "RGBA"))
    d = ImageDraw.Draw(dbg)
    for k, p in layout.items():
        if isinstance(p, list):
            d.ellipse((p[0] - 8, p[1] - 8, p[0] + 8, p[1] + 8), outline=(255, 0, 0, 255), width=2)
            d.text((p[0] + 10, p[1] - 6), k, fill=(255, 255, 255, 255))
    d.line([(0, CFG["horizon"]), (1280, CFG["horizon"])], fill=(0, 255, 0, 160))
    dbg.convert("RGB").save(HERE / "assets" / "bg_debug.png")
    print(json.dumps(layout), f"Wasseranteil {water_soft.mean():.3f}, Glitzer {float((glint > 0.3).mean()):.4f}, Linien {float((line & region).mean()):.4f}")


if __name__ == "__main__":
    main()
