#!/usr/bin/env python3
"""Verarbeitet die agy-Rohbilder der Ortsserie mit der Pipeline des Eintrags pc98-adventure zu spielfertigen
Hintergründen (Indexbilder für die Godot-Szenen unter styles/ortsserie/demo/pc98-adventure/).

    .venv/bin/python styles/ortsserie/pc98-adventure/scripts/build_ort.py [ort ...] [--palette fixed|own]

Ablauf je Ort (wie scripts/build_assets.py des Eintrags pc98-adventure, dessen pc98lib wiederverwendet wird):
  1. Rohbild BOX-verkleinert auf 416 px Breite (416x279), CROP_TOP Zeilen oben weg -> Bildfenster 416x256.
  2. Palette, zwei Wege zum Vergleich:
       fixed  die 16 Register des Hafens unverändert (styles/pc98-adventure/demo/art/meta.json): 14 statische
              Farben, Register 14 (Licht, Grundwert ffeeaa) und 15 (Leuchtfeuer, ffffcc) animiert.
       own    wie beim Hafen je Bild neu: 5 feste Akzentfarben (000 edb 932 563 e97) + 9 freie Register per k-means
              in Oklab (Start: sprites.py palette --colors 14) + Register 14/15, alles auf 4 Bit je Kanal.
  3. Musterdithering (pc98lib.pattern_dither, 5 Mischstufen, Bayer 4x4, bildschirmfest).
  4. Lichter: in von Hand gesetzten Kästen mit Register 14 neu rastern (Lampe, Feuer, Kerze, Fenster).
  5. Leuchtfeuer bzw. Lichtblitz auf Register 15: helle Pixel im Lampenkasten, Rasterring als Schein und optional
     ein Strahl, Schein- und Strahlpixel nur auf Pixeln, die schon die Aus-Farbe des Registers haben.
  6. Wasser: Fläche über Farbton in von Hand gesetzten Kästen, Ausschlüsse als Polygone; Glanzstriche in 3
     Einzelbildern (weg, an ihrem Platz, um 2 px versetzt), Phase und Richtung je Strich mit festem Seed.
Ausgabe: demo/pc98-adventure/art/<ort>/{bg.png, water.png, meta.json} (Indexbilder R = G = B = Index * 17),
assets/<ort>_bg.png (Echtfarben, Blitz aus), assets/<ort>_bg_lit.png (Blitz an), assets/<ort>_bg_<palette>.png
(Vergleich, Register 15 an), assets/hafen_bg_<palette>.png (Anker mit beiden Paletten, ohne Lichter),
assets/build_stats.json (Handarbeit, Pixelzahlen, Palettenverlust je Ort und Palettenweg).
"""
import argparse, json, pathlib, subprocess, sys

sys.dont_write_bytecode = True        # nichts in fremde Ordner schreiben (Import aus styles/pc98-adventure)
import numpy as np  # noqa: E402
from PIL import Image, ImageDraw  # noqa: E402

HERE = pathlib.Path(__file__).resolve().parent
SD = HERE.parent
ROOT = SD.parents[2]
STYLE = ROOT / "styles" / "pc98-adventure"
sys.path.insert(0, str(STYLE / "scripts"))
sys.path.insert(0, str(HERE))
from pc98lib import (BAYER4, c12, colorize, hexc, index_png, kmeans_fixed, oklab, oklab_to_rgb,  # noqa: E402
                     pattern_dither, tohex, to_linear, lin_to_oklab)
import metrics  # noqa: E402

RAW = SD / "assets" / "raw"
ASSETS = SD / "assets"
DEMO_ART = ROOT / "styles" / "ortsserie" / "demo" / "pc98-adventure" / "art"
SCRATCH_ENV = "ORTSSERIE_SCRATCH"     # Zwischendateien (Median-Cut-Eingabe) nur im Scratchpad
PY = str(ROOT / ".venv" / "bin" / "python")
MODES = ("fixed", "own", "serie")

