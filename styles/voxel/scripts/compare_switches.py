#!/usr/bin/env python3
"""Vergleichsschalter (PIPELINE.md: Effekte messen): rendert Bild 60 (Totale) und 150 (Nahaufnahme) mit und
ohne gebackenes Voxel-AO, Voxelkanten und Sonnenschatten sowie mit den weichen Schatten der ersten Fassung,
zählt die Pixel, die sich um mehr als 8 Stufen (0..255) ändern, und misst den Nachbarkontrast (mittlere
Helligkeitsdifferenz benachbarter Pixel) auf Pflasterflächen neben dem Dachs. Legt ab:
assets/preview/switches.png (Zeilen Totale/Nahaufnahme, Spalten voll / ohne AO / ohne Kanten / alte Schatten)
und assets/preview/shadows.png (Pflaster neben dem Dachs, 4-fach: alte Schatten / jetzt / ohne Schatten).

    .venv/bin/python styles/voxel/scripts/compare_switches.py
"""
import pathlib, subprocess, sys, tempfile
import numpy as np
from PIL import Image

HERE = pathlib.Path(__file__).resolve().parent
OUT = HERE.parent / "assets" / "preview"
FR = (60, 150)
CASES = [("voll", []), ("ohne AO", ["--no-ao"]), ("ohne Kanten", ["--no-edge"]),
         ("alte Schatten", ["--old-shadow"]), ("ohne Schatten", ["--no-shadow"])]
SHEET = ["voll", "ohne AO", "ohne Kanten", "alte Schatten"]
# Pflasterflächen (x0, y0, x1, y1) ohne Figur und Objekte: Nahaufnahme rechts und links neben dem Dachs, Kai
# hinter ihm; Totale vorn links
PATCHES = {150: [(400, 610, 495, 700), (40, 640, 160, 710), (560, 470, 760, 520)], 60: [(100, 560, 300, 700)]}
ZOOM = (150, (400, 600, 500, 680))


def contrast(img, box):
    x0, y0, x1, y1 = box
    L = img[y0:y1, x0:x1].astype(float) @ np.array([0.299, 0.587, 0.114])
    return (np.abs(np.diff(L, axis=1)).mean() + np.abs(np.diff(L, axis=0)).mean()) / 2


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    td = pathlib.Path(tempfile.mkdtemp())
    imgs = {}
    for name, args in CASES:
        d = td / name.replace(" ", "_")
        subprocess.run([sys.executable, str(HERE / "snap.py"), str(d), "--frames", ",".join(map(str, FR)), "--"] + args,
                       capture_output=True, text=True)
        imgs[name] = [np.array(Image.open(d / f"f{f:04d}.png").convert("RGB")).astype(int) for f in FR]
    lines = []
    for name, _ in CASES[1:]:
        r = []
        for i, f in enumerate(FR):
            diff = np.abs(imgs[name][i] - imgs["voll"][i]).max(2) > 8
            r.append(f"Bild {f}: {diff.mean() * 100:.1f} %")
        lines.append(f"{name}: " + ", ".join(r))
    lines.append("Nachbarkontrast Pflaster (Mittel der Flächen; Bild 150 / Bild 60):")
    for name in ("voll", "alte Schatten", "ohne Schatten"):
        v = [np.mean([contrast(imgs[name][i], b) for b in PATCHES[f]]) for i, f in enumerate(FR)]
        lines.append(f"  {name}: {v[1]:.1f} / {v[0]:.1f}")
    print("\n".join(lines))
    # Tafel: halbe Größe
    W, H = 640, 360
    sheet = Image.new("RGB", (W * len(SHEET), H * len(FR)))
    for c, name in enumerate(SHEET):
        for r in range(len(FR)):
            sheet.paste(Image.fromarray(imgs[name][r].astype(np.uint8)).resize((W, H), Image.LANCZOS), (c * W, r * H))
    sheet.save(OUT / "switches.png")
    # Schatten-Ausschnitt 4-fach ohne Glättung
    f, (x0, y0, x1, y1) = ZOOM
    i = FR.index(f)
    tiles = [Image.fromarray(imgs[n][i][y0:y1, x0:x1].astype(np.uint8)).resize(((x1 - x0) * 4, (y1 - y0) * 4), Image.NEAREST)
             for n in ("alte Schatten", "voll", "ohne Schatten")]
    zs = Image.new("RGB", (sum(t.width for t in tiles) + 16 * 2, tiles[0].height), (200, 200, 200))
    x = 0
    for t in tiles:
        zs.paste(t, (x, 0)); x += t.width + 16
    zs.save(OUT / "shadows.png")
    (OUT / "switches.txt").write_text("\n".join(lines) + "\n")


if __name__ == "__main__":
    main()
