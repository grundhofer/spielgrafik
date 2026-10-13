#!/usr/bin/env python3
"""Zwei feste Einstellungen der Szene im Rahmenfenster (Totale und Nahaufnahme).

    .venv/bin/python styles/jugendstil/scripts/layout.py

Welt = Pixel von bg.png (Plakatbild mit PAD Zeilen Himmel oben). Bildschirm = 1280x720.
  Totale:      Szene füllt die Fensterbreite (Faktor = Fensterbreite / 1536), Weltzeile 0 am Bogenscheitel.
  Nahaufnahme: Faktor ZOOM_CLOSE; Welt-x CLOSE_CX in der Fenstermitte, die Sohlenlinie FOOT_Y liegt
               FOOT_MARGIN Bildschirmpixel über der Fensterunterkante.
Ausgang (assets/ und demo/art/): layout.json mit je Einstellung zoom und pos (Bildschirmlage von Welt 0,0).
"""
import json, pathlib

ROOT = pathlib.Path(__file__).resolve().parents[1]
FOOT_Y = 855.0          # Sohlenlinie des Dachses in Weltpixeln (Mitte des Kais; 815 im KI-Bild + PAD)
ZOOM_CLOSE = 1.0        # Nahaufnahme: Plakatbild 1:1
CLOSE_CX = 560.0        # Welt-x in der Fenstermitte der Nahaufnahme (Dachs im Stand links, Laterne rechts)
FOOT_MARGIN = 24.0


def main():
    fr = json.loads((ROOT / "assets/frame.json").read_text())
    sc = json.loads((ROOT / "assets/scene.json").read_text())
    w = fr["window"]
    ww, wh = w["x1"] - w["x0"] + 1, w["y1"] - w["y0"] + 1
    z0 = ww / sc["size"][0]
    far = {"zoom": z0, "pos": [float(w["x0"]), float(w["y0"])]}
    z1 = ZOOM_CLOSE
    px = w["x0"] + ww / 2 - CLOSE_CX * z1
    py = w["y1"] + 1 - FOOT_MARGIN - FOOT_Y * z1
    close = {"zoom": z1, "pos": [round(px, 2), round(py, 2)]}
    vis_far = [(w["y0"] - far["pos"][1]) / z0, (w["y1"] + 1 - far["pos"][1]) / z0]
    vis_close = [(w["y0"] - py) / z1, (w["y1"] + 1 - py) / z1]
    out = {"window": w, "foot_y": FOOT_Y, "shots": [far, close],
           "visible_rows": {"far": [round(v, 1) for v in vis_far], "close": [round(v, 1) for v in vis_close]},
           "visible_cols_close": [round((w["x0"] - px) / z1, 1), round((w["x1"] + 1 - px) / z1, 1)]}
    for d in (ROOT / "assets", ROOT / "demo/art"):
        d.mkdir(parents=True, exist_ok=True)
        (d / "layout.json").write_text(json.dumps(out, indent=1))
    print(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