SCENE_X, SCENE_Y, SCENE_W, SCENE_H = 12, 12, 416, 256
LEVELS = 4
FIXED = {"black": "000000", "cream": "eeddbb", "red": "993322", "green": "556633", "peach": "ee9977"}
GLOW = ["ffeeaa", "ffdd99", "eecc88", "ffffbb"]   # Flackerstufen wie beim Hafen (Register 14)
LAMP_ON = "ffffcc"
HAFEN_META = STYLE / "demo" / "art" / "meta.json"
UI_COLORS = {"black": "000000", "cream": "eeddbb", "peach": "ee9977", "steel": "778899", "indigo": "444488",
             "navy": "222266", "plum": "221122"}

# --- Handarbeit je Ort: alles, was am verkleinerten Bild (416x256, Bildfenster) abgelesen wurde ---------------
# glow: Kästen (x0, y0, x1, y1), in denen Register 14 erlaubt ist; lamp: Kasten des Leuchtfeuers / Blitzlichts,
# Mitte, Scheinringe [(Radius, Deckung)], Strahl ja/nein, Aus-Farbe "auto" (häufigster Index im Schein);
# sea: Kästen der Wasserfläche, exclude: Polygone für Gegenstände im Wasser.
CONFIG = {
    "leuchtturm": {
        "crop_top": 10,
        "name": "Im Leuchtturm", "time": "Abenddämmerung",
        "text": ["Die große Lampe glimmt hinter ihren Glasringen.",
                 "Draußen versinkt das Meer im Abendblau."],
        "objects": ["Lampe", "Logbuch", "Fernrohr"],
        "glow": [(110, 62, 156, 136)],                       # Linse mit Lampe
        "glow_method": "redither",
        "glow_reg": {"mode": "pulse", "a": "eecc88", "b": "ffffcc", "period": 60, "hold": 3},
        "lamp": {"box": None, "center": (132.0, 102.0), "rings": [(36, 0.0), (50, 0.25), (64, 0.125)],
                 "beam": False, "off": "cccccc"},              # Blitz als warmer Lichtring auf der hellen Wand
        "lamp_reg": {"mode": "flash", "period": 90, "phase": 25},
        "sea": {"boxes": [(183, 128, 234, 150), (306, 128, 351, 155)], "exclude": []},
    },
    "stube": {
        "crop_top": 10,
        "name": "Hafenmeisterstube", "time": "Abenddämmerung",
        "text": ["Im Kamin glüht die Asche, die Kerze flackert.",
                 "Fern im Fenster blinkt der Leuchtturm."],
        "objects": ["Teekanne", "Seekarte", "Ölzeug"],
        "glow": [(28, 118, 94, 230), (190, 112, 222, 142)],   # Kamin mit Glut, Kerze mit Schein
        "glow_method": "swap", "glow_swap": ["ee9977"],
        "glow_reg": {"mode": "flicker", "steps": ["ee9977", "ffaa88", "dd8866", "ffbb99"], "hold": 3, "seed": 11},
        "lamp": {"box": (292, 86, 300, 96), "center": (296.0, 91.0), "rings": [(2, 0.0), (4, 0.25), (6, 0.125)],
                 "beam": False},
        "lamp_reg": {"mode": "flash", "period": 90, "phase": 25},
        "sea": {"boxes": [(262, 106, 304, 128)], "exclude": []},
    },
    "klippe": {
        "crop_top": 10,
        "name": "Klippenpfad", "time": "Abenddämmerung",
        "text": ["Der Pfad führt an der Kante entlang zum Leuchtturm.",
                 "Unten im Hafen gehen die ersten Lichter an."],
        "objects": ["Wegweiser", "Bank", "Zaun"],
        "glow": [(384, 82, 404, 94), (0, 178, 44, 242)],     # Fenster am Leuchtturmhaus, Fenster im Hafen
        "glow_method": "swap", "glow_swap": ["eeddbb", "ee9977"],
        "glow_reg": {"mode": "flicker", "steps": GLOW, "hold": 3, "seed": 11},
        "lamp": {"box": (366, 20, 384, 38), "center": (375.0, 29.0), "rings": [(5, 0.0), (9, 0.25), (13, 0.125)],
                 "beam": 135},
        "lamp_reg": {"mode": "flash", "period": 90, "phase": 25},
        "sea": {"boxes": [(0, 132, 300, 150), (0, 150, 170, 192)], "exclude": []},
    },
}


