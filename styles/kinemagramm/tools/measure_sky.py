#!/usr/bin/env python3
"""Misst die Schärfe des Himmels (Hochfrequenzanteil) in der gerenderten Demo gegen das Gemälde.

    .venv/bin/python styles/kinemagramm/tools/measure_sky.py WORKDIR [--times 0 3 6 20 40 60 80]

Rendert je Zeitpunkt ein Bild (--t0, ohne Figur und Textfeld) und berechnet im Himmel (Maske, Bereich ohne
Strahl, Rauch und Bildrand) den mittleren Betrag von Bild minus 1-px-Weichzeichnung (feinste Struktur). Ausgabe: Wert je Zeitpunkt,
Wert des Gemäldes und Verhältnis; außerdem die Verschiebung des Himmels gegen das Gemälde (beste ganzzahlige
Verschiebung), damit Pendeln und Lage geprüft werden können. Ergebnis auch in WORKDIR/sky_measure.json.
"""
import argparse, json, pathlib, subprocess, sys

import numpy as np
from PIL import Image

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import imgops as K  # noqa: E402


def hf(L, m, r=1):
    """Mittlerer Betrag von Bild minus Weichzeichnung (r=1: feinste Pinselstruktur), in Stufen 0..255."""
    return float(np.abs(L - K.blur(L, r))[m].mean()) * 255


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("work")
    ap.add_argument("--times", type=float, nargs="+", default=[0, 3, 6, 20, 40, 60, 80])
    ap.add_argument("--demo", default=str(HERE.parent / "demo"))
    ap.add_argument("--image", nargs="*", default=[], help="zusätzlich fertige Bilder messen (z. B. ein altes Poster)")
    a = ap.parse_args()
    work = pathlib.Path(a.work)
    art = pathlib.Path(a.demo) / "art"
    still = K.luma(K.load_rgb(art / "still.png"))
    ma = K.load_rgb(art / "mask_a.png")
    H, W = still.shape
    yy, xx = np.mgrid[0:H, 0:W]
    m = (ma[..., 1] > 0.98) & (yy > 8) & (yy < 140) & (xx > 450) & (xx < W - 40)
    m &= K.box(ma[..., 1], 6) > 0.98                      # nicht an Objektkanten
    ref = hf(still, m)
    res = {"still_hf": round(ref, 3), "px": int(m.sum()), "frames": []}
    for t in a.times:
        d = work / f"sky_{t:g}"
        subprocess.run([sys.executable, str(HERE / "render.py"), str(d), "--frames", "1", "--demo", a.demo,
                        "--", f"--t0={t}", "--no-ui", "--no-badger"], check=True, capture_output=True)
        f = sorted(d.glob("f*.png"))[-1]
        L = K.luma(np.asarray(Image.open(f).convert("RGB"), np.float32) / 255)
        v = hf(L, m)
        # Verschiebung: beste ganzzahlige Verschiebung des Gemäldes in x (-40..40)
        best = min(range(-40, 41), key=lambda s: float(np.abs(np.roll(still, -s, 1)[m] - L[m]).mean()))
        res["frames"].append({"t": t, "hf": round(v, 3), "ratio": round(v / ref, 3), "shift_px": best})
    for f in a.image:
        L = K.luma(np.asarray(Image.open(f).convert("RGB"), np.float32) / 255)
        res.setdefault("images", []).append({"file": str(f), "hf": round(hf(L, m), 3), "ratio": round(hf(L, m) / ref, 3)})
    print(json.dumps(res, indent=1))
    (work / "sky_measure.json").write_text(json.dumps(res, indent=1))


if __name__ == "__main__":
    main()
