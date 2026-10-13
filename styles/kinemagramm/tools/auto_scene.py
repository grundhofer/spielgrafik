#!/usr/bin/env python3
"""Leitet aus Gemälde (und KI-Farbcode-Maske) die Szenen-Konfiguration für prep.py ab.

    .venv/bin/python styles/kinemagramm/tools/auto_scene.py --bg assets/raw/bg.png [--mask assets/raw/mask.png]
        --config-out CFG.json [--labels-out assets/mask_ai.png] [--base ENTRY] [--debug DIR]

Mit Maske: Codes einordnen, Maske an das Gemälde ausrichten (Verschiebung und Skalierung, gemessen an Kanten),
16:9-Ausschnitt so wählen, dass Leuchtfeuer und Schornstein Luft nach oben haben, dann Lage von Lichtern,
Schornstein, Drehpunkten der Boote, Horizont, Kai, Möwen und Dachs ausrechnen. Ergebnis ist vollständig.
Ohne Maske: nur ein Entwurf (Lichter aus dem Gemälde geschätzt, Horizont geschätzt, Himmel/Wasser als
Rechtecke), Exit-Code 3; Polygone von Hand nach tools/scene.hand.json übernehmen.
Im Debug-Ordner: scene_overlay.png (Masken, Punkte und ein 50-px-Raster zum Ablesen von Koordinaten).
"""
import argparse, json, os, pathlib, sys

import numpy as np
from PIL import Image, ImageDraw

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import aimask as A  # noqa: E402
import imgops as K  # noqa: E402
from prep import load_still, W, H  # noqa: E402

UI = {"x": 645, "y": 530, "w": 615, "h": 182}
BADGER_H = 230
LIGHT_DEFAULTS = {  # Kanal, Lichthof-Radius, gemalter Lichtschein (Radius)
    "window": {"channel": "window", "glow": 70, "pool_r": 130},
    "lantern": {"channel": "lantern", "glow": 80, "pool_r": 280},
    "lamp": {"channel": "lamp", "glow": 40},
}


def relp(p, base):
    p = pathlib.Path(p).resolve()
    try:
        return os.path.relpath(p, base) if base in p.parents or p == base else str(p)
    except ValueError:
        return str(p)


def warmth(img):
    return np.clip((img[..., 0] - img[..., 2]) * 2.0, 0, 1)


def light_at(img, ys, xs, name):
    """Lage einer Lichtquelle: hellster warmer Punkt im (leicht erweiterten) Bereich, Radius aus der Größe."""
    y0, y1 = max(0, ys.min() - 6), min(H, ys.max() + 7)
    x0, x1 = max(0, xs.min() - 6), min(W, xs.max() + 7)
    sub = img[y0:y1, x0:x1]
    wgt = (K.luma(sub) * (0.5 + warmth(sub))) ** 4
    yy, xx = np.mgrid[y0:y1, x0:x1]
    s = wgt.sum()
    pos = [float((xx * wgt).sum() / s), float((yy * wgt).sum() / s)] if s > 1e-9 else \
        [float(xs.mean()), float(ys.mean())]
    ext = max(xs.max() - xs.min(), ys.max() - ys.min()) / 2.0
    r = max(12.0 if name == "lamp" else 14.0, ext * 1.3 + 4)
    d = dict(LIGHT_DEFAULTS[name])
    d.update({"name": name, "pos": [round(pos[0], 1), round(pos[1], 1)], "r": round(r, 1)})
    return d


def detect_lights(img):
    """Ohne Maske: warme, helle Flecken im Gemälde den Rollen Fenster, Laterne, Leuchtfeuer zuordnen (Schätzung)."""
    s = K.luma(img) * warmth(img)
    thr = max(0.22, float(np.percentile(s, 99.85)))
    comps = A.components(s > thr, min_px=4)
    cand = []
    for ys, xs in comps[:40]:
        cand.append({"x": float(xs.mean()), "y": float(ys.mean()), "area": len(ys), "peak": float(s[ys, xs].max()),
                     "ys": ys, "xs": xs})
    out = {}
    lamp = [c for c in cand if c["x"] > 0.5 * W and c["y"] < 0.5 * H]
    if lamp:
        out["lamp"] = max(lamp, key=lambda c: c["peak"])
    win = [c for c in cand if c["x"] < 0.3 * W]
    if win:
        out["window"] = max(win, key=lambda c: c["area"])
    lan = [c for c in cand if 0.12 * W < c["x"] < 0.5 * W and 0.2 * H < c["y"] < 0.75 * H and c is not out.get("window")]
    if lan:
        out["lantern"] = max(lan, key=lambda c: c["peak"])
    return {k: light_at(img, c["ys"], c["xs"], k) for k, c in out.items()}