def poly_mask(h, w, poly):
    m = Image.new("L", (w, h), 0)
    ImageDraw.Draw(m).polygon([tuple(p) for p in poly], fill=255)
    return np.asarray(m) > 0


def ring_dither(h, w, cx, cy, radii_levels, ox, oy):
    """Bayer-Raster in Ringen um (cx, cy): [(Radius, Deckung 0..1), ...] (wie build_assets.ring_dither)."""
    yy, xx = np.mgrid[0:h, 0:w]
    d = np.hypot(xx + 0.5 - cx, (yy + 0.5 - cy))
    th = (BAYER4[(yy + oy) % 4, (xx + ox) % 4] + 0.5) / 16.0
    cov = np.zeros((h, w), np.float32)
    prev = 0.0
    for r, c in radii_levels:
        cov[(d >= prev) & (d < r)] = c
        prev = r
    return th < cov


def load_bg(ort, cfg):
    im = Image.open(RAW / f"{ort}.png").convert("RGB")
    h = round(im.height * SCENE_W / im.width)
    s = im.resize((SCENE_W, h), Image.BOX).crop((0, cfg["crop_top"], SCENE_W, cfg["crop_top"] + SCENE_H))
    return np.asarray(s)


def palette_fixed():
    meta = json.loads(HAFEN_META.read_text())
    return np.array([hexc(h) for h in meta["palette"]]), {"source": "Hafen (styles/pc98-adventure)"}


def palette_own(bg, ort, per_image=None):
    scratch = pathlib.Path(__import__("os").environ.get(SCRATCH_ENV, "/tmp"))
    scratch.mkdir(parents=True, exist_ok=True)
    tmp = scratch / f"_palsrc_{ort}.png"
    Image.fromarray(bg).save(tmp)
    out = subprocess.run([PY, str(ROOT / "tools/sprites.py"), "palette", str(tmp), str(scratch / f"_pal_{ort}.png"),
                          "--colors", "14"], capture_output=True, text=True, check=True).stdout.split()
    mediancut = out[:14]
    n_free = 16 - len(FIXED) - 2
    rng = np.random.default_rng(1)
    if per_image:
        lab = np.vstack([oklab(p[rng.choice(len(p), min(8000, len(p)), replace=False)]) for p in per_image])
        sel = np.arange(len(lab))
    else:
        lab = oklab(bg.reshape(-1, 3))
        sel = rng.choice(len(lab), min(30000, len(lab)), replace=False)
    init = oklab(np.array([hexc(h) for h in mediancut[:n_free]]))
    fixed = oklab(np.array([hexc(h) for h in list(FIXED.values()) + [GLOW[0], LAMP_ON]]))
    free = kmeans_fixed(lab[sel], fixed, init)
    pal = np.vstack([np.array([hexc(h) for h in FIXED.values()]), c12(oklab_to_rgb(free)),
                     np.array([hexc(GLOW[0]), hexc(LAMP_ON)])])
    if len({tohex(c) for c in pal}) < 16:
        print(f"WARNUNG {ort}: doppelte Registerfarben nach 4-Bit-Rundung")
    return pal, {"source": "eigene k-means-Palette", "mediancut_14": mediancut}


