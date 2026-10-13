#!/usr/bin/env python3
"""Misst, was die Merkmale zum Bild beitragen (Vergleichsschalter) und wie andere Renderer abweichen.

    .venv/bin/python styles/handpainted-3d/scripts/compare_switches.py [--tmp DIR]

Schalter (main.gd): --no-paint (gemalte Texturen durch ihre Mittelfarbe ersetzt, Pinseltupfer der Figur
aus), --no-ao (ohne gebackene Verdeckung), --no-key (ohne Figurenlicht), --no-blob (ohne Bodenschatten).
Je Schalter ein Bild bei t = 2,0 s (Kamerafahrt, Halbtotale) und t = 4,8 s (Endeinstellung, Poster)
ohne Oberfläche (--no-ui), verglichen mit dem Bild ohne Schalter: Anteil der Pixel, die sich in einem
Kanal um mehr als 8 Stufen ändern, und mittlere Abweichung; dasselbe noch einmal mit Oberfläche (die deckt
Teile des Bildes ab, die Anteile sind dann kleiner) und nur in der Silhouette des Dachses (Maske aus
--mask --static-cam bei 4,8 s). Renderer: dasselbe Bild mit
--rendering-method mobile und gl_compatibility gegen Forward+ (mit Oberfläche).
Schreibt assets/preview/switches.png und assets/preview/renderers.png.
"""
import argparse
import pathlib
import re
import subprocess
import tempfile

import numpy as np
from PIL import Image, ImageDraw

SD = pathlib.Path(__file__).resolve().parent.parent
DEMO = SD / "demo"
PREV = SD / "assets" / "preview"
TIMES = [2.0, 4.8]
SWITCHES = ["", "no-paint", "no-ao", "no-key", "no-blob"]


def shot(out, t0, extra=(), method=None):
    out.mkdir(parents=True, exist_ok=True)
    cmd = ["godot", "--path", str(DEMO), "--position", "20000,20000", "--resolution", "1280x720"]
    if method:
        cmd += ["--rendering-method", method]
    cmd += ["--write-movie", str(out / "f.png"), "--fixed-fps", "30", "--quit-after", "2", "--", f"--t0={t0}"]
    cmd += [f"--{e}" for e in extra if e]
    r = subprocess.run(cmd, capture_output=True, text=True)
    log = r.stdout + r.stderr
    errs = [l for l in log.splitlines() if re.search(r"\bERROR\b|SCRIPT ERROR", l)]
    warns = [l for l in log.splitlines() if re.search(r"\bWARNING\b", l)]
    return np.asarray(Image.open(out / "f00000001.png").convert("RGB")).astype(np.int16), errs, warns


def diff(a, b, mask=None):
    d = np.abs(a - b).max(2)
    if mask is not None:
        return (d[mask] > 8).mean() * 100.0, np.abs(a - b)[mask].mean()
    return (d > 8).mean() * 100.0, np.abs(a - b).mean()


def label(im, text):
    d = ImageDraw.Draw(im)
    d.rectangle((0, 0, 8 + 7 * len(text), 18), fill=(0, 0, 0))
    d.text((4, 3), text, fill=(255, 255, 255))
    return im


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tmp", default=None)
    a = ap.parse_args()
    base = pathlib.Path(a.tmp or tempfile.mkdtemp(prefix="hp3d_switch_"))
    subprocess.run(["godot", "--headless", "--path", str(DEMO), "--import"], capture_output=True)
    PREV.mkdir(parents=True, exist_ok=True)
    mask_img, _, _ = shot(base / "mask", 4.8, ("mask", "static-cam"))
    badger = mask_img.max(2) > 128
    print(f"Dachs-Maske bei 4,8 s: {badger.sum()} Pixel")
    tiles = []
    for t0 in TIMES:
        ref = None
        for sw in SWITCHES:
            img, errs, _ = shot(base / f"t{t0}_{sw or 'voll'}", t0, ("no-ui", sw))
            if errs:
                print("FEHLER", sw, errs[:3])
            if ref is None:
                ref = img
                # Wiederholbarkeit: zweiter Lauf ohne Schalter muss bitgleich sein
                img2, _, _ = shot(base / f"t{t0}_voll2", t0, ("no-ui",))
                print(f"t={t0}: zweiter Lauf bitgleich: {bool((img2 == ref).all())}")
            else:
                share, mean = diff(ref, img)
                print(f"t={t0}: --{sw:9s} {share:5.1f} % der Pixel > 8 Stufen anders, mittlere Abweichung {mean:4.1f}")
                if t0 == 4.8:
                    bs, bm = diff(ref, img, badger)
                    print(f"         nur Dachs: {bs:5.1f} % der Pixel anders, mittlere Abweichung {bm:4.1f}")
            tiles.append(label(Image.fromarray(img.astype(np.uint8)).resize((640, 360), Image.LANCZOS),
                               f"t={t0} {sw or 'voll'}"))
    sheet = Image.new("RGB", (640 * len(SWITCHES), 360 * len(TIMES)))
    for i, im in enumerate(tiles):
        sheet.paste(im, ((i % len(SWITCHES)) * 640, (i // len(SWITCHES)) * 360))
    sheet.save(PREV / "switches.png")
    # mit Oberfläche
    for t0 in TIMES:
        ref, _, _ = shot(base / f"u{t0}_voll", t0, ())
        for sw in SWITCHES[1:]:
            img, _, _ = shot(base / f"u{t0}_{sw}", t0, (sw,))
            share, mean = diff(ref, img)
            print(f"t={t0} mit Oberfläche: --{sw:9s} {share:5.1f} % der Pixel anders, mittlere Abweichung {mean:4.1f}")

    # Renderer
    rtiles = []
    for t0 in TIMES:
        ref = None
        for method in ["forward_plus", "mobile", "gl_compatibility"]:
            img, errs, warns = shot(base / f"r{t0}_{method}", t0, (), method)
            if ref is None:
                ref = img
            else:
                share, mean = diff(ref, img)
                print(f"t={t0}: {method:16s} {share:5.1f} % der Pixel > 8 Stufen anders als Forward+, "
                      f"mittlere Abweichung {mean:4.1f}; Fehler {len(errs)}, Warnungen {len(warns)}")
                for w in (errs + warns)[:3]:
                    print("    " + w[:160])
            rtiles.append(label(Image.fromarray(img.astype(np.uint8)).resize((640, 360), Image.LANCZOS),
                                f"t={t0} {method}"))
    sheet = Image.new("RGB", (640 * 3, 360 * len(TIMES)))
    for i, im in enumerate(rtiles):
        sheet.paste(im, ((i % 3) * 640, (i // 3) * 360))
    sheet.save(PREV / "renderers.png")
    print("Temp:", base)


if __name__ == "__main__":
    main()
