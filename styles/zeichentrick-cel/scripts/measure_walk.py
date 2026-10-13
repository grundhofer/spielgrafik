#!/usr/bin/env python3
"""Misst den Vorschub je Laufbild aus dem Standfuß (assets/badger_cels.png) und schreibt assets/walk.json.

    .venv/bin/python styles/zeichentrick-cel/scripts/measure_walk.py

Je Bildpaar (i -> i+1) wird der Bodenkontakt (deckende Pixel in den untersten 3 Zeilen über der Sohle) verglichen:
steht derselbe Fuß in beiden Bildern flach (IoU >= 0,9 nach Verschiebung), gilt die beste Verschiebung. Sonst
bleibt der Drehpunkt des Fußes stehen: beim Aufsetzen die Ferse (linkes Ende des vorderen Fußes), beim Abdrücken
und Fersenheben die Zehe (rechtes Ende). Diese Paarregel steht als "advance_pairs" in walk.json.

Die Paarregel allein lässt den Standfuß kriechen: Die KI zeichnet den flachen Fuß nicht in jedem Bild gleich lang
(37–41 px), die beste IoU-Verschiebung hält dann weder Ferse noch Zehe fest (gemessen: Ferse 3 px rückwärts über
eine Standphase). Deshalb wird der Vorschub je Standphase gemeinsam gesucht: Eine Standphase reicht vom Aufsetzen
der Ferse (vorderer Fuß in einem Bild mit zwei Kontaktflächen) über die Bilder mit einem flachen Fuß bis zum Abdrücken
(hinterer Fuß im nächsten Bild mit zwei Kontaktflächen). Gesucht wird der ganzzahlige Vorschub, bei dem Ferse und Zehe
in Bildschirmkoordinaten am wenigsten wandern (zuerst die größere der beiden Spannen, dann ihre Summe, dann die
Nähe zur Paarregel). Ein Fuß gilt als flach, wenn seine Kontaktfläche mindestens 85 % so lang ist wie die längste;
sonst ist die Ferse gehoben und nur die Zehe zählt. Die Kontaktschwelle (Alpha > 50) entspricht der Prüfung im
gerenderten Bild (scripts/measure_feet.py, Abstand zu Magenta > 90). Ergebnis: "advance" in walk.json.
"""
import itertools
import json, pathlib

import numpy as np
from PIL import Image

ROOT = pathlib.Path(__file__).resolve().parents[1]


ALPHA = 50


def contact(a, base, rows=3):
    return (a[base - rows + 1:base + 1] > ALPHA).any(0)


def spans(c):
    out, x = [], 0
    while x < len(c):
        if c[x]:
            s = x
            while x < len(c) and c[x]:
                x += 1
            out.append((s, x - 1))
        x += 1
    return out


def best_shift(c0, c1, rng=range(-4, 32)):
    best = (-1, 0)
    for dx in rng:
        s = np.roll(c0, -dx)
        if dx > 0:
            s[-dx:] = False
        elif dx < 0:
            s[:-dx] = False
        inter = (s & c1).sum()
        union = (s | c1).sum()
        iou = inter / max(union, 1)
        if iou > best[0]:
            best = (iou, dx)
    return best


def stance_points(span_list):
    """Kontaktkanten je Laufbild: [(Bild, 'heel'|'toe', x, Phase)] und die Phasen (Startbild, Endbild)."""
    longest = max(s[1] - s[0] + 1 for sp in span_list for s in sp)
    n = len(span_list)
    starts = [i for i in range(n) if len(span_list[i]) == 2]
    phases, pts = [], []
    for k, i0 in enumerate(starts):
        i1 = starts[(k + 1) % len(starts)] + (n if k + 1 == len(starts) else 0)
        ph = []
        ph.append((i0, "heel", span_list[i0][1][0]))
        for j in range(i0 + 1, i1):
            sp = span_list[j % n][0]
            if sp[1] - sp[0] + 1 >= 0.85 * longest:
                ph.append((j, "heel", sp[0]))
            ph.append((j, "toe", sp[1]))
        ph.append((i1, "toe", span_list[i1 % n][0][1]))
        phases.append((i0, i1))
        pts.append(ph)
    return phases, pts


