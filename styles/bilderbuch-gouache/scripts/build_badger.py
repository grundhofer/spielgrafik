#!/usr/bin/env python3
"""Zerlegt den KI-Laufbogen (assets/raw/walk.png, 2x5 Figuren) in Spielbilder für den Eintrag bilderbuch-gouache.

    .venv/bin/python styles/bilderbuch-gouache/scripts/build_badger.py

Schritte:
  1. Figuren über Zusammenhangskomponenten den Layout-Zellen zuordnen (assets/ref/layouts.json).
  2. Magenta-Saum vom agy-Freistellen entfernen (Despill am Rand, einzelne Flecken innen), winzige Löcher zwischen
     den Beinen schließen, Farbe in den transparenten Rand ausbreiten (kein dunkler Saum beim Filtern).
  3. Jede Figur mit der Sohle auf eine gemeinsame Grundlinie setzen; waagerecht bleibt die Lage in der Zelle
     (das Bildmodell hat die Figuren wie das Layout auf der Stelle laufen lassen, Kopf ±3 px).
  4. Vormultipliziert auf Spielgröße verkleinern (FIG_H px Figurenhöhe) und als Bögen speichern:
     assets/badger_walk.png (8 Laufbilder), assets/badger_idle.png (Stehen, Dreiviertel, Dreiviertel mit
     geschlossenem Auge), assets/badger.json (Zellgröße, Fußpunkt, Vorschub je Laufbild, Versatz Stehen/Drehen).
  Der Vorschub je Laufbild ist gleichmäßig (WALK_DX Bogenpixel): gemessen wurden 12–15 px innerhalb der
  Standphasen; an den Fußwechseln ist die Sohle verschmolzen, dort wurde mit gleichem Vorschub geprüft, dass
  der hintere Fuß stehen bleibt (siehe scripts/measure_badger.py).
"""
import json, pathlib, sys

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(HERE))
from gutil import label, premul_resize, bleed_rgb  # noqa: E402

FIG_H = 200          # Figurenhöhe im Spiel (Mütze bis Sohle) in px
WALK_DX = 14.0       # Vorschub je Laufbild in Bogenpixeln (Rohbild 1264x848)
PAD = 6


def despill(arr):
    """Magenta-Rest entfernen: am Rand (bis 4 px zur Transparenz) immer, innen nur deutliche Flecken."""
    a = arr[..., 3]
    rgb = arr[..., :3].astype(np.float32)
    m = np.minimum(rgb[..., 0], rgb[..., 2]) - rgb[..., 1]
    tr = Image.fromarray(((a < 128) * 255).astype(np.uint8)).filter(ImageFilter.MaxFilter(9))
    near = np.asarray(tr) > 0
    sel = (a > 0) & (((m > 0) & near) | (m > 35))
    k = np.where(sel, np.maximum(m, 0), 0)
    rgb[..., 0] -= k
    rgb[..., 2] -= k
    out = arr.copy()
    out[..., :3] = rgb.clip(0, 255).astype(np.uint8)
    return out


def fill_small_holes(arr, max_area=120):
    """Kleine eingeschlossene Löcher (Schlüsselfarbe zwischen den Beinen) mit der Umgebungsfarbe füllen."""
    a = arr[..., 3]
    hole = a < 128
    lab, n = label(hole)
    sizes = np.bincount(lab.ravel())
    h, w = a.shape
    border = set(np.unique(np.concatenate([lab[0], lab[-1], lab[:, 0], lab[:, -1]])).tolist())
    out = arr.copy()
    filled = 0
    for i in range(1, n + 1):
        if i in border or sizes[i] > max_area:
            continue
        ys, xs = np.nonzero(lab == i)
        y0, y1, x0, x1 = max(0, ys.min() - 4), min(h, ys.max() + 5), max(0, xs.min() - 4), min(w, xs.max() + 5)
        ring = (a[y0:y1, x0:x1] > 200) & (lab[y0:y1, x0:x1] != i)
        col = np.median(arr[y0:y1, x0:x1, :3][ring], axis=0)
        out[ys, xs, :3] = col
        out[ys, xs, 3] = 255
        filled += 1
    return out, filled


