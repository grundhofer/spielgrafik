#!/usr/bin/env python3
"""Umgebungseffekte nachmessen (Prüfhilfe zu den traits).

    .venv/bin/python styles/diorama-tiltshift/scripts/check_effects.py TMP_DIR

Nimmt die 6 s mit --measure und --verbose auf (Movie-Writer, 30 fps) und misst in den Einzelbildern:
  - Leuchtfeuer: mittlere Helligkeit (Luma) eines Kastens um die Lampe in der Totale und Fahrt (Bilder 0–60);
    Spitze, Grundwert und Zeitpunkt; dazu der Wert "facing" aus main.gd (Strahl zur Kamera).
  - Laterne: Helligkeit eines Kastens um Laterne und beleuchtetes Pflaster in der Totale (Bilder 0–26).
  - Möwe am Faden (Gull1): Bildlage der Körpermitte je Bild (aus main.gd) und Abstand zur Kamera, dazu der
    Schärfebereich (wie main.gd: 0,92·f − 0,2 bis 1,05·f + 0,25, f = Abstand zum Dachs).
  - Nahaufnahme (ab 2,9 s): mittlere Änderung von Bild zu Bild in Kästen um die Möwe, das Ruderhausfenster
    von Boot A und an einer ruhigen Stelle (Pflaster links unten) als Vergleich.
Schreibt assets/preview/effects.json, den Bogen assets/preview/effects.png (Leuchtfeuer vor und beim Aufblitzen,
Laterne dunkel/hell, Möwe im Poster) und die Bilder der größten Leuchtfeuer-Helligkeit nach TMP_DIR.
"""
import json, pathlib, re, shutil, subprocess, sys

import numpy as np
from PIL import Image, ImageDraw

ROOT = pathlib.Path(__file__).resolve().parent.parent
DEMO = ROOT / "demo"


def luma(im):
    a = np.asarray(im.convert("RGB"), dtype=np.float32)
    return a[..., 0] * 0.2126 + a[..., 1] * 0.7152 + a[..., 2] * 0.0722


def box_mean(L, x0, y0, x1, y1):
    x0, y0 = max(0, int(x0)), max(0, int(y0))
    return float(L[y0:int(y1), x0:int(x1)].mean())