def drift(ph, adv):
    n = len(adv)
    xs = [0]
    for j in range(1, 2 * n + 1):
        xs.append(xs[-1] + adv[(j - 1) % n])
    out = {}
    for kind in ("heel", "toe"):
        v = [xs[j] + x for j, kd, x in ph if kd == kind]
        out[kind] = (max(v) - min(v)) if v else 0
    return out


def solve_stance(span_list, adv0):
    """Vorschub je Standphase so wählen, dass Ferse und Zehe möglichst ortsfest bleiben."""
    phases, pts = stance_points(span_list)
    n = len(adv0)
    adv = list(adv0)
    report = []
    for (i0, i1), ph in zip(phases, pts):
        idx = [j % n for j in range(i0, i1)]
        best = None
        for combo in itertools.product(*[range(adv0[j] - 4, adv0[j] + 5) for j in idx]):
            trial = list(adv)
            for j, v in zip(idx, combo):
                trial[j] = v
            d = drift(ph, trial)
            key = (max(d.values()), sum(d.values()), sum(abs(trial[j] - adv0[j]) for j in idx))
            if best is None or key < best[0]:
                best = (key, combo, d)
        for j, v in zip(idx, best[1]):
            adv[j] = v
        report.append({"drawings": [f"walk_{j % n}" for j in range(i0, i1 + 1)], "pairs": idx,
                       "heel_span_px": best[2]["heel"], "toe_span_px": best[2]["toe"],
                       "before": drift(ph, adv0)})
    return adv, report


def main():
    meta = json.loads((ROOT / "assets/sprites.json").read_text())
    a = np.array(Image.open(ROOT / "assets/badger_cels.png"))[..., 3]
    w = int(meta["cell"][0])
    # unterste deckende Zeile der Laufbilder (Sohle); dieselben drei Zeilen misst measure_feet.py im Godot-Bild
    base = max(int(np.where((a[:, :w * 8] > 127).any(1))[0].max()), 0)
    fr = {f["name"]: a[:, f["index"] * w:(f["index"] + 1) * w] for f in meta["frames"]}
    order = [f"walk_{i}" for i in range(8)]
    res = {"pairs": []}
    adv = []
    for i in range(8):
        n0, n1 = order[i], order[(i + 1) % 8]
        c0, c1 = contact(fr[n0], base), contact(fr[n1], base)
        iou, dx = best_shift(c0, c1)
        s0, s1 = spans(c0), spans(c1)
        if iou >= 0.9:
            how = "flach (IoU)"
        elif len(s0) == 2 and len(s1) == 1:
            dx, how = s0[1][0] - s1[0][0], "Ferse setzt auf (linkes Ende des vorderen Fußes)"
        elif len(s1) == 2:
            dx, how = s0[-1][1] - s1[0][1], "Zehe drückt ab (rechtes Ende des hinteren Fußes)"
        else:
            dx, how = s0[-1][1] - s1[-1][1], "Ferse hebt ab (rechtes Ende, Zehe)"
        adv.append(int(dx))
        res["pairs"].append({"from": n0, "to": n1, "advance_px": int(dx), "rule": how, "iou": round(float(iou), 3),
                             "spans_from": s0, "spans_to": s1})
        print(f"{n0}->{n1}: Vorschub {dx:3d} px  ({how}, IoU {iou:.2f})  Kontakt {s0} -> {s1}")
    c0, c1 = contact(fr["walk_6"], base), contact(fr["stand"], base)
    iou, dx = best_shift(c0, c1, range(-10, 20))
    res["walk_6_to_stand"] = {"advance_px": dx, "iou": round(float(iou), 3)}
    print(f"walk_6->stand: {dx} px IoU {iou:.2f}")
    span_list = [spans(contact(fr[nm], base)) for nm in order]
    stance_adv, report = solve_stance(span_list, adv)
    for r in report:
        print("Standphase", "-".join(r["drawings"]), "Spanne Ferse/Zehe vorher", r["before"]["heel"], "/",
              r["before"]["toe"], "px, nachher", r["heel_span_px"], "/", r["toe_span_px"], "px")
    print("Vorschub Paarregel", adv, "->", "Standphasen", stance_adv)
    res["advance_pairs"] = adv
    res["stance"] = report
    res["advance"] = [int(v) for v in stance_adv]
    res["cycle_px"] = int(sum(stance_adv))
    (ROOT / "assets/walk.json").write_text(json.dumps(res, indent=1))
    print("Zyklus", res["cycle_px"], "px")


if __name__ == "__main__":
    main()
