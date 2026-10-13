#!/usr/bin/env python3
"""Misst die Bildpaare (gleicher Prompt, gleiche Referenzen: Codex/gpt-image gegen agy/Gemini).

    .venv/bin/python styles/bildmodelle-vergleich/scripts/measure_pairs.py

Schreibt assets/measurements.json (kleine Messdaten) und druckt eine Übersicht. Gemessen wird nur, was sich
zuverlässig zählen lässt; Stiltreue, Komposition und Treue zum Referenzblatt beurteilt style.json zusätzlich
durch Ansehen.

- Größe, Dauer, ob agy den Prompt wörtlich weitergab (aus den .json neben den Bildern)
- Pseudo-Pixelraster: Gipfel der Autokorrelation der Kantenenergie (siehe grid_period); Kunstpixel = Bildbreite /
  Periode, nur wenn der Gipfel deutlich ist
- Farben: Anzahl der 5-Bit-Farben, die 95 % der Fläche decken
- Transparenz: Anteil voll durchsichtig, voll deckend, halbdurchsichtig, „Dunst“ (Alpha 1–7) und Magenta-Saum
- Figurenblätter: Bilder je Reihe, Figurhöhen, Maßstab Reihe 2 zu Reihe 1, Fußlinie, Kopfauf und -ab
- Texturblätter: Kachelnähte (Sprung an der Wiederholkante im Verhältnis zum Sprung zwischen Nachbarspalten)
- Wiederholbarkeit: zwei Läufe desselben Prompts, mittleres ΔE (Lab) auf 48×32 und Korrelation der Kantenkarten
"""
import json, pathlib
import numpy as np
from PIL import Image, ImageFilter

HERE = pathlib.Path(__file__).resolve().parent
ENTRY = HERE.parent
ROOT = ENTRY.parent.parent
RAW = ENTRY / "assets" / "raw"

PAIRS = [
    {"id": "vga_bg", "title": "VGA-Hintergrund", "kind": "background_pixel",
     "codex": "styles/vga-adventure/assets/raw/bg.png", "agy": "styles/bildmodelle-vergleich/assets/raw/vga_bg_agy.png"},
    {"id": "oel_bg", "title": "Ölmalerei-Hintergrund", "kind": "background_paint",
     "codex": "styles/oelmalerei/assets/raw/bg3.png", "agy": "styles/bildmodelle-vergleich/assets/raw/oel_bg_agy.png"},
    {"id": "vga_badger", "title": "VGA-Figurenblatt (Referenzblatt)", "kind": "sprite_sheet",
     "codex": "styles/vga-adventure/assets/raw/badger_small.png",
     "agy": "styles/bildmodelle-vergleich/assets/raw/vga_badger_agy.png"},
    {"id": "oel_portrait", "title": "Öl-Porträt (Referenzblatt)", "kind": "portrait",
     "codex": "styles/oelmalerei/assets/raw/portrait.png",
     "agy": "styles/bildmodelle-vergleich/assets/raw/oel_portrait_agy.png"},
    {"id": "master_sheet", "title": "Figurenblatt ohne Referenz", "kind": "character_sheet",
     "codex": "shared/badger/master_sheet.png", "agy": "styles/bildmodelle-vergleich/assets/raw/master_sheet_agy.png"},
    {"id": "vga_items", "title": "Inventar-Symbole", "kind": "icons",
     "codex": "styles/vga-adventure/assets/raw/items.png", "agy": "styles/bildmodelle-vergleich/assets/raw/vga_items_agy.png"},
    {"id": "ps1_textures", "title": "Texturblatt 4×4", "kind": "textures",
     "codex": "styles/bildmodelle-vergleich/assets/raw/ps1_textures_codex.png",
     "agy": "styles/ps1-lowpoly/assets/raw/textures.png"},
]
REPEATS = [
    {"id": "vga_bg_codex", "model": "codex", "a": "styles/vga-adventure/assets/raw/bg.png",
     "b": "styles/bildmodelle-vergleich/assets/raw/vga_bg_codex_b.png"},
    {"id": "vga_bg_agy", "model": "agy", "a": "styles/bildmodelle-vergleich/assets/raw/vga_bg_agy.png",
     "b": "styles/bildmodelle-vergleich/assets/raw/vga_bg_agy_b.png"},
]


