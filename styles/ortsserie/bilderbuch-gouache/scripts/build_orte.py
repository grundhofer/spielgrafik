#!/usr/bin/env python3
"""Baut die drei Orte der Ortsserie im Stil bilderbuch-gouache spielfertig und kopiert sie in die Godot-Demo.

    .venv/bin/python -B styles/ortsserie/bilderbuch-gouache/scripts/build_orte.py

Eingänge: assets/raw/<ort>.png (agy, gewählte Variante A: Hafenbild des Stils als Stilreferenz).
Ausgänge
  assets/bg_<ort>.png        1280x720: bemalte Fläche ohne Papierrand (paperframe.py), 16:9, Lanczos
  assets/build.json          je Ort: Schnitt, Textlage und -farbe, automatisch gefundene Teile, Handarbeit
  demo/bilderbuch-gouache/art/bg_<ort>.png, <ort>.json, sway_klippe.png, paper.png, fx/*.png
Die Effekte sind mit der Pinselbibliothek des Eintrags bilderbuch-gouache gemalt (fx_orte.py).

Was automatisch geht und was von Hand
  automatisch  Papierrand und Schnitt, Sterne (find_stars aus bilderbuch-gouache), Fenster im Dorf (helle warme
               Flecken in einem Rechteck), Gras-Maske für den Wind (Farbton, Zusammenhangskomponenten),
               Textlage (ruhigste Stelle für den Textblock) und Textfarbe (nach Helligkeit der Stelle)
  von Hand     Mittelpunkte der Lichtquellen und Rechtecke für Glitzer/Lichtwanderung, im 20-px-Raster vergrößerter
               Ausschnitte abgelesen (HAND unten); gezählt in build.json → handwork
"""
import json, pathlib, shutil, sys

import numpy as np
from PIL import Image, ImageFilter, ImageFont

sys.dont_write_bytecode = True
HERE = pathlib.Path(__file__).resolve().parent
SD = HERE.parent
ROOT = HERE.parents[3]
sys.path.insert(0, str(HERE))
import fx_orte as F  # noqa: E402
import gmetrics as G  # noqa: E402
import paperframe as PF  # noqa: E402
from gutil import label  # noqa: E402  (aus styles/bilderbuch-gouache/scripts, über fx_orte im Pfad)

A = SD / "assets"
DEMO = ROOT / "styles/ortsserie/demo/bilderbuch-gouache"
ART = DEMO / "art"
FONT = DEMO / "fonts/Fraunces-var.ttf"
W, H = 1280, 720

CREAM, APRICOT = "#f8ecd6", "#f4b585"                 # Schrift im dunklen Himmel (wie der Hafen)
INK, TERRACOTTA = "#3b3352", "#8e4232"                # Schrift auf heller Wand: dunkelste Palettenfarbe

TEXT = {
    "leuchtturm": ("IM LEUCHTTURM", "Die große Linse dreht sich leise."),
    "stube": ("STUBE DES HAFENMEISTERS", "Im Kamin knistert die Glut."),
    "klippe": ("KLIPPENPFAD", "Unten im Hafen gehen die Lichter an."),
}
RAWS = {"leuchtturm": "leuchtturm_a.png", "stube": "stube.png", "klippe": "klippe.png"}
DY = {"leuchtturm": 0, "stube": 0, "klippe": 0}       # feste Verschiebung des Schnitts (Rohpixel); 0 = mittig
EXTERIOR = {"klippe"}                                 # Außenorte: Schnitt automatisch auf die Horizontzeile des Ankers
ANCHOR_HORIZON = 410                                  # Hafen des Stils: styles/bilderbuch-gouache/assets/scene.json

# Von Hand abgelesen, gespeichert in Rohbild-Pixeln (1264x848), damit sie einen geänderten Schnitt überstehen.
# Abgelesen wurden sie im 20-px-Raster vergrößerter Ausschnitte des geschnittenen Bildes und einmal umgerechnet.
HAND = {
    "leuchtturm": {
        "points": {"lamp": [431, 365]},
        "rects": {"lens": [368, 247, 504, 453], "wall": [518, 184, 904, 497]},
    },
    "stube": {
        "points": {"fire": [154, 635], "kettle_spout": [217, 539], "candle": [624, 439], "window_lamp": [974, 356]},
        "rects": {},
    },
    "klippe": {
        "points": {"lamp": [1129, 264]},
        "rects": {"sea": [217, 411, 1010, 452], "sea_left": [51, 608, 245, 682], "village": [42, 442, 226, 553]},
    },
}


