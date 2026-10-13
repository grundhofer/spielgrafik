#!/usr/bin/env python3
"""KI-Tuschbild -> Tuschedichte auf eigenem Reispapier.

    .venv/bin/python styles/tusche-sumie/tools/prep_bg.py

Liest assets/raw/bg.png (1536x1024) und assets/bg_override.json (Ausschnitt, Retusche-Rechtecke, Lichtpunkte).
Schritte:
  1. Ausschnitt 16:9 (crop_y) und Verkleinern auf 1280x720.
  2. Papierton des KI-Bildes schätzen (obere Hülle der Helligkeit, großflächig geglättet), Tusche und Zinnober
     je Pixel aus R und G zurückrechnen (Modell aus inkutil: T = (1-d(1-INK)) (1-r(1-VERMILION))).
  3. Papierstruktur des KI-Bildes entfernen: sehr kleine Dichten auf 0, Zinnober nur in der Rotmaske.
  4. Tonwerte: Gamma auf d (Tusche leichter oder satter), Retusche-Rechtecke auf 0 (z. B. ungewollte Marken).
Ergebnis:
  assets/bg.png           fertiges Bild (eigenes Papier * Transmission), 1280x720
  assets/bg_ink.png       Transmission RGB + Dichte im Alpha (für das Einziehen der Tusche im Godot-Shader)
  assets/bg_meta.json     Lichtpunkte, Wasserband, Laufzeile usw. in Bildschirmkoordinaten (aus der Override-Datei)
"""
import json

import numpy as np
from PIL import Image

from inkutil import ROOT, W, H, ALPHA_FLOOR, INK_RGB, VERMILION_RGB, blur, compose, save_rgb


def envelope(L, block=24, q=0.97):
    """Obere Hülle (Papierhelligkeit) je Block, weich interpoliert."""
    h, w = L.shape
    gh, gw = h // block, w // block
    a = L[:gh * block, :gw * block].reshape(gh, block, gw, block).transpose(0, 2, 1, 3).reshape(gh, gw, -1)
    e = np.quantile(a, q, axis=2).astype(np.float32)
    # Blöcke voller Tusche: Papierwert von hellen Nachbarn übernehmen (Maximum-Filter + Glätten)
    big = Image.fromarray(e, "F").resize((w, h), Image.BICUBIC)
    env = np.asarray(big, np.float32)
    return env


def unmix(rgb, paper):
    """Löst je Pixel Tusche d und Zinnober r aus R- und G-Kanal (Fixpunkt-Iteration)."""
    tr = np.clip(rgb[..., 0] / paper[..., 0], 0, 1)
    tg = np.clip(rgb[..., 1] / paper[..., 1], 0, 1)
    ki, vi = 1 - INK_RGB, 1 - VERMILION_RGB
    d = 1 - tr
    r = np.zeros_like(d)
    for _ in range(12):
        # R: tr = (1 - d ki0)(1 - r vi0); G: tg = (1 - d ki1)(1 - r vi1)
        r = np.clip((1 - tg / np.maximum(1 - d * ki[1], 1e-3)) / vi[1], 0, 1)
        d = np.clip((1 - tr / np.maximum(1 - r * vi[0], 1e-3)) / ki[0], 0, 1)
    return d, r


def main():
    ov = json.loads((ROOT / "assets/bg_override.json").read_text())
    raw = Image.open(ROOT / ov.get("source", "assets/raw/bg.png")).convert("RGB")
    cy = ov.get("crop_y", 80)
    raw = raw.crop((0, cy, 1536, cy + 864)).resize((W, H), Image.LANCZOS)
    rgb = np.asarray(raw, np.float32) / 255.0
    L = rgb.mean(axis=2)
    env = blur(envelope(L, 32, 0.96), 24)
    # Papierfarbe des KI-Bildes: mittlere Farbe der hellsten Pixel, skaliert mit der Hülle
    bright = L > np.quantile(L, 0.9)
    pc = rgb[bright].mean(axis=0)
    paper_ai = (env / max(pc.mean(), 1e-3))[..., None] * pc[None, None, :]
    paper_ai = np.maximum(paper_ai, rgb)                      # nie dunkler als das Bild selbst
    d, r = unmix(rgb, paper_ai)

    # Rotmaske: nur deutlich zinnoberfarbene Stellen behalten Rot, sonst wird Papierstruktur rötlich
    sat = (rgb[..., 0] - rgb[..., 1]) / np.maximum(rgb[..., 0], 1e-3)
    redmask = np.clip((sat - ov.get("red_sat", 0.22)) * 8, 0, 1)
    redmask = np.clip(blur(redmask, 1.0) * 1.5, 0, 1)
    r = r * redmask
    # Papierstruktur des KI-Bildes entfernen
    floor = ov.get("ink_floor", 0.035)
    d = np.clip((d - floor) / (1 - floor), 0, 1)
    d = d ** ov.get("ink_gamma", 1.0) * ov.get("ink_gain", 1.0)
    for x0, y0, x1, y1 in ov.get("erase", []):
        d[y0:y1, x0:x1] = 0
        r[y0:y1, x0:x1] = 0
    d = np.clip(d, 0, 1)

    paper = np.asarray(Image.open(ROOT / "assets/paper.png").convert("RGB"), np.float32) / 255.0
    save_rgb(compose(paper, d, r), ROOT / "assets/bg.png")
    t = (1 - d[..., None] * (1 - INK_RGB)) * (1 - r[..., None] * (1 - VERMILION_RGB))
    # Alpha: Reihenfolge für das Einziehen (helle Lasuren zuerst, satte Striche zuletzt)
    # nie unter ALPHA_FLOOR: Godots Import ersetzt sonst die Farbe fast transparenter Pixel (Papier!) durch
    # Nachbarfarben, und um jedes Objekt entstehen graue Blöcke (siehe inkutil)
    order = ALPHA_FLOOR + np.clip(np.maximum(d, r * 0.8), 0, 1) * (1 - ALPHA_FLOOR)
    rgba = np.dstack([t, order])
    Image.fromarray((np.clip(rgba, 0, 1) * 255 + 0.5).astype(np.uint8), "RGBA").save(ROOT / "assets/bg_ink.png")
    meta = {k: v for k, v in ov.items() if k not in ("erase",)}
    (ROOT / "assets/bg_meta.json").write_text(json.dumps(meta, indent=1, ensure_ascii=False))
    print("ok bg; Tusche-Mittel %.3f, Anteil Papier (d<0.02) %.2f, Zinnober-Pixel %d" % (
        d.mean(), (d < 0.02).mean(), int((r > 0.2).sum())))


if __name__ == "__main__":
    main()