def meta(path):
    j = json.loads(pathlib.Path(path).with_suffix(".json").read_text())
    backend = j.get("backend") or ("agy" if "Antigravity" in str(j.get("tool", "")) else "codex")
    out = {"backend": backend, "seconds": j.get("seconds"), "requested": j.get("size"),
           "refs": len(j.get("refs") or [])}
    for k in ("verbatim", "source_format", "key_transparent_share", "first_status"):
        if k in j:
            out[k] = j[k]
    return out


def load(path):
    return Image.open(ROOT / path)


def grid_period(im, maxlag=16):
    """Pseudo-Pixelraster: Autokorrelation der Kantenenergie |dx| je Zeile (bzw. |dy| je Spalte), über alle
    Zeilen gemittelt. Ein festes Raster mit Periode P gibt einen Gipfel bei P (und Vielfachen); weiche oder
    ungleichmäßige Pseudo-Pixel geben eine glatt abfallende Kurve ohne Gipfel. peak = Höhe des Gipfels über dem
    Mittel seiner beiden Nachbarn (0 = kein Raster)."""
    g = np.asarray(im.convert("L"), dtype=np.float64)
    res = {}
    for name, arr in (("x", g), ("y", g.T)):
        d = np.abs(np.diff(arr, axis=1))
        d = d - d.mean(axis=1, keepdims=True)
        den = (d * d).mean()
        ac = np.array([(d[:, :-k] * d[:, k:]).mean() / den for k in range(1, maxlag + 2)])
        best, lag = 0.0, None
        for k in range(2, maxlag):          # ac[k-1] gehört zu Abstand k
            lift = ac[k - 1] - (ac[k - 2] + ac[k]) / 2
            if lift > best + 1e-9 and ac[k - 1] > ac[k - 2] and ac[k - 1] > ac[k]:
                best, lag = lift, k
        if lag is not None:                  # Unterpixel-Lage des Gipfels (Parabel)
            y0, y1, y2 = ac[lag - 2], ac[lag - 1], ac[lag]
            lag = lag + 0.5 * (y0 - y2) / (y0 - 2 * y1 + y2)
        res[name] = (lag, best)
    lx, px = res["x"]
    ly, py = res["y"]
    return {"period_x": round(lx, 2) if lx else None, "peak_x": round(px, 3),
            "period_y": round(ly, 2) if ly else None, "peak_y": round(py, 3),
            "art_px": f"{round(im.width / lx)}x{round(im.height / ly)}" if lx and ly and px > 0.03 and py > 0.03 else None}


def colours95(im):
    a = np.asarray(im.convert("RGBA"))
    rgb = a[..., :3][a[..., 3] >= 128] >> 3
    keys = (rgb[:, 0].astype(np.int32) << 10) | (rgb[:, 1].astype(np.int32) << 5) | rgb[:, 2]
    _, cnt = np.unique(keys, return_counts=True)
    cnt = np.sort(cnt)[::-1]
    return int(np.searchsorted(np.cumsum(cnt), 0.95 * cnt.sum()) + 1)


