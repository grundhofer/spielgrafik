#!/usr/bin/env python3
"""Rendert die Vorlageblätter des Eintrags mit der Demo selbst (gleicher Strahl-Shader und Glow):

    .venv/bin/python styles/vektor-display/scripts/render_sheets.py

assets/vecfont_sheet.png  Strichschrift (alle Zeichen, -- --sheet=font)
assets/badger_lines.png   Dachs als Linienfigur: fünf Laufphasen und Stehen (-- --sheet=badger)
"""
import pathlib, subprocess, tempfile

from PIL import Image

ROOT = pathlib.Path(__file__).resolve().parent.parent
DEMO = ROOT / "demo"
SHEETS = {"font": ("vecfont_sheet.png", (40, 50, 680, 640)), "badger": ("badger_lines.png", (30, 320, 1270, 660))}

for name, (out, box) in SHEETS.items():
    with tempfile.TemporaryDirectory() as td:
        subprocess.run(["godot", "--path", str(DEMO), "--position", "20000,20000", "--resolution", "1280x720",
                        "--fixed-fps", "30", "--quit-after", "3", "--write-movie", f"{td}/f.png", "--",
                        f"--sheet={name}"], capture_output=True, text=True, timeout=300, check=True)
        im = Image.open(sorted(pathlib.Path(td).glob("f*.png"))[-1]).convert("RGB").crop(box)
        im.save(ROOT / "assets" / out, optimize=True)
        print(ROOT / "assets" / out, im.size)
