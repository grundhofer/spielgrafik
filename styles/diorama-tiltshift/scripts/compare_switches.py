#!/usr/bin/env python3
"""Vergleichsschalter und Renderer messen (PIPELINE.md → Blender/Selbstprüfung).

    .venv/bin/python styles/diorama-tiltshift/scripts/compare_switches.py TMP_DIR

Rendert die Totale (0,5 s) und die Nahaufnahme (5,0 s) ohne Oberfläche
  a) voll, ohne Tiefenunschärfe (--no-dof), ohne Filzfasern (--no-shells),
  b) mit den Renderern mobile und gl_compatibility,
und gibt den Anteil der Pixel aus, die sich um mehr als 8 Stufen (größter Kanal) vom vollen Bild unterscheiden.
Bögen: assets/preview/switches.png (Zeilen Totale/Nahaufnahme; Spalten voll, ohne Unschärfe, ohne Fasern) und
assets/preview/renderers.png (Spalten Forward+, Mobile, Compatibility).
"""
import json, pathlib, shutil, subprocess, sys, tempfile

import numpy as np
from PIL import Image, ImageDraw

ROOT = pathlib.Path(__file__).resolve().parent.parent
DEMO = ROOT / "demo"
TIMES = [0.5, 5.0]


def render(t, out, extra=(), method=None):
    with tempfile.TemporaryDirectory() as td:
        cmd = ["godot", "--path", str(DEMO), "--position", "20000,20000", "--resolution", "1280x720"]
        if method:
            cmd += ["--rendering-method", method]
        cmd += ["--write-movie", f"{td}/f.png", "--fixed-fps", "30", "--quit-after", "2", "--", f"--t0={t}", "--no-ui", *extra]
        r = subprocess.run(cmd, capture_output=True, text=True)
        log = [l for l in (r.stdout + r.stderr).splitlines() if "ERROR" in l or "WARNING" in l]
        frames = sorted(pathlib.Path(td).glob("f*.png"))
        shutil.copy(frames[-1], out)
    return log


def share(a, b):
    x = np.asarray(Image.open(a).convert("RGB"), dtype=np.int16)
    y = np.asarray(Image.open(b).convert("RGB"), dtype=np.int16)
    return round(float((np.abs(x - y).max(axis=2) > 8).mean()) * 100, 1)


def sheet(rows, labels, path):
    w, h = 426, 240
    im = Image.new("RGB", (w * len(rows[0]), h * len(rows)), "black")
    d = ImageDraw.Draw(im)
    for r, row in enumerate(rows):
        for c, f in enumerate(row):
            im.paste(Image.open(f).convert("RGB").resize((w, h), Image.LANCZOS), (c * w, r * h))
            d.rectangle([c * w, r * h, c * w + 150, r * h + 16], fill="black")
            d.text((c * w + 4, r * h + 3), labels[c], fill="white")
    path.parent.mkdir(parents=True, exist_ok=True)
    im.save(path)


def main():
    tmp = pathlib.Path(sys.argv[1])
    tmp.mkdir(parents=True, exist_ok=True)
    subprocess.run(["godot", "--headless", "--path", str(DEMO), "--import"], capture_output=True)
    res, sw_rows, rd_rows, logs = {}, [], [], {}
    for t in TIMES:
        full = tmp / f"full_{t}.png"
        logs[f"full {t}"] = render(t, full)
        row = [full]
        for sw in ("--no-dof", "--no-shells"):
            f = tmp / f"{sw.strip('-')}_{t}.png"
            render(t, f, [sw])
            res[f"{sw} t={t}"] = share(full, f)
            row.append(f)
        sw_rows.append(row)
        rrow = [full]
        for m in ("mobile", "gl_compatibility"):
            f = tmp / f"{m}_{t}.png"
            logs[f"{m} {t}"] = render(t, f, method=m)
            res[f"{m} t={t}"] = share(full, f)
            rrow.append(f)
        rd_rows.append(rrow)
        again = tmp / f"again_{t}.png"
        render(t, again)
        res[f"zweiter Lauf gleich t={t}"] = share(full, again) == 0.0
    sheet(sw_rows, ["voll", "ohne Tiefenunschaerfe", "ohne Filzfasern"], ROOT / "assets/preview/switches.png")
    sheet(rd_rows, ["Forward+", "Mobile", "Compatibility"], ROOT / "assets/preview/renderers.png")
    print(json.dumps({"Anteil geänderter Pixel in %": res,
                      "Meldungen": {k: v[:6] for k, v in logs.items() if v}}, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
