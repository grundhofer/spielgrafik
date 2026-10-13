"""Zählt je Bildfolge und Bild die Pixel, die sich vom Standbild unterscheiden (gebackene Dateien).

    .venv/bin/python styles/vorgerendert-diashow/scripts/check_clips.py

Prüft, dass keine Bildfolge zwischendurch zum Standbild zurückspringt: Außer Bild 0 (es ist das Standbild) soll
jedes Bild einer Umgebungsschleife vom Standbild abweichen. Gibt außerdem die kürzeste Periode jeder Schleife aus
(kleinster Versatz k, für den Bild i und Bild i+k überall gleich sind).
"""
import json
import pathlib

import numpy as np
from PIL import Image

STYLE = pathlib.Path(__file__).resolve().parent.parent
NODES = STYLE / "assets" / "nodes"


def frames_of(sheet, c):
    x, y, w, h = c["rect"]
    return [sheet[(i // c["cols"]) * h:(i // c["cols"] + 1) * h, (i % c["cols"]) * w:(i % c["cols"] + 1) * w]
            for i in range(c["frames"])]


def main():
    meta = json.loads((NODES / "nodes_meta.json").read_text())
    for name, m in meta["nodes"].items():
        base = np.asarray(Image.open(NODES / name / m["base"]))
        for c in m["clips"]:
            if c["kind"] != "ambient":
                continue
            x, y, w, h = c["rect"]
            fr = frames_of(np.asarray(Image.open(NODES / name / c["file"])), c)
            ref = base[y:y + h, x:x + w]
            n = [int((f != ref).sum()) for f in fr]
            same = [i for i, k in enumerate(n) if k == 0]
            period = next((k for k in range(1, len(fr)) if all((fr[i] == fr[(i + k) % len(fr)]).all()
                                                                 for i in range(len(fr)))), len(fr))
            print(f"{name}/{c['file']} {w}×{h}: geändert je Bild min {min(n[1:])}, max {max(n)}, "
                  f"gleich dem Standbild: {same}, Periode {period} Bilder")
            print("   ", n)


if __name__ == "__main__":
    main()
