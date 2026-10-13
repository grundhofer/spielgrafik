#!/usr/bin/env python3
"""Leitet aus dem freigestellten, gemalten Dachs die Konfiguration für prep_badger.py ab.

    .venv/bin/python styles/kinemagramm/tools/auto_badger.py --src assets/raw/badger.png --config-out CFG.json
        [--base ENTRY] [--debug DIR] [--crop x0,y0,x1,y1]

Findet automatisch:
  tail      das frei hängende/wehende Schalende: rote Schalpixel unterhalb des Halswickels oder seitlich
            außerhalb der Körperkontur (Polygon um diesen Bereich; prep_badger.py wählt darin den Rotton)
  anchor_y  Unterkante des Halswickels (darüber bewegt sich der Schal nicht)
  eyes      zwei Glanzlichter auf gleicher Höhe im Kopfbereich, umgeben von dunklem Fell (Blinzeln);
            nicht gefunden -> keine Lider, Meldung
Im Debug-Ordner: badger_overlay.png mit Raster (Quellpixel) zum Prüfen und für Korrekturen in
tools/badger.override.json.
"""
import argparse, json, os, pathlib, sys

import numpy as np
from PIL import Image, ImageDraw

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import aimask as A  # noqa: E402
import imgops as K  # noqa: E402

HEIGHT = 230


def load_rgba(src, crop=None):
    im = Image.open(src)
    if crop:
        im = im.crop(tuple(crop))
    arr = np.asarray(im.convert("RGBA"), np.float32) / 255.0
    if im.mode != "RGBA" or arr[..., 3].min() > 0.99:
        # kein Alpha: Magenta-Hintergrund selbst freistellen (wie sprites.py key, Toleranz 70, weich 50)
        d = np.linalg.norm(arr[..., :3] * 255 - np.array([255, 0, 255]), axis=-1)
        arr[..., 3] = np.clip((d - 70) / 50, 0, 1)
    return arr


def red_mask(rgb, alpha):
    r, g, b = rgb[..., 0], rgb[..., 1], rgb[..., 2]
    return (r > 0.22) & (r > 2.0 * g) & (r > 1.5 * b) & (alpha > 0.5)


def find_scarf(rgb, alpha, bbox):
    x0, y0, x1, y1 = bbox
    fig_h = y1 - y0
    red = red_mask(rgb, alpha)
    comps = A.components(red, min_px=20)
    if not comps:
        return None, None, {"scarf": "kein Rot gefunden"}
    main = len(comps[0][0])
    scarf = np.zeros(red.shape, bool)
    for ys, xs in comps:
        if len(ys) >= 0.02 * main:
            scarf[ys, xs] = True
    width = scarf.sum(1)
    upper = np.arange(len(width)) < y0 + 0.55 * fig_h
    wmax = width[upper].max()
    wide = np.nonzero(upper & (width >= 0.5 * wmax))[0]
    # zusammenhängender Block breiter Zeilen um die breiteste Zeile = Halswickel
    peak = int(np.argmax(np.where(upper, width, 0)))
    lo = hi = peak
    wset = set(wide.tolist())
    while lo - 1 in wset:
        lo -= 1
    while hi + 1 in wset:
        hi += 1
    wrap_bottom = hi
    body = (alpha > 0.5) & ~scarf
    tail = scarf.copy()
    tail[:wrap_bottom + 1] = False
    # seitlich außerhalb der Körperkontur (Schal weht neben dem Körper), ab Oberkante des Wickels
    for y in range(lo, wrap_bottom + 1):
        bx = np.nonzero(body[y])[0]
        if len(bx):
            row = scarf[y].copy()
            row[bx.min() - 2:bx.max() + 3] = False
            tail[y] |= row
    rep = {"wrap_rows": [int(lo), int(hi)], "scarf_px": int(scarf.sum()), "tail_px": int(tail.sum())}
    if tail.sum() < 0.03 * scarf.sum():
        rep["tail"] = "kein frei hängendes Schalende gefunden"
        return None, wrap_bottom, rep
    tc = A.components(tail, min_px=10)
    ys, xs = tc[0]
    for oys, oxs in tc[1:]:  # weitere größere Teile (z. B. Fransen) dazunehmen
        if len(oys) > 0.15 * len(ys):
            ys, xs = np.concatenate([ys, oys]), np.concatenate([xs, oxs])
    m = 8
    top = int(min(ys.min(), wrap_bottom - 0.03 * fig_h))
    poly = [[int(xs.min() - m), top], [int(xs.max() + m), top], [int(xs.max() + m), int(ys.max() + m)],
            [int(xs.min() - m), int(ys.max() + m)]]
    return poly, wrap_bottom, rep