def to_screen(ort, cinfo):
    """Handwerte aus Rohbild-Pixeln in Bildschirmpixel (1280x720) des aktuellen Schnitts."""
    x0, y0 = cinfo["crop"][0], cinfo["crop"][1]
    k = cinfo["scale"]
    pt = lambda p: [int(round((p[0] - x0) * k)), int(round((p[1] - y0) * k))]
    pts = {n: pt(p) for n, p in HAND[ort]["points"].items()}
    clamp = lambda r: [min(max(r[0], 0), W), min(max(r[1], 0), H), min(max(r[2], 0), W), min(max(r[3], 0), H)]
    rects = {n: clamp(pt(r[:2]) + pt(r[2:])) for n, r in HAND[ort]["rects"].items()}
    return pts, rects


# --- Schnitt ---------------------------------------------------------------------------------------------------------

def crop(ort):
    """Schnitt mittig (+ DY). Außenorte: Horizont im mittigen Schnitt messen und den Schnitt so verschieben, dass er
    auf der Horizontzeile des Hafens liegt, begrenzt auf den Rand, den das 3:2-Bild über 16:9 hinaus hat."""
    raw = np.asarray(Image.open(A / "raw" / RAWS[ort]).convert("RGB"))
    dy, hz0 = DY[ort], None
    if ort in EXTERIOR:
        x0, y0, x1, y1, _ = PF.crop_box(raw, 0)
        k = W / (x1 - x0)
        hz0 = horizon_row(np.asarray(Image.fromarray(raw).crop((x0, y0, x1, y1)).resize((W, H), Image.LANCZOS)))
        dy = int(round(hz0 / k - ANCHOR_HORIZON / k))      # Rohpixel; crop_box begrenzt auf den Spielraum
    x0, y0, x1, y1, info = PF.crop_box(raw, dy)
    bg = Image.fromarray(raw).crop((x0, y0, x1, y1)).resize((W, H), Image.LANCZOS)
    bg.save(A / f"bg_{ort}.png")
    return bg, {"raw_size": [raw.shape[1], raw.shape[0]], "painted_bbox": info["bbox"], "crop": [x0, y0, x1, y1],
                "scale": W / (x1 - x0), "slack_px": info["slack_px"], "dy_requested": dy,
                "horizon_row_centered": hz0}


def horizon_row(img, y0=200, y1=500):
    """Stärkster waagerechter Hell-Dunkel-Sprung über die ganze Breite (Median über Spalten)."""
    L = G.lum(img[:, ::4])
    g = np.abs(L[4:] - L[:-4])
    med = np.convolve(np.median(g, axis=1), np.ones(5) / 5, mode="same")
    k = int(np.argmax(med[y0:y1])) + y0 + 2
    return k


# --- Text ------------------------------------------------------------------------------------------------------------

def text_size(title, lines):
    ft = ImageFont.truetype(str(FONT), 17)
    fl = ImageFont.truetype(str(FONT), 31)
    tw = ft.getlength(title) + 3 * (len(title) - 1)
    lw = max(fl.getlength(x) for x in lines) * 1.04    # wght 480 ist etwas breiter als die Grundform
    return max(tw, lw), 28 + 40 * len(lines) + 4      # Titelzeile + Satzzeilen


def line_variants(line):
    """Satz in einer Zeile oder an der mittleren Wortgrenze in zwei Zeilen."""
    words = line.split()
    best = min(range(1, len(words)), key=lambda k: abs(len(" ".join(words[:k])) - len(" ".join(words[k:]))))
    return [[line], [" ".join(words[:best]), " ".join(words[best:])]]