def horizon_guess(img):
    L = K.luma(img)
    gy = np.abs(np.diff(K.blur(L, 1), axis=0))
    band = gy[:, int(0.2 * W):int(0.8 * W)].mean(1)
    lo, hi = int(0.28 * H), int(0.62 * H)
    return int(lo + np.argmax(band[lo:hi]))


def choose_crop(lab, src_h, src_w):
    """crop_y so, dass Leuchtfeuer und Schornstein mindestens 10 % der Bildhöhe unter dem oberen Rand liegen."""
    ch = round(src_w * 9 / 16)
    if ch >= src_h:
        return 0.5
    tops = []
    for name in ("lamp", "chimney"):
        ys = np.nonzero((lab == A.IDX[name]).any(1))[0]
        if len(ys):
            tops.append(int(ys.min()))
    y0 = (src_h - ch) * 0.5
    if tops:
        y0 = min(y0, max(0.0, min(tops) - 0.10 * ch))
    return round(float(y0 / (src_h - ch)), 3)


def from_labels(img, lab, report):
    cfg = {}
    water = lab == A.IDX["water"]
    sky = lab == A.IDX["sky"]
    # Horizont: erste Wasserzeile in Spalten, in denen direkt darüber Himmel liegt
    cand, firsts, lasts = [], [], []
    for x in range(0, W, 4):
        col = np.nonzero(water[:, x])[0]
        if not len(col):
            continue
        y = int(col.min())
        firsts.append(y)
        lasts.append(int(col.max()))
        if y >= 3 and sky[max(0, y - 4):y, x].any():
            cand.append(y)
    cfg["horizon_y"] = int(np.median(cand)) if cand else (int(np.median(firsts)) if firsts else horizon_guess(img))
    cfg["quay_y"] = int(np.percentile(lasts, 75)) if lasts else int(0.83 * H)
    report["horizon_from"] = "Himmel/Wasser-Grenze" if cand else ("oberste Wasserzeile" if firsts else "Gemälde")

    lights = []
    guessed = detect_lights(img)
    for name in ("window", "lantern", "lamp"):
        comps = A.components(lab == A.IDX[name], min_px=6)
        if name == "window":
            comps = comps[:2]
        else:
            comps = comps[:1]
        if comps:
            for i, (ys, xs) in enumerate(comps):
                li = light_at(img, ys, xs, name)
                if i:
                    li["name"] = f"{name}{i + 1}"
                    li.pop("pool_r", None)
                    li["glow"] = 30
                lights.append(li)
            report.setdefault("lights_from_mask", []).append(name)
        elif name in guessed:
            lights.append(guessed[name])
            report.setdefault("lights_guessed", []).append(name)
        else:
            report.setdefault("lights_missing", []).append(name)
    cfg["lights"] = lights[:4]
    lamp = next((li["pos"] for li in lights if li["channel"] == "lamp"), None)
    if lamp:
        cfg["lamp"] = lamp
        cfg["beam_len"] = int(np.clip(0.75 * max(lamp[0], W - lamp[0]), 400, 800))

    ch = A.components(lab == A.IDX["chimney"], min_px=6)
    if ch:
        ys, xs = ch[0]
        top = int(ys.min())
        cfg["chimney"] = [round(float(xs[ys <= top + 4].mean()), 1), float(top - 2)]
        report["chimney_from"] = "Maske"
    else:
        report["chimney_from"] = "fehlt (Rauch nach Hand setzen: scene.override.json -> chimney)"

    boats = []
    for i, (ys, xs) in enumerate(A.boat_components(lab)):
        yb = float(np.percentile(ys, 97))
        xb = float(np.median(xs[ys >= yb - 6]))
        boats.append({"pivot": [round(xb, 1), round(yb, 1)], "amp_deg": [1.0, 0.8][i], "period": [4.2, 5.0][i],
                      "phase": [0.0, 1.7][i], "bob": 1.0, "core_r": 3})
    cfg["boats"] = boats
    report["boats"] = len(boats)

    # Dachs: auf dem freien Kai links vom Textfeld, Füße deutlich unter der Wasserkante
    notother = lab != A.IDX["other"]
    best = None
    for x in range(int(0.30 * W), int(0.50 * W) + 1, 8):
        cols = notother[:, max(0, x - 60):x + 60]
        rows = np.nonzero(cols.any(1))[0]
        edge = int(rows.max()) if len(rows) else int(0.75 * H)
        feet = max(int(0.915 * H), edge + 40)
        if feet <= H - 24:
            d = abs(x - 0.42 * W)
            if best is None or d < best[0]:
                best = (d, x, feet)
    if best is None:
        best = (0, int(0.42 * W), int(0.915 * H))
        report["badger_spot"] = "kein freier Kai gefunden, Standardlage"
    cfg["badger"] = {"x": best[1], "feet_y": best[2], "height": BADGER_H}
    hz = cfg["horizon_y"]
    cfg["gulls"] = [{"start": [round(0.22 * W), round(0.30 * hz)], "vel": [26, -2], "size": 10},
                    {"start": [round(0.74 * W), round(0.52 * hz)], "vel": [-18, 1], "size": 7}]
    cfg["ui"] = dict(UI)
    return cfg


