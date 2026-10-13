#!/usr/bin/env python3
"""Kontaktspannen der Füße je Laufbild im KI-Bogen (Rahmen wie in build_badger.py), Grundlage für die
Vorschübe in scripts/choreo.py.

    .venv/bin/python styles/art-deco/scripts/measure_stride.py

Rahmen sind an der Sohle ausgerichtet (Zeile TOP = 450), x in Zellkoordinaten. Je Bild werden die deckenden
Spalten in den untersten k Zeilen (k = 0, 2, 4, 8, 12) als Spannen ausgegeben: k = 2-4 zeigt die Aufstandsfläche
(bei Doppelstand zwei Spannen), k = 8-12 die ganze Sohle des Standfußes, solange der andere Fuß hoch genug ist.
Die Vorschübe werden daraus von Hand am Drehpunkt abgelesen (Ferse beim Aufsetzen, Spitze beim Abrollen, Ferse
und Spitze im Einzelstand); eine automatische Deckungssuche über die untersten Zeilen lieferte bei diesem Bogen
keine brauchbaren Werte (beide Füße verschmelzen in den untersten Zeilen, die Suche lief an den Rand).
Ausgabe: assets/stride.json
"""
import json, pathlib
import numpy as np
from PIL import Image

ROOT = pathlib.Path(__file__).resolve().parents[1]


def frames():
    """Rahmen wie in build_badger.py, aber in voller KI-Auflösung (nur Alpha)."""
    import importlib.util
    spec = importlib.util.spec_from_file_location("bb", ROOT / "scripts/build_badger.py")
    bb = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(bb)
    im = np.asarray(Image.open(ROOT / "assets/raw/walk.png").convert("RGBA"))
    lay = json.loads((ROOT / "assets/ref/layout.json").read_text())
    out = {}
    for c in lay["cells"]:
        x, y, w, h = c["x"], c["y"], c["w"], c["h"]
        core = bb.largest_component(im[y:y + h, x:x + w, 3] >= 128)
        ys, xs = np.nonzero(core)
        sole = int(ys.max())
        canvas = np.zeros((bb.TOP + bb.BOT, w), bool)
        y0 = sole - bb.TOP
        sy0, sy1 = max(0, y0), min(h, sole + bb.BOT)
        canvas[sy0 - y0:sy1 - y0] = core[sy0:sy1]
        out[c["name"]] = canvas
    return out, bb.TOP


def spans(row):
    cols = np.nonzero(row)[0]
    if not len(cols):
        return []
    gaps = np.nonzero(np.diff(cols) > 2)[0]
    return [(int(q[0]), int(q[-1])) for q in np.split(cols, gaps + 1)]


def main():
    fr, top = frames()
    res = {}
    for n in [f"walk_{i}" for i in range(8)] + ["stand", "turn"]:
        res[n] = {str(k): spans(fr[n][top - k:top + 1].any(0)) for k in (0, 2, 4, 8, 12)}
        print(n, "  ".join(f"k={k}: {v}" for k, v in res[n].items()))
    (ROOT / "assets/stride.json").write_text(json.dumps(res, indent=1))


if __name__ == "__main__":
    main()
