#!/usr/bin/env python3
"""Misst, wie gut Figur und Foto zusammenpassen (Licht, Schärfe, Kanten), mit und ohne Angleichung.

    .venv/bin/python styles/fotoreal-standbild/tools/measure_match.py <Arbeitsordner> [--frame 156]

Rendert ohne Korn und ohne Oberfläche: angeglichen (Standard) und --raw (nur freigestellt). Ausgaben:
  schärfe   Verhältnis feinster Details (Bandpass 1 px) zu mittleren (1-3 px) in der Figur und in Fotobereichen
            gleicher Tiefe (Kisten, Kai, Boot). Gleiche Werte = gleich scharf.
  licht     Mittelwerte des weißen Bauchfells und der dunklen Weste gegen bekannte Flächen im Foto
            (weiße Leuchtturmwand, dunkle Kistenfront) und die Farbtemperatur (B/R).
  saum      äußerster Figurenring gegen den Mittelwert aus Ring innen und Hintergrund außen: > 0 heller Saum,
            < 0 dunkler Saum (Stufen 0-255).
Schreibt dazu compare.png (links roh, rechts angeglichen, Ausschnitt um den Dachs).
"""
import argparse, json, pathlib, sys

import numpy as np
from PIL import Image

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from render import render  # noqa: E402
from prep_actor import gauss  # noqa: E402

ART = HERE.parent / "demo" / "art"


def detail_ratio(L, m):
    g1, g3 = gauss(L, 1.0), gauss(L, 3.0)
    fine, mid = (L - g1)[m], (g1 - g3)[m]
    return float(fine.std() / max(mid.std(), 1e-6))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("work")
    ap.add_argument("--frame", type=int, default=156)   # Posterbild
    a = ap.parse_args()
    work = pathlib.Path(a.work)
    n = a.frame + 1
    base = ["--no-ui", "--no-grain"]
    fi = render(work / "fit", n, None, base, quiet=True)[a.frame]
    fr = render(work / "raw", n, None, base + ["--raw"], quiet=True)[a.frame]
    fo = render(work / "none", n, None, base + ["--no-actor"], quiet=True)[a.frame]
    I = {k: np.asarray(Image.open(p).convert("RGB"), np.float32) for k, p in (("fit", fi), ("raw", fr), ("none", fo))}
    actor = json.loads((ART / "actor.json").read_text())
    fx, fy = actor["feet_screen"]
    res = {}
    for k in ("fit", "raw"):
        m = np.abs(I[k] - I["none"]).max(-1) > 18
        # Inneres: 3 px vom Rand entfernt
        inner = gauss(m.astype(np.float32), 1.5) > 0.98
        L = I[k].mean(-1)
        out = {"schaerfe_figur": round(detail_ratio(L, inner), 3)}
        # Saum: äußerster Figurenring gegen den Mittelwert aus Ring innen (2 px) und Hintergrund außen (2 px).
        # > 0 heller Saum, < 0 dunkler Saum, nahe 0 kein Saum (Rand liegt zwischen Figur und Hintergrund)
        mf = m.astype(np.float32)
        gb = gauss(mf, 1.0)
        edge = m & (gb < 0.6)
        ring_in = m & (gb > 0.6) & (gauss(mf, 2.0) < 0.9)
        ring_out = ~m & (gb > 0.15)
        Lin = gauss(np.where(ring_in, L, 0), 1.5) / np.maximum(gauss(ring_in.astype(np.float32), 1.5), 1e-3)
        Lout = gauss(np.where(ring_out, L, 0), 1.5) / np.maximum(gauss(ring_out.astype(np.float32), 1.5), 1e-3)
        out["saum"] = round(float((L[edge] - (Lin[edge] + Lout[edge]) / 2).mean()), 2)
        out["saum_abs"] = round(float(np.abs(L[edge] - (Lin[edge] + Lout[edge]) / 2).mean()), 2)
        res[k] = out
    L0 = I["none"].mean(-1)
    boxes = {"kisten": (360, 470, 500, 570), "kai_vorn": (650, 620, 740, 700), "boot_1": (670, 420, 800, 470)}
    for name, (x0, y0, x1, y1) in boxes.items():
        m = np.zeros(L0.shape, bool)
        m[y0:y1, x0:x1] = True
        res[f"schaerfe_foto_{name}"] = round(detail_ratio(L0, m), 3)
    # Licht: Bauchfell und Weste in Bildschirmlage (aus der Figur abgeleitet), Vergleichsflächen im Foto
    def mean(img, b):
        x0, y0, x1, y1 = b
        return [round(float(v), 1) for v in img[y0:y1, x0:x1].reshape(-1, 3).mean(0)]
    belly = (fx - 12, fy - 80, fx + 12, fy - 60)
    for k in ("fit", "raw"):
        res[k]["bauchfell"] = mean(I[k], belly)
    res["foto_leuchtturm_weiss"] = mean(I["none"], (1080, 215, 1095, 250))
    res["foto_kistenfront"] = mean(I["none"], (360, 500, 400, 540))
    res["foto_kai_neben_fuessen"] = mean(I["none"], (650, 670, 700, 700))
    print(json.dumps(res, indent=1, ensure_ascii=False))
    (work / "match.json").write_text(json.dumps(res, indent=1, ensure_ascii=False))
    crop = (fx - 170, fy - 290, fx + 150, fy + 27)
    w = Image.new("RGB", ((crop[2] - crop[0]) * 2 + 8, crop[3] - crop[1]), (20, 20, 20))
    w.paste(Image.open(fr).convert("RGB").crop(crop), (0, 0))
    w.paste(Image.open(fi).convert("RGB").crop(crop), (crop[2] - crop[0] + 8, 0))
    w.save(work / "compare.png")


if __name__ == "__main__":
    main()
