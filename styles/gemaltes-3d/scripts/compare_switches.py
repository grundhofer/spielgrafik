#!/usr/bin/env python3
"""Vergleichsschalter und zeitliche Ruhe der Nachbearbeitung messen.

    .venv/bin/python styles/gemaltes-3d/scripts/compare_switches.py [--out DIR] [--sheet PNG]

1. Schalter: Einzelbilder bei 2,0 s (Kamerafahrt) und 5,0 s (feste Endeinstellung, wie das Poster) ohne
   Oberfläche, je mit einem Schalter aus main.gd/post.gd. Anteil der Pixel, die sich um mehr als 8 Stufen
   (0..255, größter Kanal) vom vollen gemalten Bild unterscheiden. --raw ist das ungemalte 3D-Bild.
2. Haften der Striche (Kamerafahrt 1,0–2,0 s): In festen Ausschnitten (Kaiboden vorn, Felsnase) wird je
   Bildpaar die ganzzahlige Verschiebung gesucht, die den Ausschnitt am besten zur Deckung bringt; der
   Rest danach (mittlere Abweichung in Stufen) zeigt, ob das Strichmuster mit der Oberfläche mitwandert.
   Verglichen werden das ungemalte Bild, das gemalte Bild (Strichrauschen an den Oberflächen) und
   --screen-noise (Strichrauschen fest im Bild).
3. Flimmern (feste Kamera 4,6–5,6 s): mittlere Abweichung aufeinanderfolgender Bilder in ruhigen
   Ausschnitten (Himmel, Kaiboden, Felsnase), gemalt gegen ungemalt.
Optional --sheet: Bildtafel ungemalt | gemalt bei 5,0 s.
"""
import argparse, pathlib, subprocess, tempfile
import numpy as np
from PIL import Image

DEMO = pathlib.Path(__file__).resolve().parent.parent / "demo"
FPS = 30


def frames(args, t0, n):
    """n Bilder ab t0 (main.gd spult per --t0 vor); das erste aufgenommene Bild entspricht t0 + 1/30."""
    with tempfile.TemporaryDirectory() as td:
        cmd = ["godot", "--path", str(DEMO), "--position", "20000,20000", "--resolution", "1280x720",
               "--write-movie", str(pathlib.Path(td) / "f.png"), "--fixed-fps", str(FPS),
               "--quit-after", str(n), "--", f"--t0={t0:.4f}", "--no-ui"] + args
        log = subprocess.run(cmd, capture_output=True, text=True, timeout=900)
        bad = [l for l in (log.stdout + log.stderr).splitlines() if "ERROR" in l]
        if bad:
            print("  Godot:", bad[:3])
        return [np.asarray(Image.open(p).convert("RGB"), dtype=np.int16) for p in sorted(pathlib.Path(td).glob("f*.png"))]


def changed(a, b):
    return float((np.abs(a - b).max(axis=2) > 8).mean() * 100)


def best_shift_residual(a, b, box, r=6):
    x0, y0, x1, y1 = box
    pa = a[y0:y1, x0:x1]
    best = 1e9
    for dy in range(-r, r + 1):
        for dx in range(-r, r + 1):
            pb = b[y0 + dy:y1 + dy, x0 + dx:x1 + dx]
            best = min(best, float(np.abs(pa - pb).mean()))
    return best


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--sheet", default="")
    ap.add_argument("--only", default="123", help="Teile, z. B. 2")
    a = ap.parse_args()
    if "1" not in a.only:
        return part23(a.only)

    print("1. Schalter (Anteil geänderter Pixel gegenüber dem vollen Bild, ohne Oberfläche)")
    switches = [["--raw"], ["--no-kuwahara"], ["--no-lic"], ["--no-edges"], ["--no-paper"], ["--screen-noise"]]
    for t in (2.0, 5.0):
        full = frames([], t - 1.0 / FPS, 1)[0]
        for sw in switches:
            img = frames(sw, t - 1.0 / FPS, 1)[0]
            print(f"  t={t:.1f} s {' '.join(sw):16s} {changed(full, img):5.1f} %")
        if a.sheet and t == 5.0:
            raw = frames(["--raw"], t - 1.0 / FPS, 1)[0]
            sheet = np.concatenate([raw, full], axis=1).astype(np.uint8)
            Image.fromarray(sheet).resize((1280, 360), Image.LANCZOS).save(a.sheet)
            print(f"  Bildtafel: {a.sheet}")

    part23(a.only)


def part23(only):
    if "2" not in only:
        return part3()
    print("2. Haften der Striche bei Kamerafahrt (Rest nach bester Verschiebung, Stufen)")
    boxes = {"Kaiboden vorn": (160, 590, 560, 690), "Felsnase": (760, 380, 980, 440)}
    # ohne Papier: dessen Körnung liegt (richtig) fest im Bild und würde die Messung überdecken
    for label, sw in [("ungemalt", ["--raw"]), ("gemalt, ohne Papier", ["--no-paper"]),
                      ("Rauschen fest, ohne Papier", ["--screen-noise", "--no-paper"]),
                      ("ohne Striche, ohne Papier", ["--no-lic", "--no-paper"]),
                      ("gemalt mit Papier", [])]:
        seq = frames(sw, 1.0, 30)
        res = {k: np.mean([best_shift_residual(seq[i], seq[i + 1], b) for i in range(len(seq) - 1)])
               for k, b in boxes.items()}
        print(f"  {label:28s} " + "  ".join(f"{k} {v:5.2f}" for k, v in res.items()))

    if "3" in only:
        part3()


def part3():
    print("3. Flimmern bei fester Kamera (mittlere Abweichung aufeinanderfolgender Bilder, Stufen)")
    calm = {"Himmel": (300, 60, 760, 220), "Kaiboden": (60, 640, 560, 690), "Felsnase": (760, 400, 1000, 470)}
    for label, sw in [("ungemalt", ["--raw"]), ("gemalt", [])]:
        seq = frames(sw, 4.6, 30)
        out = []
        for k, (x0, y0, x1, y1) in calm.items():
            d = np.mean([np.abs(seq[i][y0:y1, x0:x1] - seq[i + 1][y0:y1, x0:x1]).mean() for i in range(len(seq) - 1)])
            out.append(f"{k} {d:5.2f}")
        print(f"  {label:10s} " + "  ".join(out))


if __name__ == "__main__":
    main()
