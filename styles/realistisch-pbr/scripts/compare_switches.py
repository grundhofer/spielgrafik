#!/usr/bin/env python3
"""Vergleichsschalter: Was trägt jedes Merkmal zum Bild bei? (PIPELINE.md -> Blender/Effekte messen)

    .venv/bin/python styles/realistisch-pbr/scripts/compare_switches.py

Rendert die Endeinstellung (feste Kamera wie CAM_KEYS[2], t = 4,8 s, ohne Oberfläche) einmal voll und
je einmal mit einem Merkmal aus, nach 30 Bildern (TAA, SDFGI und Nebel eingeschwungen). Misst den Anteil
der Pixel, die sich um mehr als 8 Stufen (0..255, größter Kanal) ändern, und die mittlere Abweichung.
Außerdem dieselbe Einstellung in den Renderern Mobile und Compatibility, und der volumetrische Nebel in
der Totale (Bild 30 der Fahrt) mit Helligkeit um Fenster und Laterne (Lichtschein im Dunst).
Schreibt assets/preview/switches.jpg, assets/preview/renderers.jpg, assets/preview/fog.jpg und
assets/switches.json.
"""
import json
import pathlib
import subprocess
import sys
import tempfile

import numpy as np
from PIL import Image, ImageDraw, ImageFont

ENTRY = pathlib.Path(__file__).resolve().parent.parent
SNAP = ENTRY / "scripts" / "snap.py"
CAM = "--cam=-0.95,1.2,5.0,-0.1,1.04,-0.4,52"
BASE = [CAM, "--t0=4.8", "--no-ui"]
CASES = [
    ("voll", []),
    ("ohne Texturen (glTF-Farben)", ["--flat"]),
    ("ohne Parallaxe", ["--no-pom"]),
    ("ohne SDFGI", ["--no-sdfgi"]),
    ("ohne SSR", ["--no-ssr"]),
    ("ohne SSAO+SSIL", ["--no-ssao", "--no-ssil"]),
    ("ohne vol. Nebel", ["--no-volfog"]),
    ("ohne Dunst an Laterne/Fenster", ["--no-haze"]),
    ("ohne Fell", ["--no-fur"]),
    ("ohne Tiefenschärfe", ["--no-dof"]),
]
# Totale: Bild 30 der Kamerafahrt (t = 1,0 s); Ausschnitte um Fenster und Laterne (x0, y0, x1, y1)
TOTALE = [("voll", []), ("ohne vol. Nebel", ["--no-volfog"]), ("ohne Dunst", ["--no-haze"])]
BOX_TOTALE = {"vor dem Fenster": (60, 330, 300, 520), "um die Laterne (Totale)": (960, 310, 1100, 440)}
BOX_END = {"um die Laterne (Endeinstellung)": (1040, 160, 1280, 420)}
RENDERERS = [("Forward+", ""), ("Mobile", "mobile"), ("Compatibility", "gl_compatibility")]


def render(td, name, extra, renderer="", base=None, frames=30):
    out = pathlib.Path(td) / (name.replace(" ", "_").replace("/", "_") + ".png")
    cmd = [sys.executable, str(SNAP), str(out), "--frames", str(frames)]
    if renderer:
        cmd += ["--renderer", renderer]
    subprocess.run(cmd + ["--"] + (BASE if base is None else base) + extra, check=True, capture_output=True,
                   text=True)
    return np.asarray(Image.open(out).convert("RGB"))


def box_mean(a, b):
    x0, y0, x1, y1 = b
    return float(a[y0:y1, x0:x1].mean())


