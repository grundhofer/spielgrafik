#!/usr/bin/env python3
"""Prüft die Regeln des Eintrags an den Daten und an der laufenden Demo.

    .venv/bin/python styles/vorgerenderte-sprites/scripts/probe.py [--renderer forward_plus|mobile|gl_compatibility]
                                                                    [--seconds 6] [--t0 0] [--keep DIR]

1. Sprite-Bögen (demo/sprites/*.png): Alpha nur 0 oder 255, höchstens 15 Farben + Durchsichtig je Bogen
   (Lichtkegel: 15 Farben + Schwarz, additiv), jede Farbe auf dem 15-Bit-Raster.
2. Hintergrund (demo/bg/*.png): Farben auf dem 15-Bit-Raster, Zahl der Farben.
3. Aufnahme in 426×240 (Temp-Ordner): jedes Ausgabepixel auf dem 15-Bit-Raster, Farben je Bild,
   Anteil geänderter Pixel je Bild (Bewegung), Godot-Fehler und -Warnungen.
--keep DIR legt die Bilder dort ab (für Vergleiche zwischen Renderern).
"""
import argparse
import os
import pathlib
import shutil
import subprocess
import sys
import tempfile

import numpy as np
from PIL import Image

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import vs_color as C  # noqa: E402

STYLE = pathlib.Path(__file__).resolve().parent.parent


def check_sheets():
    ok = True
    for p in sorted((STYLE / "demo" / "sprites").glob("*.png")):
        a = np.asarray(Image.open(p).convert("RGBA"))
        alpha = np.unique(a[..., 3])
        op = a[a[..., 3] > 0][:, :3]
        cols = np.unique(op, axis=0)
        n555 = int((~C.is555(cols)).sum())
        if p.stem in ("beam", "lantern_halo"):     # additiv: Schwarz = keine Wirkung
            cols = cols[cols.max(1) > 0]
        bad = (len(cols) > 15 and p.stem != "badger_shadow") or n555 or not set(alpha.tolist()) <= {0, 255}
        ok &= not bad
        print(f"  {p.name:22s} {a.shape[1]:4d}×{a.shape[0]:<4d} Farben {len(cols):3d}  nicht-15-Bit {n555}  "
              f"Alpha {sorted(alpha.tolist())[:3]}{' …' if len(alpha) > 3 else ''}  {'FEHLER' if bad else 'ok'}")
    return ok


def check_bg():
    allc = []
    for p in sorted((STYLE / "demo" / "bg").glob("*.png")):
        a = np.asarray(Image.open(p).convert("RGBA"))
        op = a[a[..., 3] > 0][:, :3]
        allc.append(op)
    cols = np.unique(np.concatenate(allc), axis=0)
    n555 = int((~C.is555(cols)).sum())
    print(f"  Hintergrund gesamt: {len(cols)} Farben, nicht-15-Bit {n555}")
    return n555 == 0


def capture(renderer, seconds, t0, keep):
    n = int(round(seconds * 30))
    td = keep or tempfile.mkdtemp(prefix="vorgerenderte-sprites-probe-")
    os.makedirs(td, exist_ok=True)
    subprocess.run(["godot", "--headless", "--path", str(STYLE / "demo"), "--import"], capture_output=True)
    cmd = ["godot", "--path", str(STYLE / "demo"), "--position", "20000,20000", "--write-movie",
           os.path.join(td, "f.png"), "--fixed-fps", "30", "--quit-after", str(n)]
    if renderer:
        cmd += ["--rendering-method", renderer]
    if t0:
        cmd += ["--", f"--t0={t0}"]
    r = subprocess.run(cmd, capture_output=True, text=True)
    log = r.stdout + r.stderr
    errs = [l for l in log.splitlines() if "ERROR" in l]
    warns = [l for l in log.splitlines() if "WARNING" in l]
    files = sorted(pathlib.Path(td).glob("f*.png"))
    bad_px, ncol, changed = 0, [], []
    prev = None
    for p in files:
        a = np.asarray(Image.open(p).convert("RGB"))
        cols = np.unique(a.reshape(-1, 3), axis=0)
        ncol.append(len(cols))
        bad_px += int((~C.is555(a.reshape(-1, 3))).sum())
        if prev is not None:
            changed.append(float((np.abs(a.astype(int) - prev).max(-1) > 0).mean()))
        prev = a.astype(int)
    size = Image.open(files[0]).size if files else None
    print(f"  Aufnahme ({renderer or 'Standard'}): {len(files)} Bilder {size}, Pixel nicht auf 15 Bit: {bad_px}, "
          f"Farben je Bild {min(ncol)}–{max(ncol)}, geänderte Pixel je Bild Mittel {np.mean(changed) * 100:.2f} %")
    print(f"  Godot: {len(errs)} Fehler, {len(warns)} Warnungen")
    for l in (errs + warns)[:6]:
        print("    " + l[:160])
    if not keep:
        shutil.rmtree(td, ignore_errors=True)
    return bad_px == 0 and not errs


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--renderer", default="")
    ap.add_argument("--seconds", type=float, default=6.0)
    ap.add_argument("--t0", type=float, default=0.0)
    ap.add_argument("--keep", default="")
    ap.add_argument("--no-capture", action="store_true")
    a = ap.parse_args()
    print("Sprite-Bögen:")
    ok = check_sheets()
    print("Hintergrund:")
    ok &= check_bg()
    if not a.no_capture:
        ok &= capture(a.renderer, a.seconds, a.t0, a.keep)
    print("ok" if ok else "PROBLEME")


if __name__ == "__main__":
    main()
