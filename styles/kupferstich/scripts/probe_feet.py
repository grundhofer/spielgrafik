#!/usr/bin/env python3
"""Misst den Dachs in der gerenderten Godot-Demo: Fußlinie, Standfuß bei jedem Bildwechsel, Kopf.

    .venv/bin/python styles/kupferstich/scripts/probe_feet.py [--frames 180] [--keep DIR]

Rendert die Demo mit --probe-badger-only (nur die Figur auf Magenta, ohne Licht), dann je Bild:
  - Deckung = Pixel, die deutlich nicht Magenta sind (Abstand > 200, also fast deckend; halbtransparente
    Kantenpixel würden die 1-px-Lücke zwischen zwei Füßen schließen); Sohle = unterste deckende Zeile
  - Bodenkontakt = deckende Spalten in den 4 Zeilen über der gemeinsamen Fußlinie (unterste Sohle aller Bilder),
    als Läufe (Ferse = linkes, Spitze = rechtes Ende)
  - Kopf = oberste Zeile und Schwerpunkt-x des obersten Viertels
Für jeden Bildwechsel (Figur ändert sich) wird geprüft, ob ein Fuß stehen bleibt: Jeder Kontaktlauf des alten Bildes
(mindestens 15 px) wird als Schablone (Silhouette der untersten 12 Zeilen über dem Lauf) im neuen Bild um -20..+20 px
verschoben gesucht; der Lauf mit der besten Übereinstimmung ist der Standfuß, seine Verschiebung der Schlupf.
Zweite Messung: Abstand der Fersen-/Spitzenenden der Kontaktläufe in den untersten 2 und 4 Zeilen (beim Abrollen
ändert sich die Form des Fußes, dann versagt die Schablone, die Spitze bleibt aber stehen). Gewertet wird die
kleinere der Messungen. (Endpunkte allein taugen auch nicht: im Doppelstand verschmelzen beide Füße in 4 Zeilen.) Ein Wechsel gilt als Standfuß-Wechsel, wenn er laut
timeline.json nach einem Bild aus foot_switch_after in assets/badger_override.json kommt (dort steht kein Fuß in
beiden Bildern).
Rumpf: Bei jedem Bildwechsel beim Laufen wird die Silhouette der Zeilen 38 bis 118 über der Sohle (Bauch bis Brust,
ohne Beine und Kopf) im neuen Bild um -25..+25 px verschoben gesucht (beste Übereinstimmung) und zusätzlich der
mittlere Vorder- und Hinterrand in den Zeilen 48 bis 98 über der Sohle verglichen. Ziel: Der Rumpf läuft nie rückwärts.
Bei Fußwechseln wird außerdem die landende Spitze verglichen: vorderstes Pixel im Band 8 bis 18 Zeilen über der Sohle
(Fuß in der Luft, altes Bild) gegen das Ende des vordersten Kontaktlaufs (neues Bild). Bilder, in denen der Clip am
linken Tafelrand die Figur anschneidet (deckende Pixel bis Spalte CLIP_X + 1), zählen beim Rumpf nicht mit.
Movie Maker schreibt das erste Bild nach dem ersten _process: gerendertes Bild i zeigt Takt i + 1 der Tabelle
(mit --probe-log in godot.log nachgeprüft).
Ergebnis: assets/measure_badger.json und eine Zusammenfassung auf der Konsole.
"""
import argparse, json, pathlib, tempfile

import numpy as np
from PIL import Image

from render_frames import render

SD = pathlib.Path(__file__).resolve().parents[1]
CLIP_X = 82          # linke Kante des Clips in Bildschirmspalten (Platte 80 + Einfassungslinie 2)


def runs(row_mask):
    out, start = [], None
    for i, v in enumerate(row_mask):
        if v and start is None:
            start = i
        if not v and start is not None:
            out.append((start, i - 1))
            start = None
    if start is not None:
        out.append((start, len(row_mask) - 1))
    return out


