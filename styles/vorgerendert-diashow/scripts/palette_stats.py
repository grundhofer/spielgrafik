"""Kennzahlen der 256-Farben-Reduktion je Knoten (Standbild gegen Rohbild).

    .venv/bin/python styles/vorgerendert-diashow/scripts/palette_stats.py

Farben im Rohbild (8 Bit) und im gebackenen Standbild, mittlere Abweichung je Kanal (8-Bit-Stufen) und im reinen
Himmel (feste Rechtecke ohne Gegenstände) der mittlere Helligkeitsunterschied waagerecht benachbarter Pixel: Er zeigt,
wie stark die Fehlerdiffusion den glatten Verlauf körnt.
"""
import pathlib

import numpy as np
from PIL import Image

STYLE = pathlib.Path(__file__).resolve().parent.parent
SKY = {"kai": (300, 0, 540, 60), "steg": (0, 0, 260, 60), "tuer": (0, 0, 200, 60)}


def main():
    for name, (x0, y0, x1, y1) in SKY.items():
        raw = np.asarray(Image.open(STYLE / "assets" / "raw" / "render" / name / "loop_0000.png").convert("RGB"))
        base = np.asarray(Image.open(STYLE / "assets" / "nodes" / name / "base.png").convert("RGB"))
        n_raw = len(np.unique(raw.reshape(-1, 3), axis=0))
        n_base = len(np.unique(base.reshape(-1, 3), axis=0))
        dev = np.abs(raw.astype(int) - base.astype(int)).mean()
        y = lambda a: a[y0:y1, x0:x1].astype(float) @ [0.299, 0.587, 0.114]
        nb = lambda a: np.abs(np.diff(y(a), axis=1)).mean()
        print(f"{name}: Farben roh {n_raw}, gebacken {n_base}, mittlere Abweichung {dev:.2f} Stufen, "
              f"Nachbarunterschied im Himmel roh {nb(raw):.2f}, gebacken {nb(base):.2f}")


if __name__ == "__main__":
    main()