def load_hafen_src():
    """Quelle des Hafens wie in build_assets.load_bg: BOX auf 416x279, Zeilen 10–265."""
    im = Image.open(STYLE / "assets/raw/bg.png").convert("RGB")
    return np.asarray(im.resize((SCENE_W, 279), Image.BOX).crop((0, 10, SCENE_W, 10 + SCENE_H)))


_SERIE = {}


def palette_serie():
    """Eine Palette für die ganze Serie: wie palette_own, aber über Hafen + alle drei Orte zugleich (je Bild
    gleich viele Stichproben), damit alle Orte dieselben 16 Register teilen."""
    if "pal" in _SERIE:
        return _SERIE["pal"], _SERIE["info"]
    srcs = [load_hafen_src()] + [load_bg(o, CONFIG[o]) for o in CONFIG]
    comp = np.vstack(srcs)
    pal, info = palette_own(comp, "serie", per_image=[s.reshape(-1, 3) for s in srcs])
    info["source"] = "gemeinsame k-means-Palette über Hafen, Leuchtturm, Stube, Klippe"
    _SERIE["pal"], _SERIE["info"] = pal, info
    return pal, info


def nearest_idx(pal, hx, allowed=None):
    d = ((oklab(np.asarray(pal)) - oklab(hexc(hx)[None])) ** 2).sum(-1)
    if allowed is not None:
        mask = np.full(len(pal), np.inf)
        mask[list(allowed)] = 0
        d = d + mask
    return int(d.argmin())


def _blur4(a):
    """4x4-Kastenmittel (Periode des Bayer-Rasters), Ränder per Randwiederholung."""
    p = np.pad(a, ((2, 1), (2, 1), (0, 0)), mode="edge")
    c = p.cumsum(0).cumsum(1)
    c = np.pad(c, ((1, 0), (1, 0), (0, 0)))
    return (c[4:, 4:] - c[:-4, 4:] - c[4:, :-4] + c[:-4, :-4]) / 16.0


def palette_loss(src, idx, pal, k=10):
    """Was die Palette verliert: ΔE (Oklab ×100) zwischen Quelle und gerastertem Bild, beide 4x4 gemittelt in
    linearem Licht (so mischt das Auge das Raster). Dazu die Quellfarben in k Gruppen (k-means) mit Anteil,
    Quellfarbe, Ergebnisfarbe und ΔE je Gruppe."""
    ls = _blur4(to_linear(src))
    lo = _blur4(to_linear(np.asarray(pal)[idx]))
    a, b = lin_to_oklab(ls.reshape(-1, 3)), lin_to_oklab(lo.reshape(-1, 3))
    de = np.sqrt(((a - b) ** 2).sum(-1)) * 100
    cent, _ = metrics.kmeans(a[np.random.default_rng(0).choice(len(a), 15000, replace=False)], k)
    lbl = ((a[:, None] - cent[None]) ** 2).sum(-1).argmin(1)
    groups = []
    for j in range(k):
        m = lbl == j
        if not m.any():
            continue
        groups.append({"share": round(float(m.mean()), 3),
                       "src": tohex(oklab_to_rgb(a[m].mean(0))), "out": tohex(oklab_to_rgb(b[m].mean(0))),
                       "dE": round(float(de[m].mean()), 1)})
    groups.sort(key=lambda g: -g["dE"])
    return {"dE_mean": round(float(de.mean()), 2), "dE_p90": round(float(np.percentile(de, 90)), 2),
            "groups": groups}


