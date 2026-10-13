#!/usr/bin/env python3
"""Vergleichsschalter: Wie viel tragen weiche Schatten, AO und Volumen zum Bild bei? Dazu Schrittzahl-Karte
und Nahaufnahme des Dachses für den Steckbrief.

    .venv/bin/python styles/raymarching-sdf/scripts/compare_switches.py [--times 2.2,5.1]

Rendert je Zeitpunkt die Demo voll und mit main.gd --debug 2 (ohne Volumen: Strahl, Bodennebel, Rauch,
Wolken), 3 (ohne Schatten und AO), 5 (ohne Sonnenschatten), 6 (ohne AO) und gibt den Anteil der Pixel aus,
die sich um mehr als 8 bzw. 24 Stufen ändern (Oberfläche ausgeblendet über den Bildbereich ohne Textkasten
gerechnet). Schreibt assets/preview/switches.png (Zeilen: Zeitpunkte; Spalten: voll, ohne Volumen,
ohne Schatten/AO), assets/preview/steps_heatmap.png (--debug 1: Schritte des Primärstrahls, weiß = 160)
mit Mittelwerten und assets/preview/badger_close.png (feste Nahkamera, ohne Oberfläche).
"""
import argparse, pathlib, sys, tempfile
import numpy as np
from PIL import Image

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from snap import snap  # noqa: E402

PREVIEW = HERE.parent / "assets" / "preview"
MODES = {2: "ohne Volumen", 3: "ohne Schatten und AO", 5: "ohne Sonnenschatten", 6: "ohne AO"}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--times", default="2.2,5.1")
    a = ap.parse_args()
    times = [float(x) for x in a.times.split(",")]
    PREVIEW.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as td:
        td = pathlib.Path(td)
        w, h = 640, 360
        sheet = Image.new("RGB", (w * 3, h * len(times)), "black")
        heat = Image.new("RGB", (w * len(times), h), "black")
        for j, tt in enumerate(times):
            full_dir = td / "full"
            full_dir.mkdir(exist_ok=True)
            full, errs, _ = snap(full_dir, tt, user=["--debug", "0"])
            base = np.asarray(Image.open(full).convert("RGB")).astype(int)
            # Bereich ohne Oberfläche: Ortsschild oben links und (ab 3,45 s) Textkasten unten rechts aussparen
            keep = np.ones(base.shape[:2], bool)
            keep[20:85, 20:335] = False
            if tt >= 3.45:
                keep[505:705, 490:1262] = False
            sheet.paste(Image.open(full).convert("RGB").resize((w, h), Image.LANCZOS), (0, j * h))
            for mode, name in MODES.items():
                d_dir = td / f"d{mode}"
                d_dir.mkdir(exist_ok=True)
                o, errs, _ = snap(d_dir, tt, user=["--debug", str(mode)])
                arr = np.asarray(Image.open(o).convert("RGB")).astype(int)
                d = np.abs(arr - base).max(axis=2)[keep]
                print(f"t={tt}: {name}: {(d > 8).mean() * 100:.1f} % der Pixel > 8 Stufen anders, "
                      f"{(d > 24).mean() * 100:.1f} % > 24")
                if mode in (2, 3):
                    sheet.paste(Image.open(o).convert("RGB").resize((w, h), Image.LANCZOS),
                                ((1 if mode == 2 else 2) * w, j * h))
            hm_dir = td / "heat"
            hm_dir.mkdir(exist_ok=True)
            o, _, _ = snap(hm_dir, tt, user=["--debug", "1"])
            st = np.asarray(Image.open(o).convert("L")).astype(float) / 255 * 160
            print(f"t={tt}: Primärstrahl {st.mean():.1f} Schritte im Mittel, 90 % unter {np.percentile(st, 90):.0f}, "
                  f"{(st > 155).mean() * 100:.2f} % am Limit 160")
            heat.paste(Image.open(o).convert("RGB").resize((w, h), Image.LANCZOS), (j * w, 0))
        sheet.save(PREVIEW / "switches.png")
        heat.save(PREVIEW / "steps_heatmap.png")
        cl = td / "close"
        cl.mkdir()
        o, _, _ = snap(cl, 5.1, user=["--debug", "0", "--no-ui", "--cam", "2.4,1.0,5.5,0.7,0.55,1.2,13"])
        Image.open(o).convert("RGB").crop((240, 0, 1040, 720)).save(PREVIEW / "badger_close.png")
        print("geschrieben:", PREVIEW / "switches.png", PREVIEW / "steps_heatmap.png", PREVIEW / "badger_close.png")


if __name__ == "__main__":
    main()
