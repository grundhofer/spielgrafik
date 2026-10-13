#!/usr/bin/env python3
"""Vergleichsschalter für die Knet-Oberfläche: dasselbe Bild mit und ohne --no-detail (keine Abdrücke, Poren,
Krümel, Marmorierung, kein Formrauschen). Misst den Anteil der Pixel, die sich um mehr als 8 Stufen ändern,
im ganzen Bild und im Bereich des Dachses.

    .venv/bin/python styles/knete/scripts/compare_detail.py TMP_DIR [--t0 4.3]

Schreibt styles/knete/assets/measure/detail_switch.json und detail_switch.jpg (Ausschnitt Dachs, links mit,
rechts ohne Oberfläche).
"""
import argparse, json, pathlib, shutil, subprocess

import numpy as np
from PIL import Image

ROOT = pathlib.Path(__file__).resolve().parents[1]
BADGER_BOX = (300, 420, 470, 690)


def render(out, extra, t0):
    out.mkdir(parents=True, exist_ok=True)
    cmd = ["godot", "--path", str(ROOT / "demo"), "--position", "20000,20000", "--resolution", "1280x720",
           "--write-movie", str(out / "f.png"), "--fixed-fps", "30", "--quit-after", "1", "--", f"--t0={t0}",
           "--no-ui"] + extra
    subprocess.run(cmd, capture_output=True, text=True, timeout=900)
    return Image.open(sorted(out.glob("f*.png"))[0]).convert("RGB")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("tmp")
    ap.add_argument("--t0", type=float, default=4.3)
    a = ap.parse_args()
    tmp = pathlib.Path(a.tmp)
    on = render(tmp / "on", [], a.t0)
    off = render(tmp / "off", ["--no-detail"], a.t0)
    A, B = np.asarray(on, dtype=np.int16), np.asarray(off, dtype=np.int16)
    d = np.abs(A - B).max(axis=2) > 8
    x0, y0, x1, y1 = BADGER_BOX
    res = {"t0": a.t0, "changed_share_frame": round(float(d.mean()), 4),
           "changed_share_badger_box": round(float(d[y0:y1, x0:x1].mean()), 4), "badger_box": BADGER_BOX}
    out = ROOT / "assets" / "measure"
    out.mkdir(parents=True, exist_ok=True)
    w, h = x1 - x0, y1 - y0
    sheet = Image.new("RGB", (2 * w * 2, h * 2))
    sheet.paste(on.crop(BADGER_BOX).resize((w * 2, h * 2), Image.NEAREST), (0, 0))
    sheet.paste(off.crop(BADGER_BOX).resize((w * 2, h * 2), Image.NEAREST), (w * 2, 0))
    sheet.save(out / "detail_switch.jpg", quality=85)
    (out / "detail_switch.json").write_text(json.dumps(res, indent=1))
    print(json.dumps(res, indent=1))
    shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    main()
