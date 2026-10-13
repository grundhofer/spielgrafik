#!/usr/bin/env python3
"""Misst die Figur im echten Godot-Bild (PIPELINE.md → Figuren und Animation).

    .venv/bin/python styles/bilderbuch-gouache/scripts/measure_badger.py [--out <tmpdir>]

Rendert demo/test/measure.tscn (Hauptszene, nur die Figur ohne Schatten auf Magenta) 180 Bilder bei 30 fps und prüft:
  * Fußzeile (unterste deckende Zeile) in allen Bildern;
  * Laufen: Bodenkontakt (unterste 2 Zeilen) je Laufbild; innerhalb einer Standphase muss die Kontaktspanne ortsfest
    sein (±1 px), im Doppelstand innerhalb der Spannen von altem und neuem Standfuß liegen. (Ein Vergleich der
    untersten 6 Zeilen per IoU taugt an Fußwechseln nicht: er zentriert den breiteren Doppelfuß-Klecks und meldet
    dann -12 px, obwohl nur die Ferse des hinteren Fußes abhebt.)
  * Stehen/Drehen/Blinzeln: Fußzeile gleich, Kopfoberkante (ohne Atmen) und Sohlenmitte.
"""
import argparse, json, pathlib, subprocess, sys, tempfile

import numpy as np
from PIL import Image

ROOT = pathlib.Path(__file__).resolve().parents[1]


def render(out):
    cmd = ["godot", "--path", str(ROOT / "demo"), "res://test/measure.tscn", "--position", "20000,20000",
           "--resolution", "1280x720", "--write-movie", str(out / "f.png"), "--fixed-fps", "30", "--quit-after", "180"]
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
    bad = [l for l in (r.stdout + r.stderr).splitlines() if "ERROR" in l]
    if bad:
        print("\n".join(bad))
    return sorted(out.glob("f*.png"))


def mask(p):
    a = np.asarray(Image.open(p).convert("RGB"), np.int16)
    # "Figur" = Pixel, die mindestens etwa zur Hälfte von der Figur gedeckt sind (Magenta-Anteil < 50 %); so zählt
    # die halbdurchsichtige Kantenglättung der untersten Zeile nicht als Fuß.
    return (a[..., 0] < 200) | (a[..., 2] < 200) | (a[..., 1] > 70)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out")
    a = ap.parse_args()
    out = pathlib.Path(a.out or tempfile.mkdtemp(prefix="bbg_measure_"))
    out.mkdir(parents=True, exist_ok=True)
    pngs = render(out)
    tl = json.loads((ROOT / "assets/timeline.json").read_text())["rows"]
    print("Bilder:", len(pngs), "in", out)
    ms = [mask(p) for p in pngs[:len(tl)]]
    res = {"frames": len(ms), "feet": [], "walk": [], "idle": []}
    for f, m in enumerate(ms):
        ys, xs = np.nonzero(m)
        res["feet"].append(int(ys.max()))
    feet = np.array(res["feet"])
    print("Fußzeile: min", feet.min(), "max", feet.max(), "Werte", sorted(set(feet.tolist())))
    # Laufen: Bodenkontakt = deckende Spalten in den untersten 2 Zeilen (über der Fußzeile). Ein stehender Fuß
    # ergibt über mehrere Laufbilder dieselbe Kontaktspanne (±1 px). Bilder mit Doppelstand (Fußwechsel) müssen
    # innerhalb der Spanne aus vorigem und nächstem Standfuß liegen (hinterer Fuß rollt über die Spitze ab, vorderer
    # setzt mit der Ferse auf); was darüber hinausragt, wäre Schlupf.
    contact = []
    for f in range(0, 120, 2):
        m = ms[f]
        bot = feet[f]
        c = np.nonzero(m[bot - 1:bot + 1].any(0))[0]
        contact.append((f, tl[f][1], int(c.min()), int(c.max())))
    groups = [[contact[0]]]
    for c in contact[1:]:
        g = groups[-1]
        if abs(c[2] - g[0][2]) <= 2 and abs(c[3] - g[0][3]) <= 2:
            g.append(c)
        else:
            groups.append([c])
    stances = [g for g in groups if len(g) >= 2]
    worst_stance = max(max(abs(c[2] - g[0][2]) for c in g) for g in stances)
    worst_stance = max(worst_stance, max(max(abs(c[3] - g[0][3]) for c in g) for g in stances))
    slips = []
    for gi, g in enumerate(groups):
        if len(g) >= 2:
            continue
        f, img, x0, x1 = g[0]
        prev = next((h for h in reversed(groups[:gi]) if len(h) >= 2), None)
        nxt = next((h for h in groups[gi + 1:] if len(h) >= 2), None)
        lo = prev[0][2] if prev else -10 ** 6
        hi = nxt[0][3] if nxt else 10 ** 6
        out = max(0, lo - x0) + max(0, x1 - hi)
        slips.append(out)
        res["walk"].append({"frame": f, "img": img, "contact": [x0, x1], "allowed": [lo, hi], "outside_px": out})
    for g in stances:
        res["walk"].append({"stance_frames": [c[0] for c in g], "imgs": [c[1] for c in g],
                            "contact": [[c[2], c[3]] for c in g]})
    print("Laufen: %d Standphasen, Kontaktspanne innerhalb einer Standphase höchstens %d px verschoben" %
          (len(stances), worst_stance))
    print("Laufen: Doppelstand-Bilder außerhalb der Spanne aus vorigem und nächstem Standfuß: max %d px (%d Bilder)"
          % (max(slips) if slips else 0, len(slips)))
    for g in stances[:4]:
        print("  Standphase Bilder", [c[0] for c in g], "walk", [c[1] for c in g], "Kontakt",
              [(c[2], c[3]) for c in g])
    res["summary"] = {"stance_max_shift_px": int(worst_stance), "transition_max_outside_px": int(max(slips or [0]))}
    # Stehen/Drehen
    for f in range(118, 180):
        m = ms[f]
        ys, xs = np.nonzero(m)
        bot = ys.max()
        band = m[bot - 5:bot + 1].any(0)
        bx = np.nonzero(band)[0]
        res["idle"].append({"frame": f, "sheet": tl[f][0], "img": tl[f][1], "feet": int(bot), "top": int(ys.min()),
                            "sole_mid": round((bx.min() + bx.max()) / 2, 1), "sy": tl[f][4]})
    for r in res["idle"][::4]:
        print(f"  Bild {r['frame']:3d} {r['sheet']}_{r['img']}: Fuß {r['feet']} Kopf {r['top']} Sohlenmitte "
              f"{r['sole_mid']} (sy {r['sy']})")
    (ROOT / "assets/measure_badger.json").write_text(json.dumps(res, indent=1))
    print("ok -> assets/measure_badger.json")


if __name__ == "__main__":
    main()
