#!/usr/bin/env python3
"""Weg B: KI-Rasterbild -> vtracer -> SVG -> (svg2godot.py) -> Polygon2D.

    <eigenes venv mit vtracer>/bin/python styles/flat-vektor/scripts/vectorize_ai.py in.png out.svg \
        [--fit 1280x720] [--anchor bottom] [--preset flat]

vtracer (MIT, pip install vtracer) zerlegt das Bild in Farbflächen und legt sie gestapelt übereinander
(hierarchical="stacked": keine Löcher, jede Fläche ein eigener Pfad). Mit --fit wird das Ergebnis in eine
Gruppe mit Skalierung und Versatz gelegt, damit es den Bildausschnitt der Demo füllt (Seitenverhältnis bleibt,
überstehende Ränder werden in Godot vom Bildrand abgeschnitten).
"""
import argparse, pathlib, re, sys

import vtracer
from PIL import Image

PRESETS = {
    # flache Illustration: wenige Farbstufen, glatte Kurven, Krümel unter 4 px weg
    "flat": dict(colormode="color", hierarchical="stacked", mode="spline", filter_speckle=4, color_precision=6,
                 layer_difference=16, corner_threshold=60, length_threshold=4.0, max_iterations=10,
                 splice_threshold=45, path_precision=2),
    # feiner: Verläufe bleiben als Stufen erhalten, dafür viel mehr Flächen
    "fine": dict(colormode="color", hierarchical="stacked", mode="spline", filter_speckle=4, color_precision=7,
                 layer_difference=5, corner_threshold=60, length_threshold=4.0, max_iterations=10,
                 splice_threshold=45, path_precision=2),
    # gröber: weniger Flächen (für den Vergleich der Formenzahl)
    "coarse": dict(colormode="color", hierarchical="stacked", mode="spline", filter_speckle=10, color_precision=5,
                   layer_difference=28, corner_threshold=60, length_threshold=6.0, max_iterations=10,
                   splice_threshold=45, path_precision=2),
}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("src")
    ap.add_argument("out")
    ap.add_argument("--fit", default=None, help="Zielgröße BxH; skaliert auf volle Breite")
    ap.add_argument("--anchor", default="bottom", choices=["bottom", "center", "top"])
    ap.add_argument("--preset", default="flat", choices=sorted(PRESETS))
    ap.add_argument("--scale", type=float, default=None, help="statt --fit: fester Faktor")
    ap.add_argument("--offset", default="0,0")
    a = ap.parse_args()
    src = pathlib.Path(a.src)
    w, h = Image.open(src).size
    tmp = pathlib.Path(a.out).with_suffix(".raw.svg")
    # vtracer 0.6.15 stürzt unter Python 3.14 bei Schlüsselwortargumenten ab (Speicherzugriffsfehler);
    # deshalb positionell in der Reihenfolge der Signatur übergeben.
    order = ["colormode", "hierarchical", "mode", "filter_speckle", "color_precision", "layer_difference",
             "corner_threshold", "length_threshold", "max_iterations", "splice_threshold", "path_precision"]
    vtracer.convert_image_to_svg_py(str(src), str(tmp), *[PRESETS[a.preset][k] for k in order])
    raw = tmp.read_text()
    body = raw[raw.index(">", raw.index("<svg")) + 1: raw.rindex("</svg>")]
    if a.fit:
        W, H = map(int, a.fit.split("x"))
        s = W / w
        oy = {"bottom": H - h * s, "center": (H - h * s) / 2, "top": 0}[a.anchor]
        ox = 0.0
    else:
        W, H = w, h
        s = a.scale or 1.0
        ox, oy = map(float, a.offset.split(","))
        W, H = round(w * s + ox), round(h * s + oy)
    out = (f'<svg xmlns="http://www.w3.org/2000/svg" id="ai_vector" width="{W}" height="{H}" viewBox="0 0 {W} {H}">\n'
           f'<g id="traced" transform="translate({ox:.3f},{oy:.3f}) scale({s:.6f})">{body}</g>\n</svg>\n')
    pathlib.Path(a.out).write_text(out)
    tmp.unlink()
    n = len(re.findall(r"<path", body))
    print(f"{a.out}: {n} Pfade aus {src.name} ({w}x{h}), Faktor {s:.4f}")


if __name__ == "__main__":
    sys.exit(main())