def measure(png, floor_row=None):
    a = np.asarray(Image.open(png).convert("RGB")).astype(np.int16)
    cover = (np.abs(a[..., 0] - 255) + a[..., 1] + np.abs(a[..., 2] - 255)) > 200
    ys, xs = np.nonzero(cover)
    if len(ys) == 0:
        return None
    sole, top = int(ys.max()), int(ys.min())
    h = sole - top
    fr = floor_row if floor_row is not None else sole
    contact = runs(cover[fr - 3:fr + 1].any(0))
    contact2 = runs(cover[fr - 1:fr + 1].any(0))
    head = xs[ys <= top + h // 4]
    rr = [int(np.nonzero(cover[r])[0].max()) for r in range(fr - 98, fr - 47) if cover[r].any()]
    ll = [int(np.nonzero(cover[r])[0].min()) for r in range(fr - 98, fr - 47) if cover[r].any()]
    air = cover[fr - 18:fr - 7].any(0)
    return {"sole": sole, "top": top, "contact": contact, "contact2": contact2, "head_x": round(float(head.mean()), 1),
            "torso_r": round(float(np.mean(rr)), 1), "torso_l": round(float(np.mean(ll)), 1),
            "air_tip": int(np.nonzero(air)[0].max()) if air.any() else None, "clipped": bool(xs.min() <= CLIP_X + 1),
            "foot": cover[fr - 11:fr + 1].copy(), "torso": cover[fr - 118:fr - 37].copy()}


def torso_shift(m0, m1):
    """Verschiebung (px) der Rumpfsilhouette von Bild m0 nach m1 mit der besten Übereinstimmung."""
    a, b = m0["torso"], m1["torso"]
    best = None
    for s in range(-25, 26):
        err = float((a != np.roll(b, -s, axis=1)).mean())
        if best is None or err < best[0] - 1e-9:
            best = (err, s)
    return best[1]


def slip(m0, m1):
    """Verschiebung des am besten passenden Fußes von Bild m0 nach m1 (px) und Anteil abweichender Pixel."""
    best = None
    for a, b in m0["contact"]:
        if b - a < 15:
            continue
        tpl = m0["foot"][:, a:b + 1]
        for s in range(-20, 21):
            if a + s < 0 or b + 1 + s > m1["foot"].shape[1]:
                continue
            err = float((tpl != m1["foot"][:, a + s:b + 1 + s]).mean())
            if best is None or err < best[0] - 1e-9 or (abs(err - best[0]) < 1e-9 and abs(s) < abs(best[1])):
                best = (err, s)
    return (best[1], round(best[0], 3)) if best else (99, 1.0)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--frames", type=int, default=180)
    ap.add_argument("--keep")
    a = ap.parse_args()
    tl = json.loads((SD / "assets/timeline.json").read_text())
    names = tl["frames"]
    switch = set(json.loads((SD / "assets/badger_override.json").read_text())["foot_switch_after"])
    seq = tl["timeline"][1:]          # Bild i zeigt Takt i + 1
    with tempfile.TemporaryDirectory() as td:
        out = pathlib.Path(a.keep or td)
        pngs, errs = render(out, a.frames, None, ["--probe-badger-only"])
        if errs:
            raise SystemExit("Godot-Fehler: " + errs[0])
        m0 = [measure(p) for p in pngs]
        floor_row = max(x["sole"] for x in m0 if x)
        m = [measure(p, floor_row) for p in pngs]
    soles = sorted({x["sole"] for x in m if x})
    changes = []
    for i in range(1, len(m)):
        f0, f1 = names[seq[i - 1]["f"]], names[seq[i]["f"]]
        if seq[i - 1]["f"] == seq[i]["f"] and seq[i - 1]["x"] == seq[i]["x"]:
            continue
        sh, err = slip(m[i - 1], m[i])
        ends = []
        for key in ("contact", "contact2"):
            e0 = [e for r in m[i - 1][key] for e in r]
            e1 = [e for r in m[i][key] for e in r]
            if e0 and e1:              # am Tafelrand angeschnitten: kein Kontaktlauf in 2 Zeilen
                ends.append(min(abs(p - q) for p in e0 for q in e1))
        best = min([abs(sh), *ends])
        kind = "Fußwechsel" if (f0 in switch and f1 != f0) else ("Blinzeln" if "blink" in (f0, f1) else "Stand")
        c = {"frame": i, "from": f0, "to": f1, "planted_diff_px": int(best), "mismatch": err,
             "kind": kind, "dx_sprite": seq[i]["x"] - seq[i - 1]["x"],
             "torso_dx": torso_shift(m[i - 1], m[i]),
             "torso_edge_dx": round(((m[i]["torso_r"] - m[i - 1]["torso_r"]) + (m[i]["torso_l"] - m[i - 1]["torso_l"])) / 2, 1)}
        if kind == "Fußwechsel":
            c["landing_toe"] = [m[i - 1]["air_tip"], m[i]["contact"][-1][1]]
        changes.append(c)
    for x in m:
        x.pop("foot", None)
        x.pop("torso", None)
    walk = [c for c in changes if c["from"].startswith("walk") and c["to"].startswith("walk")
            and not (m[c["frame"] - 1]["clipped"] or m[c["frame"]]["clipped"])]
    back = [c for c in walk if min(c["torso_dx"], c["torso_edge_dx"]) < 0]
    stand = [c for c in changes if c["kind"] == "Stand"]
    bad = [c for c in stand if c["planted_diff_px"] > 1]
    held = [c for c in changes if c["kind"] == "Stand" and c["from"].startswith("walk")]
    res = {"frames": len(m), "sole_rows": soles, "changes": changes,
           "planted_ok": len(stand) - len(bad), "planted_checked": len(stand),
           "planted_max_px": max((c["planted_diff_px"] for c in stand), default=0),
           "foot_switch": len([c for c in changes if c["kind"] == "Fußwechsel"]),
           "walk_changes": len(held),
           "head_top_range": [min(x["top"] for x in m if x), max(x["top"] for x in m if x)],
           "torso_backward": len(back), "torso_checked": len(walk),
           "torso_dx_range": [min((c["torso_dx"] for c in walk), default=0), max((c["torso_dx"] for c in walk), default=0)]}
    (SD / "assets/measure_badger.json").write_text(json.dumps(res, indent=1, ensure_ascii=False))
    print("Sohlenzeilen:", soles)
    print(f"Standfuß bei Bildwechseln: {res['planted_ok']}/{res['planted_checked']} höchstens 1 px, "
          f"max {res['planted_max_px']} px; Fußwechsel (kein gemeinsamer Standfuß, Prüfung über landende Spitze und Rumpf): {res['foot_switch']}")
    for c in bad:
        print("  >1 px:", c)
    print(f"Rumpf beim Laufen (ohne angeschnittene Bilder): {res['torso_backward']} von {res['torso_checked']} Bildwechseln rückwärts; "
          f"Verschiebung {res['torso_dx_range'][0]}..{res['torso_dx_range'][1]} px")
    last = {}
    for c in walk:
        last[(c["from"], c["to"])] = c
    for c in sorted(last.values(), key=lambda c: c["frame"]):
        extra = f", landende Spitze Luft {c['landing_toe'][0]} -> Boden {c['landing_toe'][1]}" if "landing_toe" in c else ""
        print(f"  {c['from']} -> {c['to']}: Sprite {c['dx_sprite']:+d}, Rumpf {c['torso_dx']:+d} "
              f"(Ränder {c['torso_edge_dx']:+.1f}), Standfuß {c['planted_diff_px']} px [{c['kind']}]{extra}")
    for c in back:
        print("  rückwärts:", {k: c[k] for k in ("frame", "from", "to", "torso_dx", "torso_edge_dx")})


if __name__ == "__main__":
    main()