def place_text(img, title, line):
    """Ruhigste Stelle für den Textblock (eine oder zwei Satzzeilen): kleinste Summe aus Gradientenenergie und
    Helligkeitsstreuung im Rechteck, leicht nach oben und zur Mitte gezogen (Bilderbuch: Text oben mittig).
    Die Streuung verhindert, dass der Block auf einer weichen Kante zwischen zwei Flächen sitzt (Decke/Wand)."""
    L = G.lum(img) * 100
    gm = G._sobel(L / 100) * 100

    def integ(a):
        return np.pad(a.cumsum(0).cumsum(1), ((1, 0), (1, 0)))

    ig, il, il2 = integ(gm), integ(L), integ(L * L)

    def box(ii, x0, y0, x1, y1):
        return ii[y1, x1] - ii[y0, x1] - ii[y1, x0] + ii[y0, x0]

    best = None
    for lines in line_variants(line):
        w, h = text_size(title, lines)
        bw, bh = int(w + 40), int(h + 12)
        for cx in range(440, 841, 10):
            x0 = int(cx - bw / 2)
            if x0 < 0 or x0 + bw > W:
                continue
            for y in range(18, 241, 5):
                y0 = y - 6
                if y0 + bh > H:
                    continue
                n = bw * bh
                g = box(ig, x0, y0, x0 + bw, y0 + bh) / n
                m = box(il, x0, y0, x0 + bw, y0 + bh) / n
                sd = np.sqrt(max(box(il2, x0, y0, x0 + bw, y0 + bh) / n - m * m, 0))
                score = g + 0.05 * sd + 0.002 * (y - 18) + 0.001 * abs(cx - 640) + 0.05 * (len(lines) - 1)
                if best is None or score < best[0]:
                    best = (score, cx, y, [x0, y0, x0 + bw, y0 + bh], lines)
    _, cx, y, rect, lines = best
    calm = G.calm(img, rect)
    dark = calm["L_mean"] > 62
    title_col, line_col = (TERRACOTTA, INK) if dark else (APRICOT, CREAM)
    rgb = tuple(int(line_col[i:i + 2], 16) for i in (1, 3, 5))
    con = G.contrast(rgb, img, rect)
    band = None
    if con["p05"] < 3.0:                               # zu unruhig/zu wenig Kontrast: gemalter dunkler Fleck
        band = [rect[0] - 20, rect[1] - 14, 0.88]
        title_col, line_col = APRICOT, CREAM
    return {"title": title, "line": "\n".join(lines), "cx": cx, "y": y, "rect": rect, "lines": len(lines),
            "scheme": "dunkel" if dark else "hell", "title_col": title_col, "line_col": line_col, "band": band,
            "calm": calm, "contrast": con}


# --- automatisch gefundene Teile ---------------------------------------------------------------------------------------

def village_windows(img, rect):
    """Kleine helle, warme Flecken (erleuchtete Fenster) in einem Rechteck."""
    x0, y0, x1, y1 = rect
    lab = G.oklab(img[y0:y1, x0:x1])
    L, a, b = lab[..., 0], lab[..., 1], lab[..., 2]
    m = (L > 0.72) & (b > 0.06)
    lb, n = label(m)
    out = []
    for i in range(1, n + 1):
        ys, xs = np.nonzero(lb == i)
        if 6 <= len(ys) <= 400:
            out.append([round(float(xs.mean()) + x0, 1), round(float(ys.mean()) + y0, 1)])
    return out


def sway_mask(img, y_min=430):
    """Grasbüschel (dunkles Grün) und Heide (Violett) unterhalb y_min; nur hohe Komponenten (Büschel, nicht die
    waagerechten Grenzen zwischen Gras und Sand). Gewicht steigt von der Basis (0) zur Spitze (1)."""
    lab = G.oklab(img)
    L, a, b = lab[..., 0], lab[..., 1], lab[..., 2]
    C = np.hypot(a, b)
    hue = np.degrees(np.arctan2(b, a)) % 360
    yy = np.arange(H)[:, None]
    tuft = (hue > 80) & (hue < 200) & (C > 0.03) & (L < 0.625) & (yy > y_min)
    heath = (hue > 250) & (hue < 345) & (C > 0.035) & (yy > 520)
    m = tuft | heath
    m = np.asarray(Image.fromarray(m.astype(np.uint8) * 255).filter(ImageFilter.MaxFilter(3))) > 0
    lb, n = label(m)
    w = np.zeros((H, W), np.float32)
    kept = 0
    for i in range(1, n + 1):
        ys, xs = np.nonzero(lb == i)
        hgt = ys.max() - ys.min() + 1
        wid = xs.max() - xs.min() + 1
        if hgt < 14 or hgt / wid < 0.3 or len(ys) < 40:
            continue
        kept += 1
        w[ys, xs] = np.clip((ys.max() - ys) / hgt, 0, 1) ** 0.8
    w = Image.fromarray((w * 255).astype(np.uint8)).filter(ImageFilter.MaxFilter(5))
    w = np.asarray(w.filter(ImageFilter.GaussianBlur(3)), np.float32)
    return Image.fromarray(np.clip(w, 0, 255).astype(np.uint8), "L"), kept