def close_eye(im, cx, cy, r):
    """Blinzeln: Auge mit der Farbe des dunklen Augenstreifens übermalen und ein kurzes Lid als Bogen setzen."""
    arr = np.asarray(im).copy()
    h, w = arr.shape[:2]
    yy, xx = np.mgrid[0:h, 0:w]
    d = np.hypot(xx - cx, yy - cy)
    ring = (d > r + 1) & (d < r + 4) & (arr[..., 3] > 200)
    lum = arr[..., :3].astype(int).sum(2)
    dark = ring & (lum < np.percentile(lum[ring], 50))
    col = np.median(arr[..., :3][dark], axis=0)
    inner = d <= r + 0.8
    arr[inner, :3] = col
    out = Image.fromarray(arr, "RGBA")
    dr = ImageDraw.Draw(out)
    lid = tuple(int(c * 0.45) for c in col) + (255,)
    dr.arc([cx - r, cy - r * 0.9, cx + r, cy + r * 0.7], start=20, end=160, fill=lid, width=max(2, int(r * 0.45)))
    return out


def main():
    lay = json.loads((ROOT / "assets/ref/layouts.json").read_text())["walk"]
    src = Image.open(ROOT / "assets/raw/walk.png").convert("RGBA")
    W, H = src.size
    sx, sy = W / 1536, H / 1024
    arr = np.asarray(src).copy()
    arr = despill(arr)
    lab, n = label(arr[..., 3] > 8)
    sizes = np.bincount(lab.ravel())
    cells = lay["cells"]
    names = [c["name"] for c in cells]
    frames = {}
    for i in range(1, n + 1):
        if sizes[i] < 30:
            continue
        ys, xs = np.nonzero(lab == i)
        cx, cy = xs.mean() / sx, ys.mean() / sy
        k = min(range(len(cells)), key=lambda j: abs(cells[j]["x"] + cells[j]["w"] / 2 - cx) / cells[j]["w"]
                + abs(cells[j]["y"] + cells[j]["h"] / 2 - cy) / cells[j]["h"])
        frames.setdefault(names[k], []).append(i)
    assert len(frames) == 10, frames
    figs, info = {}, {}
    holes_total = 0
    for name in names:
        c = next(c for c in cells if c["name"] == name)
        x0, y0 = int(round(c["x"] * sx)), int(round(c["y"] * sy))
        cw, ch = int(round(c["w"] * sx)), int(round(c["h"] * sy))
        m = np.isin(lab, frames[name])
        part = arr.copy()
        part[~m] = 0
        crop = part[y0:y0 + ch, x0:x0 + cw]
        crop, nh = fill_small_holes(crop)
        holes_total += nh
        ys, xs = np.nonzero(crop[..., 3] > 128)
        info[name] = {"top": int(ys.min()), "bot": int(ys.max()), "x0": int(xs.min()), "x1": int(xs.max())}
        figs[name] = Image.fromarray(crop, "RGBA")
    heights = [info[n]["bot"] - info[n]["top"] for n in names[:8]]
    scale = FIG_H / float(np.median(heights))
    # gemeinsame Zelle: Sohle auf Grundlinie, waagerecht Zelllage
    cw = int(round(lay["cells"][0]["w"] * sx))
    top_max = max(info[n]["bot"] - info[n]["top"] for n in names)
    CH_src = top_max + 2 * PAD
    base_src = top_max + PAD                      # Grundlinie in der Quellzelle
    out_w = int(np.ceil(cw * scale)) + 2 * PAD
    out_h = int(np.ceil(CH_src * scale))
    shift_extra = {}
    # Stehen nach Laufbild 6: Standfuß-Überdeckung messen (Sohlenband 8 Zeilen)
    def band(name, rows=8):
        a = np.asarray(figs[name])[..., 3] > 128
        b = info[name]["bot"]
        return a[b - rows + 1:b + 1]
    def best_shift(a_name, b_name, rng):
        A, B = band(a_name), band(b_name)
        best = None
        for s in rng:
            Bs = np.roll(B, s, 1)
            iou = (A & Bs).sum() / max(1, (A | Bs).sum())
            if best is None or iou > best[0]:
                best = (iou, s)
        return best
    st = best_shift("walk_6", "stand", range(-12, 13))
    shift_extra["stand_after_walk_6"] = {"iou": round(float(st[0]), 3), "shift_src": st[1]}
    # Drehen: beide Füße stehen, die Sohlen ändern aber ihre Form (Seitenansicht -> Dreiviertel); deshalb die Mitte
    # des Sohlenbands gleich halten statt der Überdeckung (die fand nur 0,52 am Rand des Suchbereichs).
    def sole_mid(name):
        b = band(name, 6).any(0)
        xs = np.nonzero(b)[0]
        return (xs.min() + xs.max()) / 2.0
    shift_extra["turn_after_stand"] = {"sole_mid_stand": sole_mid("stand"), "sole_mid_turn": sole_mid("turn"),
                                       "shift_src": round(sole_mid("stand") - sole_mid("turn"), 2)}

    def place(name):
        im = figs[name]
        canvas = Image.new("RGBA", (cw, CH_src), (0, 0, 0, 0))
        dy = base_src - info[name]["bot"]
        canvas.alpha_composite(im, (0, dy))
        return canvas

    def bake(name, extra=None):
        cv = place(name)
        if extra is not None:
            cv = extra(cv, base_src - info[name]["bot"])
        cv = bleed_rgb(cv, 6)
        sm = premul_resize(cv, (int(round(cw * scale)), out_h))
        full = Image.new("RGBA", (out_w, out_h), (0, 0, 0, 0))
        full.alpha_composite(sm, (PAD, 0))
        return bleed_rgb(full, 4)

    walk = [bake(f"walk_{i}") for i in range(8)]
    # Auge im Dreiviertelbild: im Rohbogen bei (1160.6, 543.4), r ≈ 5,5 (von Hand gemessen)
    tc = next(c for c in cells if c["name"] == "turn")
    ex = 1160.6 - int(round(tc["x"] * sx))
    ey_raw = 543.4 - int(round(tc["y"] * sy))
    idle = [bake("stand"), bake("turn"),
            bake("turn", lambda cv, dy: close_eye(cv, ex, ey_raw + dy, 5.5))]
    sheet = Image.new("RGBA", (out_w * 8, out_h), (0, 0, 0, 0))
    for i, f in enumerate(walk):
        sheet.paste(f, (i * out_w, 0))
    sheet.save(ROOT / "assets/badger_walk.png")
    sheet2 = Image.new("RGBA", (out_w * 3, out_h), (0, 0, 0, 0))
    for i, f in enumerate(idle):
        sheet2.paste(f, (i * out_w, 0))
    sheet2.save(ROOT / "assets/badger_idle.png")
    meta = {
        "cell_w": out_w, "cell_h": out_h, "scale": round(scale, 5), "fig_h": FIG_H,
        "foot_y": round(base_src * scale, 2),              # Grundlinie in der Zelle
        "walk_dx": round(WALK_DX * scale, 4),              # Vorschub je Laufbild in Spielpixeln
        "walk_frames": 8, "idle_frames": ["stand", "turn", "turn_blink"],
        "stand_dx": round(shift_extra["stand_after_walk_6"]["shift_src"] * scale, 3),
        "turn_dx": round(shift_extra["turn_after_stand"]["shift_src"] * scale, 3),
        "measure": shift_extra, "holes_filled": holes_total,
        "src_info": info,
    }
    (ROOT / "assets/badger.json").write_text(json.dumps(meta, indent=1))
    print("ok", out_w, out_h, "scale", round(scale, 4), "walk_dx", meta["walk_dx"], "stand_dx", meta["stand_dx"],
          "turn_dx", meta["turn_dx"], shift_extra, "holes", holes_total)


if __name__ == "__main__":
    main()
