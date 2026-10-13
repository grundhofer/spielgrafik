#!/usr/bin/env python3
"""Prüft die Haltezeiten der getippten Eingabe "> nimm paket" (je Zeichen 3 Bilder) und den Wechsel der Auswahl.

    .venv/bin/python styles/flat-vektor/scripts/check_ui_timing.py <tempordner>

Rendert 180 Bilder ohne Schreibmarke (--probe-no-caret), zählt die bernsteinfarbenen Pixel im Eingabefeld je Bild
und misst, wie viele Bilder jeder Zwischenstand steht. Ergebnis: assets/ui_timing.json.
"""
import json, pathlib, shutil, subprocess, sys
import numpy as np
from PIL import Image

STYLE = pathlib.Path(__file__).resolve().parents[1]
DEMO = STYLE / "demo"
FIELD = (998, 656, 1224, 686)   # Eingabefeld (x0, y0, x1, y1)
PILL = (305, 656, 503, 686)     # "Das Paket ansehen"


def main():
    tmp = pathlib.Path(sys.argv[1]) / "ui"
    tmp.mkdir(parents=True, exist_ok=True)
    subprocess.run(["godot", "--headless", "--path", str(DEMO), "--import"], capture_output=True)
    subprocess.run(["godot", "--path", str(DEMO), "--position", "20000,20000", "--resolution", "1280x720",
                    "--write-movie", str(tmp / "f.png"), "--fixed-fps", "30", "--quit-after", "180", "--",
                    "--probe-no-caret"], capture_output=True)
    counts, pill = [], []
    for p in sorted(tmp.glob("f*.png")):
        a = np.asarray(Image.open(p).convert("RGB"), dtype=np.int16)
        f = a[FIELD[1]:FIELD[3], FIELD[0]:FIELD[2]]
        counts.append(int(((f[:, :, 0] > 150) & (f[:, :, 1] > 120) & (f[:, :, 2] < 170)).sum()))
        q = a[PILL[1]:PILL[3], PILL[0]:PILL[2]]
        pill.append(float(q[:, :, 0].mean() - q[:, :, 2].mean()))
    holds, start = [], 0
    for i in range(1, len(counts) + 1):
        if i == len(counts) or counts[i] != counts[start]:
            holds.append({"from_frame": start, "frames": i - start, "amber_px": counts[start]})
            start = i
    typing = [h for h in holds if 0 < h["from_frame"] and h["from_frame"] < 120][:-1]
    sel = next((i for i, v in enumerate(pill) if v > 60), None)
    res = {"typing_holds": [h["frames"] for h in typing], "typing_first_frame": typing[0]["from_frame"] if typing else None,
           "selection_red_from_frame": sel, "holds": holds}
    (STYLE / "assets" / "ui_timing.json").write_text(json.dumps(res, indent=1))
    print(json.dumps({k: v for k, v in res.items() if k != "holds"}))
    shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    main()
