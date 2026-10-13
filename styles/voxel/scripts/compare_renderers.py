#!/usr/bin/env python3
"""Probelauf mit den Renderern Mobile und Compatibility (PIPELINE.md, Bewertung mobile): Bild 60 (Totale)
und 150 (Nahaufnahme) je Renderer; Anteil der Pixel, die vom Forward+-Bild um mehr als 8 Stufen abweichen,
Fehler und Warnungen aus dem Godot-Log; Tafel assets/preview/renderers.png (Spalten Forward+, Mobile,
Compatibility; Zeilen Bild 60 und 150).

    .venv/bin/python styles/voxel/scripts/compare_renderers.py
"""
import pathlib, subprocess, sys, tempfile
import numpy as np
from PIL import Image

HERE = pathlib.Path(__file__).resolve().parent
OUT = HERE.parent / "assets" / "preview"
FR = (60, 150)
RENDERERS = ["forward_plus", "mobile", "gl_compatibility"]


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    td = pathlib.Path(tempfile.mkdtemp())
    imgs, lines = {}, []
    for r in RENDERERS:
        d = td / r
        res = subprocess.run([sys.executable, str(HERE / "snap.py"), str(d), "--frames", ",".join(map(str, FR)),
                              "--renderer", r], capture_output=True, text=True)
        log = (d / "godot.log").read_text()
        errs = [l for l in log.splitlines() if "ERROR" in l or "WARNING" in l]
        imgs[r] = [np.array(Image.open(d / f"f{f:04d}.png").convert("RGB")).astype(int) for f in FR]
        lines.append(f"{r}: {len(errs)} Fehler/Warnungen" + (f" (erste: {errs[0].strip()[:160]})" if errs else ""))
    for r in RENDERERS[1:]:
        ds = [f"Bild {f}: {(np.abs(imgs[r][i] - imgs['forward_plus'][i]).max(2) > 8).mean() * 100:.1f} %"
              for i, f in enumerate(FR)]
        lines.append(f"{r} gegen forward_plus: " + ", ".join(ds))
    print("\n".join(lines))
    W, H = 640, 360
    sheet = Image.new("RGB", (W * 3, H * 2))
    for c, r in enumerate(RENDERERS):
        for i in range(2):
            sheet.paste(Image.fromarray(imgs[r][i].astype(np.uint8)).resize((W, H), Image.LANCZOS), (c * W, i * H))
    sheet.save(OUT / "renderers.png")
    (OUT / "renderers.txt").write_text("\n".join(lines) + "\n")


if __name__ == "__main__":
    main()
