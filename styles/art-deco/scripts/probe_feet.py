#!/usr/bin/env python3
"""Misst den Dachs in gerenderten Godot-Bildern (Prüflauf --probe-badger: nur Figur vor flachem Blau).
Nach styles/ukiyo-e/scripts/probe_feet.py, erweitert um die zwei Einstellungen dieser Demo.

    godot --path styles/art-deco/demo --write-movie <dir>/f.png --fixed-fps 30 --quit-after 180 -- --probe-badger
    .venv/bin/python styles/art-deco/scripts/probe_feet.py <dir>

Je Bild: Sohlenzeile (unterste Figurzeile), Bodenkontakt (Spalten der vorletzten Sohlenzeile; Lücken ab 2 px
trennen Füße), Scheitel und Nasenspitze (rechteste Spalte im oberen Viertel). Bei jedem Bildwechsel innerhalb
einer Einstellung werden alle Paare sich überdeckender Kontaktgruppen verglichen; der Standfuß ist das Paar,
dessen Ferse (linke Kante) oder Spitze (rechte Kante) am wenigsten wandert. Gemeldet: Versatz dieses Drehpunkts
(soll höchstens ±1 px betragen), Sohlenzeilen je Einstellung und Bewegung innerhalb eines Halts.
Ausgabe auch als assets/measure_feet.json.
"""
import json, pathlib, sys
import numpy as np
from PIL import Image

ROOT = pathlib.Path(__file__).resolve().parents[1]


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
            ref = im[2, 2]
        m = np.abs(im - ref).sum(-1) > 150
        tick = i + 1                      # Movie Maker: Bild i zeigt Takt i + 1
        e = tl["ticks"][min(tick, len(tl["ticks"]) - 1)]
        if not m.any():
            rows.append({"img": i, "tick": tick, "shot": e["s"], "frame": names[e["f"]], "empty": True})
            continue
        ys, xs = np.nonzero(m)
        sole, top = int(ys.max()), int(ys.min())
        cols = np.nonzero(m[sole - 1])[0]
        gaps = np.nonzero(np.diff(cols) > 1)[0]
        contact = [(int(g[0]), int(g[-1])) for g in np.split(cols, gaps + 1)] if len(cols) else []
        upper = m[top:top + (sole - top) // 4]
        nose = int(np.nonzero(upper.any(0))[0].max())
        rows.append({"img": i, "tick": tick, "shot": e["s"], "frame": names[e["f"]], "x": e["x"], "sole": sole,
                     "top": top, "nose": nose, "contact": contact, "left": int(xs.min())})
    report = []
    for a, b in zip(rows, rows[1:]):
        if a.get("empty") or b.get("empty") or a["frame"] == b["frame"] or a["shot"] != b["shot"]:
            continue
        best = None
        for ca in a["contact"]:
            for cb in b["contact"]:
                if min(ca[1], cb[1]) - max(ca[0], cb[0]) < 0:
                    continue
                dh, dt = cb[0] - ca[0], cb[1] - ca[1]
                piv = dh if abs(dh) <= abs(dt) else dt
                if best is None or abs(piv) < abs(best[0]):
                    best = (piv, ca, cb, "Ferse" if abs(dh) <= abs(dt) else "Spitze")
        if best is None:
            report.append({"img": b["img"], "shot": b["shot"], "change": f'{a["frame"]}->{b["frame"]}',
                           "d_pivot": None})
            continue
        piv, ca, cb, kind = best
        report.append({"img": b["img"], "shot": b["shot"], "change": f'{a["frame"]}->{b["frame"]}', "foot_a": ca,
                       "foot_b": cb, "pivot": kind, "d_pivot": piv, "d_sole": b["sole"] - a["sole"],
                       "d_nose": b["nose"] - a["nose"], "d_top": b["top"] - a["top"]})
    for s in (0, 1):
        soles = sorted({r["sole"] for r in rows if not r.get("empty") and r["shot"] == s})
        print(f"Einstellung {s}: Sohlenzeilen {soles}")
    for r in report:
        if r["d_pivot"] is None:
            print(f'{r["img"]:4d} {r["change"]:16s} kein gemeinsamer Kontakt')
            continue
        print(f'{r["img"]:4d} s{r["shot"]} {r["change"]:16s} Fuß {r["foot_a"]} -> {r["foot_b"]}  {r["pivot"]:6s} '
              f'{r["d_pivot"]:+d}  Sohle {r["d_sole"]:+d}  Nase {r["d_nose"]:+d}  Scheitel {r["d_top"]:+d}')
    summary = {}
    for s in (0, 1):
        walk = [r for r in report if r["shot"] == s and r["d_pivot"] is not None and r["change"].startswith("walk")
                and "->walk" in r["change"]]
        if walk:
            dist = {v: sum(1 for r in walk if r["d_pivot"] == v) for v in sorted({r["d_pivot"] for r in walk})}
            summary[s] = {"changes": len(walk), "max_abs": max(abs(r["d_pivot"]) for r in walk), "dist": dist}
            print(f"Einstellung {s}: Laufwechsel {len(walk)}, größter Drehpunktversatz {summary[s]['max_abs']}, "
                  f"Verteilung {dist}")
    moved = [(a["img"], b["img"]) for a, b in zip(rows, rows[1:]) if not a.get("empty") and not b.get("empty")
             and a["frame"] == b["frame"] and a["shot"] == b["shot"]
             and (a["contact"] != b["contact"] or a["sole"] != b["sole"])]
    print("Bewegung innerhalb eines Halts:", moved[:10] if moved else "keine")
    (ROOT / "assets/measure_feet.json").write_text(json.dumps({"summary": summary, "changes": report,
                                                                "moved_in_hold": moved}, indent=1))


if __name__ == "__main__":
    main()
