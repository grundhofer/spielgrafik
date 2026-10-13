#!/usr/bin/env python3
"""Misst die Figur in den gerenderten Godot-Bildern (Prüfmodus --probe-badger-only: nur die Figur auf Magenta).

    .venv/bin/python styles/noir/scripts/render_frames.py OUT --frames 180 -- --probe-badger-only
    .venv/bin/python styles/noir/scripts/measure_badger.py OUT [--json assets/measure_badger.json]

Je Bild: Sohlenzeile (unterste deckende Zeile), Kopfzeile (oberste), Bodenkontakt (deckende Spalten in den untersten
3 Zeilen über der Fußlinie). Bewertet wird:
  * Fußlinie: in allen Bildern gleich (±1 px).
  * Standfuß: zwischen zwei aufeinanderfolgenden Laufbildern bleibt der hintere Rand des Bodenkontakts des
    Standfußes stehen (±1 px). Gemessen über den Schablonenvergleich des Fußstreifens (untere 10 Zeilen):
    die Verschiebung der Figur gegenüber dem Vorbild minus Vorschub ergibt das Rutschen des Standfußes; zusätzlich
    die Enden der Kontaktläufe.
  * Kopf: keine Sprünge zwischen den Bildern außer bei Posenwechseln.
"""
import argparse, json, pathlib

import numpy as np
from PIL import Image

FEET_Y = 645


def figure_mask(path):
    a = np.asarray(Image.open(path).convert("RGB")).astype(np.int16)
    mag = (np.abs(a[..., 0] - 255) < 40) & (a[..., 1] < 40) & (np.abs(a[..., 2] - 255) < 40)
    return ~mag


def runs(row):
    out, start = [], None
    for i, v in enumerate(row):
        if v and start is None:
            start = i
        if not v and start is not None:
            out.append((start, i - 1))
            start = None
    if start is not None:
        out.append((start, len(row) - 1))
    return out


def best_shift(a, b, rng=14):
    """Waagerechte Verschiebung, die Streifen b am besten auf a legt (IoU)."""
    best = (-1.0, 0)
    for dx in range(-rng, rng + 1):
        bs = np.roll(b, dx, axis=1)
        inter = (a & bs).sum()
        uni = (a | bs).sum()
        if uni and inter / uni > best[0]:
            best = (inter / uni, dx)
    return best[1], best[0]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("frames_dir")
    ap.add_argument("--json")
    a = ap.parse_args()
    files = sorted(pathlib.Path(a.frames_dir).glob("f*.png"))
    rows = []
    masks = []
    for i, f in enumerate(files):
        m = figure_mask(f)
        ys, xs = np.where(m)
        if len(ys) == 0:
            rows.append({"i": i, "visible": False})
            masks.append(None)
            continue
        sole, head = int(ys.max()), int(ys.min())
        contact = runs(m[FEET_Y - 2:FEET_Y + 1].any(0))
        rows.append({"i": i, "visible": True, "sole": sole, "head": head, "x0": int(xs.min()), "x1": int(xs.max()),
                     "contact": contact})
        masks.append(m)

    # Bildwechsel (Figur auf Zweien): nur dort vergleichen, wo sich die Maske ändert
    changes = []
    for i in range(1, len(files)):
        if masks[i] is None or masks[i - 1] is None:
            continue
        if (masks[i] ^ masks[i - 1]).sum() == 0:
            continue
        foot_a = masks[i - 1][FEET_Y - 10:FEET_Y + 1]
        foot_b = masks[i][FEET_Y - 10:FEET_Y + 1]
        # Verschiebung des ganzen Fußstreifens und der Enden der Kontaktläufe
        dx, iou = best_shift(foot_a, foot_b)
        ca, cb = rows[i - 1]["contact"], rows[i]["contact"]
        end_moves = []
        for ra in ca:
            for rb in cb:
                if rb[0] <= ra[1] + 6 and rb[1] >= ra[0] - 6:
                    end_moves.append((rb[0] - ra[0], rb[1] - ra[1]))
        # Standfuß: Bodenkontakt (untere 3 Zeilen) beider Bilder; die Verschiebung im Bereich ±6 px, bei der die
        # meisten Kontaktpixel übereinanderliegen. Steht der Fuß, ist sie 0 (±1) und die Überdeckung groß.
        ka = masks[i - 1][FEET_Y - 2:FEET_Y + 1]
        kb = masks[i][FEET_Y - 2:FEET_Y + 1]
        stance = max(((int((ka & np.roll(kb, -d, axis=1)).sum()), -abs(d), d) for d in range(-6, 7)))
        same0 = int((ka & kb).sum())
        kind = "Stand" if same0 >= 0.6 * min(ka.sum(), kb.sum()) and abs(stance[2]) <= 1 else "Kontaktwechsel"
        changes.append({"i": i, "t": round(i / 30, 3), "kind": kind, "stance_shift": stance[2], "stance_px": stance[0],
                        "contact_px": [int(ka.sum()), int(kb.sum())], "same_at_0": same0,
                        "foot_shift": -dx, "iou": round(iou, 3),
                        "contact_prev": ca, "contact": cb, "end_moves": end_moves,
                        "sole": rows[i]["sole"], "head": rows[i]["head"], "head_prev": rows[i - 1]["head"]})

    soles = sorted({r["sole"] for r in rows if r.get("visible")})
    print("Sohlenzeilen über alle Bilder:", soles)
    for c in changes:
        mv = min((min(abs(e[0]), abs(e[1])) for e in c["end_moves"]), default=None)
        print(f"Bild {c['i']:3d} t={c['t']:.2f}  Standfuß {c['stance_shift']:+d} px ({c['stance_px']} Kontaktpx)  "
              f"Fußstreifen {c['foot_shift']:+d} px (IoU {c['iou']:.2f})  "
              f"kleinste Endenbewegung {mv}  Kopf {c['head_prev']}→{c['head']}  Kontakt {c['contact']}")
    real = [c for c in changes if c["iou"] < 0.995 or c["stance_shift"] != 0]
    stand = [c for c in real if c["kind"] == "Stand"]
    swap = [c for c in real if c["kind"] != "Stand"]
    worst = max((abs(c["stance_shift"]) for c in stand), default=0)
    print(f"Bildwechsel mit Änderung am Fuß: {len(real)}; davon Standphase {len(stand)} "
          f"(größte Verschiebung des Standfußes {worst} px), Kontaktwechsel {len(swap)} "
          f"(kein Fuß in beiden Bildern am Boden; Sichtprüfung über feet_overlay): "
          + ", ".join(str(c["i"]) for c in swap))
    if a.json:
        pathlib.Path(a.json).write_text(json.dumps({"soles": soles, "worst_stance_shift": worst,
                                                    "changes": changes}, indent=1))


if __name__ == "__main__":
    main()
