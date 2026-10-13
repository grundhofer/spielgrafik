#!/usr/bin/env python3
"""Vergleich starr gegen weich: dieselbe Animation einmal mit weichen Gewichten, einmal mit getrennten starren
Teilen (--rigid: jedes Dreieck ganz am stärksten Knochen). Nur die Figur vor Magenta.

    .venv/bin/python styles/skelett-2d/scripts/compare_rigid.py

Schreibt assets/check/vergleich_starr_weich.png (je Zeile: weich | starr | Unterschied, 2-fach vergrößert)
und assets/check/vergleich_starr_weich.json (Anteil geänderter Figurpixel, Löcher in der starren Fassung).
"""
import json, pathlib, subprocess, tempfile

import numpy as np
from PIL import Image, ImageDraw

HERE = pathlib.Path(__file__).resolve().parents[1]
SHOW = [18, 102, 150]


def run(td, name, extra):
    out = pathlib.Path(td) / name
    out.mkdir(parents=True)
    subprocess.run(["godot", "--path", str(HERE / "demo"), "--position", "20000,20000", "--resolution", "1280x720",
                    "--write-movie", str(out / "f.png"), "--fixed-fps", "30", "--quit-after", "180", "--",
                    "--badger-only"] + extra, capture_output=True)
    return out


def fig(a):
    return (np.abs(a[..., 0] - 255) + a[..., 1] + np.abs(a[..., 2] - 255)) > 140


def main():
    with tempfile.TemporaryDirectory() as td:
        soft, rigid = run(td, "soft", []), run(td, "rigid", ["--rigid"])
        stats, rows = [], []
        for i in range(180):
            a = np.asarray(Image.open(soft / f"f{i:08d}.png").convert("RGB")).astype(int)
            b = np.asarray(Image.open(rigid / f"f{i:08d}.png").convert("RGB")).astype(int)
            fa, fb = fig(a), fig(b)
            d = np.abs(a - b).max(axis=2) > 40
            stats.append({"frame": i, "changed": int(d.sum()), "figure": int(fa.sum()),
                          "holes": int((fa & ~fb).sum()), "extra": int((fb & ~fa).sum())})
            if i in SHOW:
                ys, xs = np.nonzero(fa)
                box = (xs.min() - 8, ys.min() - 8, xs.max() + 8, ys.max() + 8)
                dv = np.zeros_like(a)
                dv[d] = (255, 230, 0)
                row = [Image.fromarray(x.astype(np.uint8)).crop(box) for x in (a, b, dv)]
                rows.append([r.resize((r.width * 2, r.height * 2), Image.NEAREST) for r in row])
    w = max(sum(r.width for r in row) for row in rows)
    h = sum(row[0].height for row in rows) + 28
    sheet = Image.new("RGB", (w, h), (20, 20, 26))
    dr = ImageDraw.Draw(sheet)
    x = 0
    for lab in ("weich (Mesh-Skinning)", "starr (Teile je Knochen)", "Unterschied"):
        dr.text((x + 8, 8), lab, fill=(240, 240, 240))
        x += rows[0][0].width
    y = 28
    for row in rows:
        x = 0
        for r in row:
            sheet.paste(r, (x, y))
            x += r.width
        y += row[0].height
    out = HERE / "assets" / "check"
    sheet.save(out / "vergleich_starr_weich.png")
    share = [s["changed"] / s["figure"] for s in stats]
    summary = {"frames": len(stats), "changed_share_mean": round(float(np.mean(share)), 4),
               "changed_share_max": round(float(np.max(share)), 4),
               "holes_px_mean": round(float(np.mean([s["holes"] for s in stats])), 1),
               "holes_px_max": int(max(s["holes"] for s in stats)), "figure_px_mean": round(float(np.mean([s["figure"] for s in stats])), 1),
               "shown_frames": SHOW}
    (out / "vergleich_starr_weich.json").write_text(json.dumps({"summary": summary, "per_frame": stats}, indent=1))
    print(json.dumps(summary, indent=1))


if __name__ == "__main__":
    main()