# --- Effekt-Texturen ----------------------------------------------------------------------------------------------------

def build_fx():
    fx = ART / "fx"
    fx.mkdir(parents=True, exist_ok=True)
    F.halo(7, 260, [1.0, 0.68, 0.4, 0.18], [(240, 200, 150), (246, 212, 156), (252, 226, 170), (255, 244, 212)]) \
        .save(fx / "halo_lamp.png")
    F.halo(9, 200, [1.0, 0.66, 0.38, 0.16], [(240, 170, 110), (248, 196, 128), (255, 220, 150), (255, 240, 200)]) \
        .save(fx / "halo_lantern.png")
    F.halo(13, 160, [1.0, 0.7, 0.45, 0.2], [(236, 168, 112), (246, 190, 126), (252, 210, 150), (255, 232, 190)]) \
        .save(fx / "halo_window.png")
    F.halo(21, 320, [1.0, 0.7, 0.45, 0.22], [(232, 140, 90), (240, 160, 100), (248, 186, 120), (255, 214, 150)]) \
        .save(fx / "halo_fire.png")
    F.halo(23, 300, [1.0, 0.72, 0.46, 0.22], [(246, 196, 128), (250, 210, 146), (253, 224, 168), (255, 238, 196)]) \
        .save(fx / "halo_wall.png")
    F.rays(17).save(fx / "rays.png")
    for i, (w, col, tint) in enumerate([(46, (250, 234, 204), (250, 206, 166)), (30, (244, 224, 198), None),
                                        (60, (250, 196, 150), (252, 222, 186)), (38, (206, 226, 222), None)]):
        F.stroke(40 + i, w, 4, col, tint, holes=0.2).save(fx / f"glint_{i}.png")
    F.star(70).save(fx / "star.png")
    for i in range(3):
        F.steam_puff(131 + i * 13).save(fx / f"steam_{i}.png")
    for i, lean in enumerate([-0.9, -0.2, 0.5, 1.0]):
        F.flame(150 + i * 3, lean=lean).save(fx / f"flame_{i}.png")
    F.sweep_light(170).save(fx / "sweep.png")
    F.text_band(101).save(fx / "band_text.png")
    F.paper().save(ART / "paper.png")


# --- Orte ---------------------------------------------------------------------------------------------------------------

