#!/usr/bin/env python3
"""Probelauf mit den Renderern Mobile und Compatibility (PIPELINE.md, Selbstprüfung 5).

    .venv/bin/python styles/gemaltes-3d/scripts/compare_renderers.py [--sheet PNG]

Rendert das Bild bei 2,0 s und 5,0 s mit Forward+, --rendering-method mobile und
--rendering-method gl_compatibility (ohne Oberfläche), gibt Fehler/Warnungen aus Godot und den Anteil
der Pixel aus, die um mehr als 8 Stufen (größter Kanal) vom Forward+-Bild abweichen.
"""
import argparse, pathlib, re, subprocess, tempfile
import numpy as np
from PIL import Image

DEMO = pathlib.Path(__file__).resolve().parent.parent / "demo"


def frame(method, t):
    with tempfile.TemporaryDirectory() as td:
        cmd = ["godot", "--path", str(DEMO), "--position", "20000,20000", "--resolution", "1280x720"]
        if method:
            cmd += ["--rendering-method", method]
        cmd += ["--write-movie", str(pathlib.Path(td) / "f.png"), "--fixed-fps", "30", "--quit-after", "1",
                "--", f"--t0={t - 1 / 30:.4f}", "--no-ui"]
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
        log = r.stdout + r.stderr
        issues = [l for l in log.splitlines() if re.search(r"\bERROR\b|SCRIPT ERROR|WARNING", l)]
        pngs = sorted(pathlib.Path(td).glob("f*.png"))
        img = np.asarray(Image.open(pngs[-1]).convert("RGB"), dtype=np.int16) if pngs else None
        return img, issues


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--sheet", default="")
    a = ap.parse_args()
    row = []
    for t in (2.0, 5.0):
        ref, issues = frame("", t)
        print(f"t={t:.1f} s Forward+: {len(issues)} Meldungen")
        row = [ref]
        for m in ("mobile", "gl_compatibility"):
            img, issues = frame(m, t)
            if img is None:
                print(f"  {m}: kein Bild; " + " | ".join(issues[:4]))
                continue
            share = float((np.abs(img - ref).max(axis=2) > 8).mean() * 100)
            mean = float(np.abs(img - ref).mean())
            print(f"  {m}: {share:.1f} % der Pixel > 8 Stufen anders, mittlere Abweichung {mean:.1f}; "
                  f"{len(issues)} Meldungen" + (": " + " | ".join(i[:120] for i in issues[:4]) if issues else ""))
            row.append(img)
    if a.sheet and len(row) == 3:
        sheet = np.concatenate(row, axis=1).astype(np.uint8)
        Image.fromarray(sheet).resize((1920, 360), Image.LANCZOS).save(a.sheet)
        print(f"Bildtafel (Forward+ | Mobile | Compatibility): {a.sheet}")


if __name__ == "__main__":
    main()
