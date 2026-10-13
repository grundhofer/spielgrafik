#!/usr/bin/env python3
"""Misst den Dachs in gerenderten Godot-Bildern (Prüflauf --probe-badger: nur Figur, Platten roh, vor Petrol).

    godot --path styles/holzschnitt/demo --write-movie <dir>/f.png --fixed-fps 30 --quit-after 180 -- --probe-badger
    .venv/bin/python styles/holzschnitt/scripts/probe_feet.py <dir>

Je Bild: Sohlenzeile (unterste Figurzeile), Bodenkontakt (Spalten der untersten 3 Zeilen, als Gruppen),
Scheitel (oberste Zeile) und Nasenspitze (rechteste Spalte im oberen Viertel). Bei jedem Bildwechsel wird die
Kontaktgruppe gesucht, die in beiden Bildern am Boden liegt (größte Überdeckung), und ihr Versatz in px gemeldet:
Ein stehender Fuß darf beim Wechsel höchstens 1-2 px wandern (Ferse/Spitze rollt). Ausgabe auch als JSON.
"""
import json, pathlib, sys
import numpy as np
from PIL import Image

ROOT = pathlib.Path(__file__).resolve().parents[1]
BLOCK = (60, 18, 1220, 598)


def groups(cols):
    if len(cols) == 0:
        return []
    gaps = np.nonzero(np.diff(cols) > 2)[0]
    return [(int(g[0]), int(g[-1])) for g in np.split(cols, gaps + 1)]


def main():
    d = pathlib.Path(sys.argv[1])
    tl = json.loads((ROOT / "assets/timeline.json").read_text())
    names = json.loads((ROOT / "assets/badger.json").read_text())["names"]
    files = sorted(d.glob("f*.png"))
    ref = None
    rows = []
    for i, f in enumerate(files):
        im = np.asarray(Image.open(f).convert("RGB")).astype(int)
        if ref is None:
            ref = im[5, 5]            # Petrol-Grund (außerhalb des Stocks ist auch Petrol)
        x0, y0, x1, y1 = BLOCK
        m = (np.abs(im[y0:y1, x0:x1] - ref).sum(-1) > 40)          # Figur samt Papierrand
        ink = im[y0:y1, x0:x1].sum(-1) < 150                          # nur Schwarz (Sohlen ohne Papierrand)
        tick = i + 1                  # Movie Maker: Bild i zeigt Takt i + 1
        e = tl["ticks"][min(tick, len(tl["ticks"]) - 1)]
        if not m.any():
            rows.append({"img": i, "tick": tick, "frame": names[e["f"]], "empty": True})
            continue
        ys, xs = np.nonzero(m)
        sole, top = int(ys.max()), int(ys.min())
        iys = np.nonzero(ink.any(1))[0]
        isole = int(iys.max())
        contact = groups(np.nonzero(ink[isole - 2:isole + 1].any(0))[0])
        upper = m[top:top + (sole - top) // 4]
        nose = int(np.nonzero(upper.any(0))[0].max())
        rows.append({"img": i, "tick": tick, "frame": names[e["f"]], "x": e["x"], "sole": isole, "top": top,
                     "nose": nose, "contact": contact})
    # Auswertung der Wechsel
    report = []
    for a, b in zip(rows, rows[1:]):
        if a.get("empty") or b.get("empty") or a["frame"] == b["frame"]:
            continue
        best = None
        for ca in a["contact"]:
            for cb in b["contact"]:
                ov = min(ca[1], cb[1]) - max(ca[0], cb[0])
                if best is None or ov > best[0]:
                    best = (ov, ca, cb)
        _, ca, cb = best
        report.append({"img": b["img"], "change": f'{a["frame"]}->{b["frame"]}', "foot_a": ca, "foot_b": cb,
                       "d_heel": cb[0] - ca[0], "d_toe": cb[1] - ca[1], "d_sole": b["sole"] - a["sole"],
                       "d_nose": b["nose"] - a["nose"]})
    soles = sorted({r["sole"] for r in rows if not r.get("empty")})
    print("Sohlenzeilen:", soles)
    for r in report:
        print(f'{r["img"]:4d} {r["change"]:16s} Fuß {r["foot_a"]} -> {r["foot_b"]}  Ferse {r["d_heel"]:+d}  '
              f'Spitze {r["d_toe"]:+d}  Sohle {r["d_sole"]:+d}  Nase {r["d_nose"]:+d}')
    # Halte: innerhalb eines Bildes darf sich nichts bewegen
    moved = [(a["img"], b["img"]) for a, b in zip(rows, rows[1:]) if not a.get("empty") and not b.get("empty")
             and a["frame"] == b["frame"] and (a["contact"] != b["contact"] or a["sole"] != b["sole"])]
    print("Bewegung innerhalb eines Halts:", moved[:10] if moved else "keine")
    (ROOT / "assets/measure_feet.json").write_text(json.dumps({"soles": soles, "changes": report,
                                                                "moved_in_hold": moved}, indent=1))


if __name__ == "__main__":
    main()