def main():
    tmp = pathlib.Path(sys.argv[1])
    frames = tmp / "frames"
    if frames.exists():
        shutil.rmtree(frames)
    frames.mkdir(parents=True)
    subprocess.run(["godot", "--headless", "--path", str(DEMO), "--import"], capture_output=True)
    r = subprocess.run(["godot", "--path", str(DEMO), "--position", "20000,20000", "--resolution", "1280x720",
                        "--write-movie", f"{frames}/f.png", "--fixed-fps", "30", "--quit-after", "180", "--",
                        "--measure", "--verbose"], capture_output=True, text=True)
    out = r.stdout + r.stderr
    errs = [l for l in out.splitlines() if "ERROR" in l or "WARNING" in l]
    pngs = sorted(frames.glob("f*.png"))
    L = [luma(Image.open(p)) for p in pngs]

    facing = {round(float(m.group(1)), 2): float(m.group(2))
              for m in re.finditer(r"Leuchtfeuer t=([\d.]+) facing=([\d.]+)", out)}
    gull = [(float(p[1]), *map(float, p[2].split(",")), float(p[3]))
            for p in (l.split() for l in out.splitlines() if l.startswith("G "))]

    # Leuchtfeuer: Kasten um die Lampe (Totale: Lampe bei etwa 676/40)
    lamp = [box_mean(x, 636, 0, 716, 80) for x in L[:61]]
    k = int(np.argmax(lamp))
    shutil.copy(pngs[k], tmp / f"lamp_peak_f{k:03d}.png")
    shutil.copy(pngs[0], tmp / "lamp_f000.png")
    # Laterne in der Totale (Glas bei etwa 858/419, Pflaster darunter)
    lant = [box_mean(x, 835, 395, 885, 470) for x in L[:27]]
    j0, j1 = int(np.argmin(lant)), int(np.argmax(lant))

    # Bogen: Leuchtfeuer bei t=0 und in der Spitze, Laterne dunkelstes/hellstes Bild (je 2-fach), Möwe bei 4,97 s
    tiles = [(pngs[0], (596, 0, 756, 150), "Leuchtfeuer t=0"), (pngs[k], (596, 0, 756, 150), f"Spitze t={(k + 1) / 30:.2f}"),
             (pngs[j0], (790, 370, 950, 520), "Laterne dunkel"), (pngs[j1], (790, 370, 950, 520), "Laterne hell")]
    g = next((g for g in gull if abs(g[0] - 4.97) < 0.017), None)
    if g:
        gx, gy = int(g[1]), int(g[2])
        tiles.append((pngs[148], (gx - 80, max(0, gy - 75), gx + 80, max(0, gy - 75) + 150), "Moewe t=4,97"))
    sheet = Image.new("RGB", (320 * len(tiles), 300), "black")
    d = ImageDraw.Draw(sheet)
    for n, (f, b, label) in enumerate(tiles):
        sheet.paste(Image.open(f).convert("RGB").crop(b).resize((320, 300), Image.LANCZOS), (n * 320, 0))
        d.rectangle([n * 320, 0, n * 320 + 130, 15], fill="black")
        d.text((n * 320 + 4, 2), label, fill="white")
    sheet.save(ROOT / "assets/preview/effects.png")

    # Nahaufnahme: Änderung je Bild in Kästen
    def change(i0, i1, boxf):
        vals = []
        for i in range(i0 + 1, i1):
            b = boxf(i)
            if b is None:
                continue
            x0, y0, x1, y1 = b
            vals.append(float(np.abs(L[i][y0:y1, x0:x1] - L[i - 1][y0:y1, x0:x1]).mean()))
        return round(float(np.mean(vals)), 2), round(float(np.max(vals)), 2)

    gpos = {round(g[0] * 30): g for g in gull}

    def gull_box(i):
        g = gpos.get(i + 1) or gpos.get(i)
        if not g:
            return None
        x, y = int(g[1]), int(g[2])
        return (max(0, x - 70), max(0, y - 60), min(1280, x + 70), min(720, y + 60))

    close0 = 88
    res = {
        "Meldungen": errs[:8],
        "Leuchtfeuer": {
            "Luma Lampenkasten 636–716/0–80, Bilder 0–60": [round(v, 1) for v in lamp],
            "Spitze": {"Bild": k, "t": round((k + 1) / 30, 2), "Luma": round(lamp[k], 1)},
            "Grundwert (Median Bilder 30–60)": round(float(np.median(lamp[30:61])), 1),
            "facing > 0,05 (t: Wert)": facing,
        },
        "Laterne Totale (Kasten 835–885/395–470, Bilder 0–26)": {
            "min": round(min(lant), 1), "max": round(max(lant), 1),
            "Schwankung in % des Mittels": round((max(lant) - min(lant)) / float(np.mean(lant)) * 100, 1),
        },
        "Möwe Gull1": {
            "Bildlage alle 0,5 s (t, x, y, Abstand m)": [[round(g[0], 2), round(g[1]), round(g[2]), round(g[3], 2)]
                                                        for g in gull if abs(g[0] * 2 - round(g[0] * 2)) < 0.017],
            "Bewegung in der Nahaufnahme (x min/max, y min/max)": [
                round(min(g[1] for g in gull if g[0] >= 2.9)), round(max(g[1] for g in gull if g[0] >= 2.9)),
                round(min(g[2] for g in gull if g[0] >= 2.9)), round(max(g[2] for g in gull if g[0] >= 2.9))],
        },
        "Nahaufnahme ab 2,9 s: mittlere/größte Änderung je Bild (Luma)": {
            "Möwe (Kasten 140×120 um die Körpermitte)": change(close0, 180, gull_box),
            "Ruderhausfenster Boot A (Kasten 430–590/0–90)": change(close0, 180, lambda i: (430, 0, 590, 90)),
            "ruhiges Pflaster links unten (Kasten 20–200/560–700)": change(close0, 180, lambda i: (20, 560, 200, 700)),
        },
    }
    (ROOT / "assets/preview/effects.json").write_text(json.dumps(res, ensure_ascii=False, indent=1))
    print(json.dumps(res, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