def sheet(images, labels, path, cols):
    w, h = 426, 240
    rows = (len(images) + cols - 1) // cols
    im = Image.new("RGB", (w * cols, h * rows), "black")
    d = ImageDraw.Draw(im)
    font = ImageFont.truetype(str(ENTRY / "demo" / "fonts" / "SourceSans3.ttf"), 14)   # mit Umlauten
    for i, (a, lab) in enumerate(zip(images, labels)):
        x, y = (i % cols) * w, (i // cols) * h
        im.paste(Image.fromarray(a).resize((w, h), Image.LANCZOS), (x, y))
        tw = d.textlength(lab, font=font)
        d.rectangle([x, y, x + tw + 10, y + 19], fill="black")
        d.text((x + 5, y + 2), lab, fill="white", font=font)
    im.save(path, quality=86)


def main():
    res = {}
    prev = ENTRY / "assets" / "preview"
    prev.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as td:
        imgs, labels = [], []
        full = None
        for name, extra in CASES:
            a = render(td, name, extra)
            if full is None:
                full = a.astype(np.int16)
                labels.append(name)
            else:
                d = np.abs(a.astype(np.int16) - full)
                share = float((d.max(axis=2) > 8).mean())
                res[name] = {"changed_share": round(share, 4), "mean_abs": round(float(d.mean()), 2)}
                labels.append(f"{name}: {share * 100:.1f} %")
                print(f"{name:32s} {share * 100:5.1f} % der Pixel > 8 Stufen, mittlere Abweichung {d.mean():.1f}")
            imgs.append(a)
        sheet(imgs, labels, prev / "switches.jpg", 3)
        nofog = imgs[[n for n, _ in CASES].index("ohne vol. Nebel")]
        for k, b in BOX_END.items():
            res["Helligkeit " + k] = {"voll": round(box_mean(full, b), 1), "ohne vol. Nebel": round(box_mean(nofog, b), 1)}
            print(f"Helligkeit {k}: voll {box_mean(full, b):.1f}, ohne vol. Nebel {box_mean(nofog, b):.1f}")
        tot = {}
        for name, extra in TOTALE:
            tot[name] = render(td, "tot_" + name, extra, base=["--no-ui"], frames=31)
        t_full = tot["voll"].astype(np.int16)
        crops, clabels = [], []
        for name, a in tot.items():
            if name != "voll":
                d = np.abs(a.astype(np.int16) - t_full)
                share = float((d.max(axis=2) > 8).mean())
                res["Totale " + name] = {"changed_share": round(share, 4), "mean_abs": round(float(d.mean()), 2)}
                print(f"Totale {name:22s} {share * 100:5.1f} % der Pixel > 8 Stufen")
            for k, b in BOX_TOTALE.items():
                res.setdefault("Helligkeit " + k, {})[name] = round(box_mean(a, b), 1)
            crops.append(a[300:540, 0:1280])
            clabels.append(f"Totale {name}")
        for k in BOX_TOTALE:
            print(f"Helligkeit {k}: {res['Helligkeit ' + k]}")
        im = Image.new("RGB", (1280, 240 * len(crops)), "black")
        d = ImageDraw.Draw(im)
        font = ImageFont.truetype(str(ENTRY / "demo" / "fonts" / "SourceSans3.ttf"), 18)
        for i, (c, lab) in enumerate(zip(crops, clabels)):
            im.paste(Image.fromarray(c), (0, 240 * i))
            d.rectangle([0, 240 * i, d.textlength(lab, font=font) + 12, 240 * i + 24], fill="black")
            d.text((6, 240 * i + 2), lab, fill="white", font=font)
        im.save(prev / "fog.jpg", quality=86)
        imgs, labels = [], []
        for name, r in RENDERERS:
            a = render(td, "r_" + name, [], r)
            if name != "Forward+":
                d = np.abs(a.astype(np.int16) - full)
                share = float((d.max(axis=2) > 8).mean())
                res["Renderer " + name] = {"changed_share": round(share, 4), "mean_abs": round(float(d.mean()), 2)}
                labels.append(f"{name}: {share * 100:.1f} % anders")
                print(f"Renderer {name:24s} {share * 100:5.1f} % der Pixel > 8 Stufen, mittlere Abweichung {d.mean():.1f}")
            else:
                labels.append(name)
            imgs.append(a)
        sheet(imgs, labels, prev / "renderers.jpg", 3)
    (ENTRY / "assets" / "switches.json").write_text(json.dumps(res, indent=1, ensure_ascii=False))


if __name__ == "__main__":
    main()