def overlay(img, lab, cfg, path):
    ov = img * 0.6 + A.PALETTE[lab] * 0.4 if lab is not None else img
    im = Image.fromarray((np.clip(ov, 0, 1) * 255).astype(np.uint8))
    d = ImageDraw.Draw(im)
    for x in range(0, W, 50):
        d.line([(x, 0), (x, H)], fill=(255, 255, 255) if x % 100 == 0 else (110, 110, 110), width=1)
        if x % 100 == 0:
            d.text((x + 2, 2), str(x), fill=(255, 255, 0))
    for y in range(0, H, 50):
        d.line([(0, y), (W, y)], fill=(255, 255, 255) if y % 100 == 0 else (110, 110, 110), width=1)
        if y % 100 == 0:
            d.text((2, y + 2), str(y), fill=(255, 255, 0))
    for key, c in (("horizon_y", (0, 255, 255)), ("quay_y", (255, 128, 0))):
        if key in cfg:
            d.line([(0, cfg[key]), (W, cfg[key])], fill=c, width=2)
    for li in cfg.get("lights", []):
        x, y = li["pos"]
        r = li.get("r", 10)
        d.ellipse([x - r, y - r, x + r, y + r], outline=(255, 60, 60), width=2)
        d.text((x + r + 2, y - 6), li["name"], fill=(255, 200, 200))
    if "chimney" in cfg:
        x, y = cfg["chimney"]
        d.polygon([(x, y - 10), (x - 7, y + 4), (x + 7, y + 4)], outline=(0, 255, 0))
        d.text((x + 9, y - 8), "chimney", fill=(160, 255, 160))
    for i, b in enumerate(cfg.get("boats", [])):
        x, y = b["pivot"]
        d.ellipse([x - 5, y - 5, x + 5, y + 5], fill=(255, 0, 255))
        d.text((x + 7, y - 6), f"pivot{i + 1}", fill=(255, 160, 255))
    bd = cfg.get("badger")
    if bd:
        x, y, h = bd["x"], bd["feet_y"], bd.get("height", BADGER_H)
        d.rectangle([x - h * 0.34, y - h, x + h * 0.34, y], outline=(255, 255, 255), width=2)
        d.text((x - 20, y + 3), "badger", fill=(255, 255, 255))
    u = cfg.get("ui")
    if u:
        d.rectangle([u["x"], u["y"], u["x"] + u["w"], u["y"] + u["h"]], outline=(255, 210, 120), width=2)
    for g in cfg.get("gulls", []):
        x, y = g["start"]
        d.line([(x - 8, y), (x, y + 4), (x + 8, y)], fill=(40, 40, 40), width=2)
    im.save(path)


