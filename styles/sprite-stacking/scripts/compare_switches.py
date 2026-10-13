#!/usr/bin/env python3
"""Vergleichsschalter und Renderer: Anteil geänderter Pixel in der Szene (oberhalb der Textleiste).

    .venv/bin/python styles/sprite-stacking/scripts/compare_switches.py <Temp-Ordner> [--frames 60,126]

Rendert die Demo mit main.gd-Schaltern (--flat, --no-shadows, --ysort) und mit den Renderern mobile und
gl_compatibility, vergleicht mit der Standardfassung (Forward+) und schreibt Kontaktbögen nach assets/preview/.
Zwei Standardläufe werden bitweise verglichen (Determinismus).
"""
import argparse, json, pathlib, sys

import numpy as np
from PIL import Image, ImageDraw

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from render_frames import render  # noqa: E402

PREV = pathlib.Path(__file__).resolve().parent.parent / "assets" / "preview"
SCENE_H = 181


def load(pngs, i):
    return np.asarray(Image.open(pngs[i]).convert("RGB"))


def diff(a, b, thr=8):
    d = np.abs(a[:SCENE_H].astype(int) - b[:SCENE_H].astype(int)).max(-1)
    return float((d > thr).mean())


def sheet(images, labels, path, scale=2):
    h, w = images[0].shape[:2]
    cols = 2
    rows = (len(images) + 1) // 2
    out = Image.new("RGB", (cols * w * scale + 6, rows * (h * scale + 14) - 2), "white")
    dr = ImageDraw.Draw(out)
    for k, (im, lab) in enumerate(zip(images, labels)):
        x, y = (k % cols) * (w * scale + 6), (k // cols) * (h * scale + 14)
        out.paste(Image.fromarray(im).resize((w * scale, h * scale), Image.NEAREST), (x, y + 12))
        dr.text((x + 2, y), lab, fill="black")
    out.save(path)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("tmp")
    ap.add_argument("--frames", default="60,126")
    a = ap.parse_args()
    tmp = pathlib.Path(a.tmp)
    picks = [int(v) for v in a.frames.split(",")]
    n = max(picks) + 1
    PREV.mkdir(parents=True, exist_ok=True)
    runs = {"standard": [], "standard2": [], "--flat": ["--flat"], "--no-shadows": ["--no-shadows"], "--ysort": ["--ysort"]}
    res = {}
    out = {}
    for name, user in runs.items():
        pngs, errs, _ = render(tmp / name.strip("-"), n, user=user)
        out[name] = pngs
        if errs:
            res[name + "_errors"] = errs[:3]
    for m in ("mobile", "gl_compatibility"):
        pngs, errs, log = render(tmp / m, n, method=m)
        out[m] = pngs
        res[m + "_errors"] = errs[:3]
        res[m + "_warnings"] = [l for l in log.splitlines() if "WARNING" in l][:3]
    for i in picks:
        base = load(out["standard"], i)
        row = {k: round(diff(base, load(v, i)), 4) for k, v in out.items() if k != "standard"}
        row["standard2_bitgleich"] = bool((base == load(out["standard2"], i)).all())
        res[f"bild_{i}"] = row
        sheet([base, load(out["--flat"], i), load(out["--no-shadows"], i), load(out["--ysort"], i)],
              ["Standard", f"--flat ({row['--flat']:.1%})", f"--no-shadows ({row['--no-shadows']:.1%})",
               f"--ysort ({row['--ysort']:.1%})"], PREV / f"switches_f{i:03d}.png")
        sheet([base, load(out["mobile"], i), load(out["gl_compatibility"], i)],
              ["Forward+", f"Mobile ({row['mobile']:.1%})", f"Compatibility ({row['gl_compatibility']:.1%})"],
              PREV / f"renderers_f{i:03d}.png")
    print(json.dumps(res, indent=1, ensure_ascii=False))
    (tmp / "compare.json").write_text(json.dumps(res, indent=1, ensure_ascii=False))


if __name__ == "__main__":
    main()
