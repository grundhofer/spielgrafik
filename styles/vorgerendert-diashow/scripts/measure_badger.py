"""Misst Kopf und Füße des Dachs-Clips in den Einzelbildern aus Blender.

    blender -b --factory-startup -P styles/vorgerendert-diashow/blender/render_nodes.py -- --node steg --what mask
    .venv/bin/python styles/vorgerendert-diashow/scripts/measure_badger.py

Quelle: assets/raw/render/steg/mask_NNNN.png (gleiche Kamera, Zeiten und Posen wie der Clip, aber alles außer dem
Dachs als Holdout, also ohne Schatten, Spiegelung und Dithering; Verdeckung durch Steg und Pfahl bleibt). Dass Godot
genau diese Clip-Bilder zeigt, prüft scripts/check_demo.py.

Gemessen je Bild (Bildpunkte im 544×332-Knotenbild):
  Kopf    oberste Zeile mit mindestens 2 Deckungspixeln
  Füße    unterstes Viertel der Figur, an der Mitte geteilt; je Seite unterste Zeile und mittleres x der beiden
          untersten Zeilen
Prüfungen:
  Laufen  (Clip-Bilder 0 bis Stillstand): jeder Fuß hat Standphasen, in denen er über mindestens 2 Bildwechsel
          (3 Bilder) höchstens 1 px wandert; die Füße stehen nie gleichzeitig still und rutschen nicht.
  Drehen  (Stillstand bis Winkbeginn): Drehung auf der Stelle, Wanderung der Füße wird nur berichtet.
  Stehen  (ab Winkbeginn): Fußzeilen in allen Wink- und Stehbildern gleich (±1 px).
Schreibt assets/badger_measure.json.
"""
import json
import pathlib

import numpy as np
from PIL import Image

STYLE = pathlib.Path(__file__).resolve().parent.parent
RAW = STYLE / "assets" / "raw" / "render" / "steg"
DATA = json.loads((STYLE / "demo" / "data" / "nodes.json").read_text())
CLIP = DATA["badger_clip"]
FPS = DATA["fps"]


def measure(j):
    a = np.asarray(Image.open(RAW / f"mask_{j:04d}.png").convert("RGBA"))[..., 3] > 127
    ys, xs = np.nonzero(a)
    rows = a.sum(1)
    head = int(np.nonzero(rows >= 2)[0].min())
    bottom = int(ys.max())
    low = a.copy()
    low[: bottom - (bottom - head) // 4] = False
    lx = np.nonzero(low)[1]
    mid = (lx.min() + lx.max()) / 2.0
    feet = {}
    for side, sel in (("links", np.arange(a.shape[1]) < mid), ("rechts", np.arange(a.shape[1]) >= mid)):
        m = low & sel[None, :]
        fy, fx = np.nonzero(m)
        yb = int(fy.max())
        xb = float(fx[fy >= yb - 1].mean())
        feet[side] = (round(xb, 1), yb)
    return {"bild": j, "kopf": head, "fuss_links": feet["links"], "fuss_rechts": feet["rechts"],
            "breite": [int(xs.min()), int(xs.max())], "hoehe": bottom - head + 1}


def stance_runs(track, tol=1.0):
    """Läufe aufeinanderfolgender Bilder, in denen der Fuß höchstens tol px von der Lage im ersten Bild abweicht."""
    runs, start = [], 0
    for i in range(1, len(track) + 1):
        if i < len(track):
            dx = abs(track[i][0] - track[start][0])
            dy = abs(track[i][1] - track[start][1])
            if dx <= tol and dy <= tol:
                continue
        if i - start >= 3:
            runs.append([start, i - 1])
        start = i
    return runs


def main():
    n = CLIP["frames"]
    m = [measure(j) for j in range(n)]
    stop = int(np.ceil((CLIP["walk_s"] + CLIP["decel_s"]) * FPS))    # erstes Bild nach dem Anhalten
    walk = m[: stop + 1]
    report = {"quelle": "assets/raw/render/steg/mask_*.png", "bilder": n, "stillstand_ab_bild": stop}
    for side in ("links", "rechts"):
        tr = [w["fuss_" + side] for w in walk]
        report["standphasen_" + side] = stance_runs(tr)
    # nie beide Füße gleichzeitig in Bewegung über mehr als 1 Bildwechsel? (Kontrolle gegen Gleiten)
    moving_both = []
    for i in range(1, len(walk)):
        dl = np.hypot(walk[i]["fuss_links"][0] - walk[i - 1]["fuss_links"][0],
                      walk[i]["fuss_links"][1] - walk[i - 1]["fuss_links"][1])
        dr = np.hypot(walk[i]["fuss_rechts"][0] - walk[i - 1]["fuss_rechts"][0],
                      walk[i]["fuss_rechts"][1] - walk[i - 1]["fuss_rechts"][1])
        if dl > 1.0 and dr > 1.0:
            moving_both.append([i - 1, i, round(float(dl), 1), round(float(dr), 1)])
    report["beide_fuesse_bewegt"] = moving_both
    turn_end = int(np.ceil((CLIP["walk_s"] + CLIP["decel_s"] + CLIP["blend_to_wave_s"]) * FPS))
    report["drehen_bilder"] = [stop, turn_end - 1]
    for side in ("links", "rechts"):
        tr = [w["fuss_" + side] for w in m[stop:turn_end + 1]]
        report["drehen_wanderung_" + side] = [round(float(max(t[0] for t in tr) - min(t[0] for t in tr)), 1),
                                              int(max(t[1] for t in tr) - min(t[1] for t in tr))]
    report["stehen_ab_bild"] = turn_end
    stand = m[turn_end:]
    for side in ("links", "rechts"):
        xs = [s["fuss_" + side][0] for s in stand]
        report["stehen_fussx_" + side] = [min(xs), max(xs)]
    for side in ("links", "rechts"):
        ys = [s["fuss_" + side][1] for s in stand]
        report["stehen_fusszeile_" + side] = [min(ys), max(ys)]
    report["stehen_kopf"] = [min(s["kopf"] for s in stand), max(s["kopf"] for s in stand)]
    report["hoehe_px"] = [min(s["hoehe"] for s in m), max(s["hoehe"] for s in m)]
    report["werte"] = m
    (STYLE / "assets" / "badger_measure.json").write_text(json.dumps(report, indent=1, ensure_ascii=False))
    print("Bild  Kopf  Fuß links     Fuß rechts")
    for w in walk:
        print(f"{w['bild']:4d}  {w['kopf']:4d}  {w['fuss_links']!s:12}  {w['fuss_rechts']!s:12}")
    for k in ("stillstand_ab_bild", "standphasen_links", "standphasen_rechts", "beide_fuesse_bewegt",
              "drehen_bilder", "drehen_wanderung_links", "drehen_wanderung_rechts", "stehen_ab_bild",
              "stehen_fusszeile_links", "stehen_fusszeile_rechts", "stehen_fussx_links", "stehen_fussx_rechts",
              "stehen_kopf", "hoehe_px"):
        print(k, report[k])


if __name__ == "__main__":
    main()