def find_eyes(rgb, alpha, bbox):
    x0, y0, x1, y1 = bbox
    fig_h = y1 - y0
    L = K.luma(rgb)
    r1 = max(2, round(0.010 * fig_h))
    r2 = max(4, round(0.030 * fig_h))
    hp = L - K.blur(L, r1)
    sur = K.blur(L, r2)
    zone = np.zeros_like(L, bool)
    zone[int(y0 + 0.05 * fig_h):int(y0 + 0.32 * fig_h), x0:x1] = True
    score = np.where(zone & (alpha > 0.95) & (L > 0.40) & (sur < 0.45), hp, 0)
    cand = []
    s = score.copy()
    for _ in range(10):
        i = int(np.argmax(s))
        v = float(s.flat[i])
        if v < 0.08:
            break
        y, x = divmod(i, s.shape[1])
        cand.append((v, x, y))
        s[max(0, y - 2 * r2):y + 2 * r2, max(0, x - 2 * r2):x + 2 * r2] = 0
    best = None
    for i in range(len(cand)):
        for j in range(i + 1, len(cand)):
            vi, xi, yi = cand[i]
            vj, xj, yj = cand[j]
            dx, dy = abs(xi - xj), abs(yi - yj)
            if dy < 0.035 * fig_h and 0.06 * fig_h < dx < 0.32 * fig_h:
                sc = vi + vj
                if best is None or sc > best[0]:
                    best = (sc, sorted([(xi, yi), (xj, yj)]))
    rep = {"eye_candidates": [[int(x), int(y), round(v, 3)] for v, x, y in cand]}
    if not best:
        rep["eyes"] = "kein Augenpaar gefunden (Blinzeln aus; eyes in badger.override.json setzen)"
        return [], rep
    er = round(0.015 * fig_h, 1)
    # Glanzlicht sitzt meist oben im Auge: Mitte etwas tiefer ansetzen
    eyes = [[int(x), int(round(y + 0.3 * er)), er] for x, y in best[1]]
    return eyes, rep


def build(src, base=None, debug=None, crop=None):
    base = pathlib.Path(base).resolve() if base else HERE.parent
    arr = load_rgba(src, crop)
    rgb, alpha = arr[..., :3], arr[..., 3]
    ys, xs = np.nonzero(alpha > 0.5)
    bbox = (int(xs.min()), int(ys.min()), int(xs.max()), int(ys.max()))
    report = {"size": [arr.shape[1], arr.shape[0]], "bbox": list(bbox),
              "opaque_share": round(float((alpha > 0.5).mean()), 3)}
    tail, wrap_bottom, rep = find_scarf(rgb, alpha, bbox)
    report.update(rep)
    eyes, rep = find_eyes(rgb, alpha, bbox)
    report.update(rep)
    p = pathlib.Path(src).resolve()
    cfg = {"base": "..", "src": os.path.relpath(p, base) if base in p.parents else str(p), "height": HEIGHT}
    if crop:
        cfg["crop"] = list(crop)
    if tail:
        cfg["tail"] = tail
        cfg["anchor_y"] = int(wrap_bottom - 0.01 * (bbox[3] - bbox[1]))
    cfg["eyes"] = eyes
    cfg["_auto"] = report
    if debug:
        pathlib.Path(debug).mkdir(parents=True, exist_ok=True)
        bg = np.ones_like(rgb) * np.array([0.25, 0.3, 0.38])
        ov = rgb * alpha[..., None] + bg * (1 - alpha[..., None])
        im = Image.fromarray((np.clip(ov, 0, 1) * 255).astype(np.uint8))
        d = ImageDraw.Draw(im)
        for x in range(0, im.width, 25):
            if x % 100 == 0:
                d.line([(x, 0), (x, im.height)], fill=(255, 255, 255))
                d.text((x + 2, 2), str(x), fill=(255, 255, 0))
            else:
                d.line([(x, 0), (x, im.height)], fill=(90, 90, 90))
        for y in range(0, im.height, 25):
            if y % 100 == 0:
                d.line([(0, y), (im.width, y)], fill=(255, 255, 255))
                d.text((2, y + 2), str(y), fill=(255, 255, 0))
            else:
                d.line([(0, y), (im.width, y)], fill=(90, 90, 90))
        if tail:
            d.polygon([tuple(q) for q in tail], outline=(0, 255, 255))
            d.line([(bbox[0], cfg["anchor_y"]), (bbox[2], cfg["anchor_y"])], fill=(0, 255, 255), width=2)
        for x, y, r in eyes:
            d.ellipse([x - r, y - r, x + r, y + r], outline=(255, 0, 255), width=2)
        im.save(pathlib.Path(debug) / "badger_overlay.png")
    return cfg


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", required=True)
    ap.add_argument("--config-out", required=True)
    ap.add_argument("--base")
    ap.add_argument("--debug")
    ap.add_argument("--crop", help="x0,y0,x1,y1 im Quellbild (nur für Blätter mit mehreren Ansichten)")
    a = ap.parse_args()
    crop = [int(v) for v in a.crop.split(",")] if a.crop else None
    cfg = build(a.src, a.base, a.debug, crop)
    out = pathlib.Path(a.config_out).resolve()
    out.parent.mkdir(parents=True, exist_ok=True)
    cfg["base"] = os.path.relpath(pathlib.Path(a.base).resolve() if a.base else HERE.parent, out.parent)
    out.write_text(json.dumps(cfg, ensure_ascii=False, indent=1))
    print(json.dumps({k: cfg.get(k) for k in ("tail", "anchor_y", "eyes")}), json.dumps(cfg["_auto"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