def config(ort, bg, cinfo):
    img = np.asarray(bg)
    hp, hr = to_screen(ort, cinfo)
    title, line = TEXT[ort]
    text = place_text(img, title, line)
    stars = F.BS.find_stars(bg)
    c = {"bg": f"bg_{ort}.png", "seed": 20261013, "text_rect": text["rect"], "stars": stars,
         "text": {k: text[k] for k in ("title", "line", "cx", "y", "title_col", "line_col")}}
    if text["band"]:
        c["text"]["band"] = text["band"]
    auto = {"stars": len(stars)}
    if ort == "leuchtturm":
        lamp = hp["lamp"]
        c["halos"] = [{"tex": "halo_lamp", "pos": lamp, "scale": 1.15, "mode": "breathe", "period": 4.0,
                       "phase": -1.5708, "alpha": [0.35, 0.85], "grow": [0.9, 1.08]}]
        c["sweeps"] = [{"tex": "sweep", "rect": hr["lens"], "period": 4.0, "phase": 0.0, "alpha": 0.75},
                       {"tex": "halo_wall", "rect": hr["wall"], "period": 4.0, "phase": -0.6, "alpha": 0.6}]
    elif ort == "stube":
        fire = hp["fire"]
        c["halos"] = [{"tex": "halo_fire", "pos": [fire[0], fire[1] - 8], "scale": 1.0, "mode": "flicker",
                       "alpha": [0.22, 0.5], "grow": [0.92, 1.06]},
                      {"tex": "halo_lantern", "pos": [hp["candle"][0], hp["candle"][1] - 12], "scale": 0.7,
                       "mode": "flicker", "phase": 17.0, "alpha": [0.35, 0.75], "grow": [0.9, 1.05]},
                      {"tex": "halo_window", "pos": hp["window_lamp"], "scale": 0.22, "mode": "blink",
                       "period": 2.5, "alpha": [0.0, 0.95], "grow": [0.7, 1.1]}]
        c["flames"] = [{"tex": "flame", "frames": 4, "pos": [fire[0] - 22, fire[1] + 8], "scale": 0.3, "fps": 10,
                        "phase": 0.0},
                       {"tex": "flame", "frames": 4, "pos": [fire[0] + 2, fire[1] + 10], "scale": 0.36, "fps": 10,
                        "phase": 1.0},
                       {"tex": "flame", "frames": 4, "pos": [fire[0] + 24, fire[1] + 8], "scale": 0.28, "fps": 10,
                        "phase": 2.0},
                       {"tex": "flame", "frames": 4, "pos": hp["candle"], "scale": 0.17, "fps": 10, "phase": 3.0}]
        c["puffs"] = [{"tex": "steam", "pos": hp["kettle_spout"], "every": 0.55, "life": 2.8, "scale": 0.95,
                       "rise": 22.0, "drift": 14.0, "sway": 4.0, "alpha": 0.55}]
    elif ort == "klippe":
        lamp = hp["lamp"]
        wins = village_windows(img, hr["village"])
        auto["village_windows"] = len(wins)
        c["halos"] = [{"tex": "halo_lamp", "pos": lamp, "scale": 0.55, "mode": "blink", "period": 2.5, "phase": 0.6,
                       "alpha": [0.3, 1.0], "grow": [0.7, 1.05]}]
        c["halos"] += [{"tex": "halo_window", "pos": p, "scale": 0.13, "mode": "flicker", "phase": 11.0 * k,
                        "alpha": [0.15, 0.6], "grow": [0.9, 1.1]} for k, p in enumerate(wins)]
        c["rays"] = [{"pos": lamp, "scale": 0.5, "mode": "blink", "period": 2.5, "phase": 0.6}]
        c["glints"] = [{"rect": hr["sea"], "n": 14, "scale": 1.0}, {"rect": hr["sea_left"], "n": 4, "scale": 0.8}]
        mask, tufts = sway_mask(img)
        mask.save(ART / "sway_klippe.png")
        auto["grass_tufts"] = tufts
        c["sway"] = {"mask": "sway_klippe.png", "amp_px": 4.0}
    hand = {"points": len(hp), "rects": len(hr), "polygons": 0, "crop_overrides": int(DY[ort] != 0),
            "text_overrides": 0, "names": sorted(list(hp) + list(hr))}
    return c, text, auto, hand


def main():
    ART.mkdir(parents=True, exist_ok=True)
    build_fx()
    out = {}
    for ort in RAWS:
        bg, cinfo = crop(ort)
        shutil.copy2(A / f"bg_{ort}.png", ART / f"bg_{ort}.png")
        c, text, auto, hand = config(ort, bg, cinfo)
        (ART / f"{ort}.json").write_text(json.dumps(c, ensure_ascii=False, indent=1) + "\n")
        hz = horizon_row(np.asarray(bg)) if ort == "klippe" else None
        out[ort] = {"raw": f"assets/raw/{RAWS[ort]}", "crop": cinfo, "horizon_row": hz,
                    "text": {k: text[k] for k in ("line", "lines", "cx", "y", "rect", "scheme", "title_col",
                                                  "line_col", "band", "calm", "contrast")},
                    "auto": auto, "handwork": hand}
        print(ort, cinfo["crop"], "Text", text["cx"], text["y"], text["scheme"], text["contrast"], auto, hand["points"],
              hand["rects"])
    (A / "build.json").write_text(json.dumps(out, ensure_ascii=False, indent=1) + "\n")


if __name__ == "__main__":
    main()