def build(bg, mask=None, labels_out=None, base=None, debug=None, crop_y=None):
    """crop_y: fester 16:9-Ausschnitt (0 = oben, 1 = unten); None = automatisch (choose_crop)."""
    base = pathlib.Path(base).resolve() if base else HERE.parent
    src = Image.open(bg).convert("RGB")
    sw, sh = src.size
    img_src = np.asarray(src, np.float32) / 255.0
    report = {"bg_size": [sw, sh]}
    cfg = {"base": "..", "src": relp(bg, base)}
    if mask:
        m = Image.open(mask).convert("RGB")
        report["mask_size"] = list(m.size)
        lab_m = A.classify(np.asarray(m, np.float32) / 255.0)
        share = {n: round(float((lab_m == i).mean()), 4) for n, i in A.IDX.items()}
        report["mask_shares"] = share
        lab0 = A.resize_lab(lab_m, (sw, sh))
        T = A.align(img_src, lab0)
        report["align"] = T
        lab = A.warp_lab(lab0, (T["sx"], T["sy"], T["dx"], T["dy"]), (sw, sh))
        cfg["crop_y"] = choose_crop(lab, sh, sw) if crop_y is None else float(crop_y)
        report["crop_from"] = "automatisch" if crop_y is None else "scene.override.json"
        still_im, box = load_still(bg, cfg["crop_y"])
        img = np.asarray(still_im, np.float32) / 255.0
        lab_s = A.resize_lab(lab[box[1]:box[3], box[0]:box[2]], (W, H))
        if labels_out:
            pathlib.Path(labels_out).parent.mkdir(parents=True, exist_ok=True)
            Image.fromarray(A.to_rgb(lab_s)).save(labels_out)
            cfg["ai_labels"] = relp(labels_out, base)
        cfg.update(from_labels(img, lab_s, report))
        cfg["star_max_sat"] = 0.25
        complete = True
    else:
        cfg["crop_y"] = 0.5 if crop_y is None else float(crop_y)
        still_im, box = load_still(bg, cfg["crop_y"])
        img = np.asarray(still_im, np.float32) / 255.0
        lab_s = None
        hz = horizon_guess(img)
        lights = detect_lights(img)
        cfg.update({
            "_todo": "Entwurf ohne KI-Maske: sky/water/boats/chimney nach dem Raster in scene_overlay.png von Hand "
                     "setzen (Polygone in 1280x720), dann als tools/scene.hand.json speichern.",
            "horizon_y": hz, "quay_y": int(0.83 * H),
            "sky": [[[0, 0], [W, 0], [W, hz], [0, hz]]],
            "water": [[[0, hz], [W, hz], [W, int(0.83 * H)], [0, int(0.83 * H)]]],
            "lights": list(lights.values()),
            "chimney": [round(0.1 * W), round(0.15 * H)],
            "boats": [],
            "badger": {"x": round(0.42 * W), "feet_y": round(0.915 * H), "height": BADGER_H},
            "ui": dict(UI),
        })
        if "lamp" in lights:
            cfg["lamp"] = lights["lamp"]["pos"]
        report["lights_guessed"] = list(lights)
        complete = False
    report["crop_box"] = list(box)
    cfg["_auto"] = report
    if debug:
        pathlib.Path(debug).mkdir(parents=True, exist_ok=True)
        overlay(img, lab_s, cfg, pathlib.Path(debug) / "scene_overlay.png")
    return cfg, complete


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--bg", required=True)
    ap.add_argument("--mask")
    ap.add_argument("--config-out", required=True)
    ap.add_argument("--labels-out")
    ap.add_argument("--base")
    ap.add_argument("--debug")
    a = ap.parse_args()
    cfg, complete = build(a.bg, a.mask, a.labels_out, a.base, a.debug)
    out = pathlib.Path(a.config_out).resolve()
    out.parent.mkdir(parents=True, exist_ok=True)
    cfg["base"] = os.path.relpath(pathlib.Path(a.base).resolve() if a.base else HERE.parent, out.parent)
    out.write_text(json.dumps(cfg, ensure_ascii=False, indent=1))
    print(json.dumps(cfg["_auto"], ensure_ascii=False))
    return 0 if complete else 3


if __name__ == "__main__":
    sys.exit(main())
