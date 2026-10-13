#!/usr/bin/env python3
"""Vergleichsschalter messen: Anteil der Pixel, die sich mit und ohne Effekt ändern.

Rendert Bild 60 (Totale, 2,0 s) und Bild 150 (Nahaufnahme, 5,0 s) je Variante und vergleicht mit dem
vollen Look. Ein Pixel zählt als geändert, wenn ein Farbkanal um mehr als 8 Stufen abweicht.
Varianten (Schalter von main.gd):
  --smooth     Original-Hafen aus shared/3d mit weichen Normalen, Dachs weich, Wasser/Wolken weich,
               keine Farbabweichung je Facette (gleiche Palette, Licht, Himmel, Nebel)
  --no-jitter  nur ohne Farbabweichung je Facette
Zusätzlich Renderer: --rendering-method mobile und gl_compatibility (gleiche Bilder).
Schreibt assets/preview/switches.png (Zeilen: Bild 60, Bild 150; Spalten: voll, --smooth, --no-jitter)
und assets/preview/renderers.png (Spalten: Forward+, Mobile, Compatibility), dazu die vollen Bilder
totale_f060.png, closeup_f150.png, einen Ausschnitt badger_close.png und assets/compare_switches.json.

    .venv/bin/python styles/lowpoly-flat/scripts/compare_switches.py
"""
import json, pathlib, re, subprocess, tempfile

import numpy as np
from PIL import Image

ROOT = pathlib.Path(__file__).resolve().parent.parent
DEMO = ROOT / "demo"
FRAMES = [60, 150]


def render(td, user=(), godot=()):
    r = subprocess.run(["godot", "--path", str(DEMO), "--position", "20000,20000", "--resolution", "1280x720",
                        "--write-movie", str(pathlib.Path(td) / "f.png"), "--fixed-fps", "30",
                        "--quit-after", str(max(FRAMES) + 1), *godot, "--", *user],
                       capture_output=True, text=True)
    log = r.stdout + r.stderr
    errs = [l for l in log.splitlines() if re.search(r"\bERROR\b|SCRIPT ERROR", l)]
    warns = [l for l in log.splitlines() if re.search(r"\bWARNING\b", l)]
    return [np.asarray(Image.open(pathlib.Path(td) / f"f{n:08d}.png").convert("RGB")) for n in FRAMES], errs, warns


def changed(a, b):
    return float((np.abs(a.astype(int) - b.astype(int)).max(axis=2) > 8).mean())


def sheet(cols, path):
    tw, th = 640, 360
    im = Image.new("RGB", (tw * len(cols), th * len(FRAMES)))
    for c, imgs in enumerate(cols):
        for r, a in enumerate(imgs):
            im.paste(Image.fromarray(a).resize((tw, th), Image.LANCZOS), (c * tw, r * th))
    im.save(path)


def main():
    subprocess.run(["godot", "--headless", "--path", str(DEMO), "--import"], capture_output=True)
    res = {}
    imgs = {}
    for name, user, godot in [("full", [], []), ("smooth", ["--smooth"], []), ("no-jitter", ["--no-jitter"], []),
                              ("mobile", [], ["--rendering-method", "mobile"]),
                              ("gl_compatibility", [], ["--rendering-method", "gl_compatibility"])]:
        with tempfile.TemporaryDirectory() as td:
            imgs[name], errs, warns = render(td, user, godot)
        res[name] = {"errors": errs[:3], "warnings": warns[:3]}
        if name != "full":
            res[name]["changed_share"] = {str(f): round(changed(imgs["full"][i], imgs[name][i]), 4)
                                          for i, f in enumerate(FRAMES)}
        print(name, json.dumps(res[name], ensure_ascii=False))
    prev = ROOT / "assets" / "preview"
    prev.mkdir(parents=True, exist_ok=True)
    sheet([imgs["full"], imgs["smooth"], imgs["no-jitter"]], prev / "switches.png")
    Image.fromarray(imgs["full"][0]).save(prev / "totale_f060.png")
    Image.fromarray(imgs["full"][1]).save(prev / "closeup_f150.png")
    # Dachs in der Nahaufnahme, 2-fach (Facetten der Figur)
    Image.fromarray(imgs["full"][1]).crop((230, 380, 450, 640)).resize((440, 520), Image.NEAREST).save(
        prev / "badger_close.png")
    for k in ("smooth", "no-jitter", "mobile", "gl_compatibility"):
        res[k]["mean_abs_diff"] = {str(f): round(float(np.abs(imgs["full"][i].astype(int) - imgs[k][i].astype(int)).mean()), 2)
                                   for i, f in enumerate(FRAMES)}
    sheet([imgs["full"], imgs["mobile"], imgs["gl_compatibility"]], prev / "renderers.png")
    (ROOT / "assets" / "compare_switches.json").write_text(json.dumps(res, indent=1, ensure_ascii=False))


if __name__ == "__main__":
    main()