def build(ort, mode, write_demo):
    cfg = CONFIG[ort]
    bg = load_bg(ort, cfg)
    pal, pinfo = {"fixed": palette_fixed, "own": lambda: palette_own(bg, ort), "serie": palette_serie}[mode]()
    G, LMP = 14, 15
    static = list(range(14))
    H, W = SCENE_H, SCENE_W
    idx = pattern_dither(bg, pal, allowed=static, levels=LEVELS, ox=SCENE_X, oy=SCENE_Y)
    loss_static = palette_loss(bg, idx, pal)

    # Lichter (Register 14) in Handkästen: "redither" rastert den Kasten mit erlaubtem Register 14 neu (Lampe,
    # deren Farbe nahe am Grundwert ffeeaa liegt); "swap" legt Pixel bestimmter Registerfarben mit warmer Quelle
    # (R > B + 20) auf Register 14, dessen Grundwert dann diese Farbe ist (Feuerschein, Kerze, kleine Fenster) –
    # das Rastermuster bleibt erhalten, nur diese Pixel flackern.
    pal = np.array(pal).copy()
    if cfg["glow_method"] == "swap":
        pal[G] = hexc(cfg["glow_reg"]["steps"][0])
        swap = [nearest_idx(pal, h, static) for h in cfg["glow_swap"]]
    for (x0, y0, x1, y1) in cfg["glow"]:
        if cfg["glow_method"] == "redither":
            idx[y0:y1, x0:x1] = pattern_dither(bg[y0:y1, x0:x1], pal, allowed=static + [G], levels=LEVELS,
                                               ox=SCENE_X + x0, oy=SCENE_Y + y0)
        else:
            sb = bg[y0:y1, x0:x1].astype(int)
            sub = idx[y0:y1, x0:x1]
            sub[np.isin(sub, swap) & (sb[..., 0] > sb[..., 2] + 20)] = G
    glow_px = int((idx == G).sum())

    # Leuchtfeuer / Blitz (Register 15)
    lc = cfg["lamp"]
    cx, cy = lc["center"]
    lamp_core = 0
    if lc["box"]:
        x0, y0, x1, y1 = lc["box"]
        lb = bg[y0:y1, x0:x1].astype(int)
        bright = (lb.sum(-1) > 480) & (lb[..., 0] > lb[..., 2] + 20)
        idx[y0:y1, x0:x1][bright] = LMP
        lamp_core = int(bright.sum())
    halo = ring_dither(H, W, cx, cy, lc["rings"], SCENE_X, SCENE_Y)
    yy, xx = np.mgrid[0:H, 0:W]
    zone = ring_dither(H, W, cx, cy, [(lc["rings"][0][0], 0.0)] + [(r, 1.0) for r, _ in lc["rings"][1:]],
                       SCENE_X, SCENE_Y)
    beam = np.zeros((H, W), bool)
    if lc["beam"]:
        dx = cx - (xx + 0.5)
        dy = (yy + 0.5) - cy
        in_beam = (dx > 6) & (dx < lc["beam"]) & (np.abs(dy) < 0.8 + dx * 0.03)
        th = (BAYER4[(yy + SCENE_Y) % 4, (xx + SCENE_X) % 4] + 0.5) / 16.0
        beam = in_beam & (th < np.where(dx < 35, 0.5, np.where(dx < 85, 0.25, 0.125)))
        zone |= in_beam
    zidx = idx[zone & (idx < 14)]
    if lc.get("off"):
        off_idx = nearest_idx(pal, lc["off"], static)
    else:
        off_idx = int(np.bincount(zidx, minlength=16).argmax()) if zidx.size else 0
    lamp_extra = (halo | beam) & (idx == off_idx)
    idx[lamp_extra] = LMP

    # Wasser: 3 Einzelbilder der Glanzstriche
    sea = np.zeros((H, W), bool)
    for (x0, y0, x1, y1) in cfg["sea"]["boxes"]:
        sea[y0:y1, x0:x1] = True
    sea &= (bg[..., 2].astype(int) > bg[..., 0] + 15)
    for poly in cfg["sea"]["exclude"]:
        sea &= ~poly_mask(H, W, poly)
    lum = oklab(pal)[:, 0]
    light = sea & (lum[idx] > 0.55) & (idx < 14)
    fill = idx.copy()
    for y, x in zip(*np.nonzero(light)):
        for d_ in (4, -4, 8, -8):
            y2 = y + d_
            if 0 <= y2 < H and sea[y2, x] and not light[y2, x]:
                fill[y, x] = idx[y2, x]
                break
    rng = np.random.default_rng(5)
    dashes = []
    for y in range(H):
        xs_ = np.flatnonzero(light[y])
        if xs_.size == 0:
            continue
        start = prev = xs_[0]
        for x in list(xs_[1:]) + [None]:
            if x is None or x != prev + 1:
                dashes.append((y, start, prev + 1, int(rng.integers(3)), int(rng.choice([-1, 1]))))
                if x is None:
                    break
                start = x
            prev = x
    base = np.where(light, fill, idx)
    frames = []
    for k in range(3):
        f = base.copy()
        for y, xa, xb, ph, d_ in dashes:
            st = (ph + k) % 3
            if st == 0:
                continue
            off = 0 if st == 1 else 2 * d_
            for x in range(xa, xb):
                nx = x + off
                if 0 <= nx < W and sea[y, nx]:
                    f[y, nx] = idx[y, x]
        frames.append(f)
    changed = np.zeros((H, W), bool)
    for f in frames:
        changed |= f != frames[0]
    idx_base = frames[0]

    ui = {k: nearest_idx(pal, hx, static) for k, hx in UI_COLORS.items()}
    off_hex = tohex(pal[off_idx])
    gr = dict(cfg["glow_reg"], index=G)
    lr = dict(cfg["lamp_reg"], index=LMP, off=off_hex, on=LAMP_ON)
    meta = {
        "ort": ort, "name": cfg["name"], "time": cfg["time"], "text": cfg["text"], "objects": cfg["objects"],
        "palette": [tohex(c) for c in pal], "palette_mode": mode, "palette_info": pinfo,
        "scene": [SCENE_X, SCENE_Y, SCENE_W, SCENE_H], "ui": ui,
        "registers": [gr, lr],
        "strips": ([{"file": "water.png", "frames": 3, "hold": 6, "pos": [0, 0]}] if changed.any() else []),
    }
    handwork = {"glow_boxes": len(cfg["glow"]), "lamp_box": int(bool(lc["box"])), "lamp_center": 1,
                "lamp_rings": len(lc["rings"]), "beam": int(bool(lc["beam"])), "lamp_off": int(bool(lc.get("off"))),
                "sea_boxes": len(cfg["sea"]["boxes"]), "sea_polygons": len(cfg["sea"]["exclude"]),
                "crop_top": 1, "texts": len(cfg["text"]) + len(cfg["objects"]) + 1}
    handwork["entries_total"] = sum(v for k, v in handwork.items() if k != "texts")
    stats = {"palette_mode": mode, "palette": meta["palette"], "loss_static": loss_static,
             "glow_px": glow_px, "lamp_core_px": lamp_core, "lamp_extra_px": int(lamp_extra.sum()),
             "lamp_off": off_hex, "water_px": int(sea.sum()), "water_dashes": len(dashes),
             "water_changed_px": int(changed.sum()), "handwork": handwork,
             "colors_used": int(len(np.unique(idx_base)))}

    prev = colorize(idx_base, pal).copy()
    prev_on = prev.copy()
    Image.fromarray(prev).save(ASSETS / f"{ort}_bg_{mode}.png")
    if write_demo:
        out = DEMO_ART / ort
        out.mkdir(parents=True, exist_ok=True)
        Image.fromarray(index_png(idx_base)).save(out / "bg.png")
        if changed.any():
            strip = np.zeros((H, W * 3), np.int32)
            salpha = np.zeros((H, W * 3), bool)
            for k, f in enumerate(frames):
                strip[:, k * W:(k + 1) * W] = f
                salpha[:, k * W:(k + 1) * W] = changed
            Image.fromarray(index_png(strip, salpha)).save(out / "water.png")
        (out / "meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=1) + "\n")
        pal_off = np.array(pal).copy()
        pal_off[LMP] = pal[off_idx]                    # Grundzustand: Blitz aus (wie zwischen den Blitzen)
        Image.fromarray(colorize(idx_base, pal_off)).save(ASSETS / f"{ort}_bg.png")
        pal_on = np.array(pal).copy()
        pal_on[LMP] = hexc(LAMP_ON)
        prev_on = colorize(idx_base, pal_on)
        Image.fromarray(prev_on).save(ASSETS / f"{ort}_bg_lit.png")
    return stats


def build_static(name, mode):
    """Gegenproben (leuchtturm_a/_b, klippe_b) nur statisch: verkleinern, Palette, Musterdithering; keine Lichter,
    keine Handarbeit. Für den Vergleich der Varianten nach der Pipeline."""
    im = Image.open(RAW / f"{name}.png").convert("RGB")
    # leuchtturm_a/_b haben einen gemalten Rahmen: Rahmenbreite aus dem Rohbild (gemessen), vor dem Verkleinern weg
    border = {"leuchtturm_a": 22, "leuchtturm_b": 34}.get(name, 0)
    if border:
        im = im.crop((border, border, im.width - border, im.height - border))
    h = round(im.height * SCENE_W / im.width)
    top = (h - SCENE_H) // 2 if border else 10
    bg = np.asarray(im.resize((SCENE_W, h), Image.BOX).crop((0, top, SCENE_W, top + SCENE_H)))
    pal, _ = {"fixed": palette_fixed, "own": lambda: palette_own(bg, name), "serie": palette_serie}[mode]()
    idx = pattern_dither(bg, pal, allowed=list(range(14)), levels=LEVELS, ox=SCENE_X, oy=SCENE_Y)
    Image.fromarray(colorize(idx, pal)).save(ASSETS / f"{name}_bg_{mode}.png")
    return {"loss_static": palette_loss(bg, idx, pal), "border_cropped_px": border}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--alt", nargs="*", default=[], help="Gegenproben nur statisch verarbeiten (z. B. klippe_b)")
    ap.add_argument("orte", nargs="*")
    ap.add_argument("--palette", choices=MODES, default="fixed", help="Palette für die Demo")
    a = ap.parse_args()
    orte = a.orte or [o for o in CONFIG if (RAW / f"{o}.png").exists()]
    sf = ASSETS / "build_stats.json"
    allstats = json.loads(sf.read_text()) if sf.exists() else {}
    for ort in orte:
        res = {}
        for mode in MODES:
            res[mode] = build(ort, mode, write_demo=(mode == a.palette))
        res["demo_palette"] = a.palette
        allstats[ort] = res
        print(ort, {m: (res[m]["loss_static"]["dE_mean"], res[m]["colors_used"]) for m in MODES},
              res[a.palette]["handwork"]["entries_total"], "Handeinträge")
    for name in a.alt:
        allstats.setdefault("gegenproben", {})[name] = {m: build_static(name, m) for m in MODES}
        print(name, {m: allstats["gegenproben"][name][m]["loss_static"]["dE_mean"] for m in MODES})
    # Hafen (Anker) mit seiner eigenen Palette und mit der Serienpalette: was die Serienpalette dort kostet
    hsrc = load_hafen_src()
    hstat = {}
    for mode, (pal, _) in (("fixed", palette_fixed()), ("serie", palette_serie())):
        hidx = pattern_dither(hsrc, pal, allowed=list(range(14)), levels=LEVELS, ox=SCENE_X, oy=SCENE_Y)
        hstat[mode] = {"palette": [tohex(c) for c in pal], "loss_static": palette_loss(hsrc, hidx, pal)}
        Image.fromarray(colorize(hidx, pal)).save(ASSETS / f"hafen_bg_{mode}.png")
    allstats["hafen"] = hstat
    print("hafen", {m: hstat[m]["loss_static"]["dE_mean"] for m in hstat})
    sf.write_text(json.dumps(allstats, ensure_ascii=False, indent=1) + "\n")


if __name__ == "__main__":
    main()