def alpha_stats(im):
    if im.mode != "RGBA":
        return {"alpha": False}
    a = np.asarray(im)
    al = a[..., 3]
    op = al >= 128
    edge = op & ~np.asarray(Image.fromarray(op.astype(np.uint8) * 255).filter(ImageFilter.MinFilter(3))).astype(bool)
    rgb = a[..., :3].astype(np.int32)
    magenta = ((rgb[..., 0] + rgb[..., 2]) // 2 - rgb[..., 1] > 70) & (rgb[..., 0] > 150) & (rgb[..., 2] > 150)
    # dunkler Lilasaum: Mischfarbe aus dunkler Kontur und Magenta-Schlüsselfarbe (R und B über G). Gezählt je Ring
    # vom Rand nach innen (Ring 0 = äußerstes deckendes Pixel); JPEG-Farbunterabtastung trägt das Magenta bei agy
    # 2–3 px in die Kontur hinein, das Freistellen entfärbt nur den äußersten Ring.
    purple = (rgb[..., 0] > rgb[..., 1] + 12) & (rgb[..., 2] > rgb[..., 1] + 12) & (rgb[..., 0] - rgb[..., 2] < 60)
    mimg = Image.fromarray(op.astype(np.uint8) * 255)
    shells = [op] + [np.asarray(mimg.filter(ImageFilter.MinFilter(k))) > 0 for k in (3, 5, 7)]
    rings = [round(float((shells[i] & ~shells[i + 1] & purple).sum()) / max(1, int((shells[i] & ~shells[i + 1]).sum())), 3)
             for i in range(3)]
    return {"alpha": True,
            "share_clear": round(float((al == 0).mean()), 3),
            "share_full": round(float((al == 255).mean()), 3),
            "share_semi": round(float(((al > 0) & (al < 255)).mean()), 3),
            "share_haze_1_7": round(float(((al > 0) & (al < 8)).mean()), 3),
            "opaque_alpha_median": int(np.median(al[op])) if op.any() else None,
            "edge_px": int(edge.sum()),
            "edge_magenta_px": int((edge & magenta).sum()),
            "purple_share_ring_0_1_2": rings}


def runs(mask, min_gap):
    idx = np.flatnonzero(mask)
    out, s, p = [], idx[0], idx[0]
    for i in idx[1:]:
        if i - p > min_gap:
            out.append((int(s), int(p + 1)))
            s = i
        p = i
    out.append((int(s), int(p + 1)))
    return out


def sheet_layout(im):
    a = np.asarray(im.convert("RGBA"))
    op = a[..., 3] >= 128
    rows = [r for r in runs(op.any(1), 10) if r[1] - r[0] > 40]
    out = []
    for y0, y1 in rows:
        cols = [c for c in runs(op[y0:y1].any(0), 4) if c[1] - c[0] > 30]
        tops, bots = [], []
        for x0, x1 in cols:
            ys = np.flatnonzero(op[y0:y1, x0:x1].any(1))
            tops.append(int(y0 + ys[0]))
            bots.append(int(y0 + ys[-1]))
        hs = [b - t + 1 for t, b in zip(tops, bots)]
        out.append({"frames": len(cols), "heights": hs, "top_spread": max(tops) - min(tops),
                    "foot_spread": max(bots) - min(bots), "height_share": round(float(np.mean(hs)) / im.height, 3)})
    res = {"rows": out}
    g = grid_period(im.convert("RGB"))
    if g["period_y"]:
        for r in out:
            r["art_px_tall"] = round(float(np.mean(r["heights"])) / g["period_y"])
    if len(out) >= 2:
        res["row2_to_row1_scale"] = round(float(np.mean(out[1]["heights"]) / np.mean(out[0]["heights"])), 3)
    return res


def seams(im):
    """Je Kachel des 4×4-Blatts: mittlerer Sprung an der Wiederholkante (links/rechts, oben/unten) geteilt durch
    den mittleren Sprung zwischen Nachbarspalten im Inneren. Um 1 = nahtlos, deutlich darüber = sichtbare Naht."""
    g = np.asarray(im.convert("RGB"), dtype=np.float64)
    lum = g.mean(axis=2)
    dark = lum < 18
    # Rinnen: Spalten und Zeilen, die fast ganz schwarz sind
    colmask = dark.mean(axis=0) > 0.6
    rowmask = dark.mean(axis=1) > 0.6
    xs = [r for r in runs(~colmask, 2) if r[1] - r[0] > 50]
    ys = [r for r in runs(~rowmask, 2) if r[1] - r[0] > 50]
    ratios = []
    for y0, y1 in ys:
        for x0, x1 in xs:
            t = g[y0 + 3:y1 - 3, x0 + 3:x1 - 3]
            inner = np.abs(np.diff(t, axis=1)).mean()
            inner_y = np.abs(np.diff(t, axis=0)).mean()
            wrap_x = np.abs(t[:, 0] - t[:, -1]).mean()
            wrap_y = np.abs(t[0] - t[-1]).mean()
            ratios.append(round(float((wrap_x / inner + wrap_y / inner_y) / 2), 2))
    return {"tiles": len(ratios), "seam_ratio": ratios, "seam_ratio_median": float(np.median(ratios)) if ratios else None,
            "tiles_over_2": int(sum(r > 2 for r in ratios))}


def lab(im, size=(48, 32)):
    x = np.asarray(im.convert("RGB").resize(size, Image.BOX), dtype=np.float64) / 255
    x = np.where(x > 0.04045, ((x + 0.055) / 1.055) ** 2.4, x / 12.92)
    m = np.array([[0.4124, 0.3576, 0.1805], [0.2126, 0.7152, 0.0722], [0.0193, 0.1192, 0.9505]])
    xyz = x @ m.T / np.array([0.9505, 1.0, 1.089])
    f = np.where(xyz > 0.008856, np.cbrt(xyz), 7.787 * xyz + 16 / 116)
    return np.stack([116 * f[..., 1] - 16, 500 * (f[..., 0] - f[..., 1]), 200 * (f[..., 1] - f[..., 2])], -1)


def edges(im, size=(192, 128)):
    g = np.asarray(im.convert("L").resize(size, Image.BOX), dtype=np.float64)
    e = np.hypot(np.diff(g, axis=1)[:-1], np.diff(g, axis=0)[:, :-1])
    return (e - e.mean()) / (e.std() + 1e-9)


def similarity(pa, pb):
    a, b = load(pa), load(pb)
    de = float(np.linalg.norm(lab(a) - lab(b), axis=-1).mean())
    ec = float((edges(a) * edges(b)).mean())
    return {"delta_e_48x32": round(de, 1), "edge_corr_192x128": round(ec, 3)}


def describe(path, kind):
    im = load(path)
    d = {"file": path, "size": f"{im.width}x{im.height}", **meta(ROOT / path)}
    if kind in ("background_pixel", "sprite_sheet", "icons"):
        d["grid"] = grid_period(im.convert("RGB"))
    d["colours95"] = colours95(im)
    d["transparency"] = alpha_stats(im.convert("RGBA") if im.mode in ("RGBA", "LA", "P") else im)
    if kind == "sprite_sheet":
        d["layout"] = sheet_layout(im)
    if kind == "textures":
        d["seams"] = seams(im)
    return d


def main():
    out = {"pairs": [], "repeats": [], "cross_model": []}
    for p in PAIRS:
        row = {"id": p["id"], "title": p["title"], "kind": p["kind"]}
        for side in ("codex", "agy"):
            row[side] = describe(p[side], p["kind"])
        out["pairs"].append(row)
    for r in REPEATS:
        if (ROOT / r["b"]).exists():
            out["repeats"].append({"id": r["id"], "model": r["model"], "a": r["a"], "b": r["b"], **similarity(r["a"], r["b"])})
    out["cross_model"].append({"id": "vga_bg codex↔agy", **similarity(PAIRS[0]["codex"], PAIRS[0]["agy"])})
    (ENTRY / "assets" / "measurements.json").write_text(json.dumps(out, ensure_ascii=False, indent=1))
    for row in out["pairs"]:
        print(f"== {row['title']}")
        for side in ("codex", "agy"):
            d = row[side]
            print(f"  {side:5} {d['size']:>9} {d['seconds']!s:>6}s  farben95={d['colours95']:<5}"
                  f" grid={d.get('grid')} alpha={d['transparency']}")
            if "layout" in d:
                print("        layout", d["layout"])
            if "seams" in d:
                print("        seams", {k: v for k, v in d["seams"].items() if k != 'seam_ratio'})
    for r in out["repeats"] + out["cross_model"]:
        print("repeat", r)


if __name__ == "__main__":
    main()
