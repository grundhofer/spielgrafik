#!/usr/bin/env python3
"""Misst Effekte, die frames.jpg nicht zeigt, an der Aufnahme selbst (6 s, 30 fps, 1280×720).

    .venv/bin/python styles/realistisch-pbr/scripts/measure_effects.py [--json assets/effects.json]

Rendert die Demo zweimal in ein Temp-Verzeichnis: wie aufgenommen und mit --no-flicker. Misst
1. SDFGI-Anlauf: mittlere Helligkeit (0..255) des Bildteils unter y = 600, des Häuschens und des ganzen
   Bildes in Bild 0–13 und die größte Änderung von Bild zu Bild (sichtbares Aufhellen am Schleifenanfang).
2. Flackern der Laterne: Differenz mit minus ohne Flackern je Bild (gleiche Kamera) in der halbnahen
   Einstellung, Bilder 118–180, an Glas, Pfosten, Lichthof im Dunst, Pflaster und Pfützenspiegelung.
3. Ortseinblendung (Bild 49): Kontrast weißer Text zu Hintergrund (relative Leuchtdichte, Median im
   Textband) nach WCAG-Formel.
4. Rauch (Bilder 25–40): Abstand zwischen Oberkante des Schornsteinkopfs und dem untersten Pixel, das
   über dem Kopf deutlich dunkler ist als der Himmel daneben (Rauch).
Die Bildbereiche sind auf die Kamerafahrt in main.gd abgestimmt.
"""
import argparse
import json
import pathlib
import subprocess
import tempfile

import numpy as np
from PIL import Image

ENTRY = pathlib.Path(__file__).resolve().parent.parent
DEMO = ENTRY / "demo"
FLICKER = {"Glas": (1150, 238, 1200, 285), "Pfosten": (1212, 300, 1245, 440), "Lichthof im Dunst": (1050, 300, 1150, 420),
           "Pflaster rechts": (1245, 450, 1280, 700), "Pfützenspiegelung": (1130, 698, 1200, 720)}


def render(td, name, extra):
    out = pathlib.Path(td) / name
    out.mkdir()
    subprocess.run(["godot", "--path", str(DEMO), "--position", "20000,20000", "--resolution", "1280x720",
                    "--write-movie", str(out / "f.png"), "--fixed-fps", "30", "--quit-after", "180", "--"] + extra,
                   check=True, capture_output=True, text=True, timeout=900)
    return sorted(out.glob("f*.png"))


def gray(p):
    return np.asarray(Image.open(p).convert("L")).astype(float)


def lum(a):
    c = a / 255.0
    c = np.where(c <= 0.04045, c / 12.92, ((c + 0.055) / 1.055) ** 2.4)
    return c @ np.array([0.2126, 0.7152, 0.0722])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", default=str(ENTRY / "assets" / "effects.json"))
    a = ap.parse_args()
    subprocess.run(["godot", "--headless", "--path", str(DEMO), "--import"], capture_output=True)
    res = {}
    with tempfile.TemporaryDirectory() as td:
        full = render(td, "full", [])
        nofl = render(td, "nofl", ["--no-flicker"])

        rows = []
        for f in full[:14]:
            g = gray(f)
            rows.append((g[600:].mean(), g[180:520, 0:350].mean(), g.mean()))
        r = np.array(rows)
        res["sdfgi_ramp"] = {k: [round(float(v), 1) for v in r[:, i]] for i, k in
                             enumerate(["unten_y600", "haeuschen", "ganzes_bild"])}
        res["sdfgi_ramp"]["max_step_unten"] = round(float(np.abs(np.diff(r[:, 0])).max()), 1)
        res["sdfgi_ramp"]["max_step_haeuschen"] = round(float(np.abs(np.diff(r[:, 1])).max()), 1)
        print("SDFGI-Anlauf unten:", " ".join(f"{v:.1f}" for v in r[:, 0]))
        print("SDFGI-Anlauf Häuschen:", " ".join(f"{v:.1f}" for v in r[:, 1]))

        diffs = {k: [] for k in FLICKER}
        base = {k: [] for k in FLICKER}
        for i in range(118, min(181, len(full), len(nofl))):
            ga, gb = gray(full[i]), gray(nofl[i])
            for k, (x0, y0, x1, y1) in FLICKER.items():
                diffs[k].append(ga[y0:y1, x0:x1].mean() - gb[y0:y1, x0:x1].mean())
                base[k].append(gb[y0:y1, x0:x1].mean())
        res["flicker"] = {}
        for k in FLICKER:
            d = np.array(diffs[k])
            res["flicker"][k] = {"min": round(float(d.min()), 1), "max": round(float(d.max()), 1),
                                 "mean_without": round(float(np.mean(base[k])), 1),
                                 "max_step": round(float(np.abs(np.diff(d)).max()), 1)}
            print(f"Flackern {k:18s} {d.min():6.1f} .. {d.max():5.1f} Stufen (ohne Flackern im Mittel {np.mean(base[k]):.1f})")

        rgb = np.asarray(Image.open(full[49]).convert("RGB")).astype(float)
        L = lum(rgb[55:100, 70:690].reshape(-1, 3))
        txt, bg = float(np.percentile(L, 99)), float(np.median(L))
        res["title_contrast"] = {"text_lum": round(txt, 3), "bg_lum_median": round(bg, 3),
                                 "ratio": round((txt + 0.05) / (bg + 0.05), 2)}
        print(f"Ortseinblendung Bild 49: Kontrast {(txt + 0.05) / (bg + 0.05):.2f}:1")

        gaps = []
        for i in range(25, 41):
            g = gray(full[i])
            top = next((y for y in range(140, 200) if (g[y, 104:116] < 60).mean() > 0.8), None)
            if top is None:
                continue
            gap = 0
            for y in range(top - 2, top - 30, -1):   # top - 1 ist die geglättete Kante des Kopfs
                if g[y, 150:170].mean() - g[y, 104:116].mean() > 8:
                    break
                gap += 1
            gaps.append(gap)
        res["smoke_gap_px"] = {"frames": len(gaps), "max": max(gaps), "median": float(np.median(gaps))}
        print(f"Rauch: Lücke über dem Schornsteinkopf höchstens {max(gaps)} px (Median {np.median(gaps):.0f}, {len(gaps)} Bilder)")
    pathlib.Path(a.json).write_text(json.dumps(res, indent=1, ensure_ascii=False))


if __name__ == "__main__":
    main()
