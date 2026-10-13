#!/usr/bin/env python3
"""Misst die Figur in der laufenden Godot-Demo (Prüfmodus --measure: nur der Dachs auf Magenta).

    .venv/bin/python styles/aquarell/tools/measure_badger.py [--keep DIR]

Je Bild (30 fps, 6 s): unterste deckende Zeile (Fußlinie), x-Bereich der Fußsohle(n) in den untersten 3 Zeilen,
Kopf (oberste Zeile) und Mitte des oberen Viertels. Prüft: (1) beim Laufen bleibt der Standfuß über die Bilder,
in denen er steht, ortsfest (±1 px); (2) die Fußlinie ist in allen Bildern gleich (±1 px). Welche Bilder Laufen
und welche Stehen sind, steht im Ablauf in demo/art/scene.json (Bogen "walk" = Laufen).
"""
import argparse, json, pathlib, subprocess, sys, tempfile
import numpy as np
from PIL import Image

ROOT = pathlib.Path(__file__).resolve().parents[1]


def segments(row):
    xs = np.where(row)[0]
    if len(xs) == 0:
        return []
    cuts = np.where(np.diff(xs) > 3)[0]
    starts = np.r_[xs[0], xs[cuts + 1]]
    ends = np.r_[xs[cuts], xs[-1]]
    return [(int(a), int(b)) for a, b in zip(starts, ends)]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--keep", default="")
    ap.add_argument("--seconds", type=float, default=6.0)
    a = ap.parse_args()
    td = pathlib.Path(a.keep) if a.keep else pathlib.Path(tempfile.mkdtemp())
    td.mkdir(parents=True, exist_ok=True)
    n = int(a.seconds * 30)
    subprocess.run(["godot", "--path", str(ROOT / "demo"), "--position", "20000,20000", "--resolution", "1280x720",
                    "--write-movie", str(td / "m.png"), "--fixed-fps", "30", "--quit-after", str(n), "--", "--measure"],
                   capture_output=True, text=True, timeout=600)
    rows = []
    soles6 = {}                                   # untere 6 Zeilen der Figur je Bild (für den Schlupf)
    for i, f in enumerate(sorted(td.glob("m*.png"))[:n]):
        im = np.asarray(Image.open(f).convert("RGB")).astype(int)
        mask = ~((im[..., 0] > 200) & (im[..., 1] < 60) & (im[..., 2] > 200))
        ys, xs = np.where(mask)
        if len(ys) == 0:
            rows.append(None)
            continue
        bottom, top = ys.max(), ys.min()
        h = bottom - top + 1
        sole = mask[bottom - 2:bottom + 1].any(0)
        segs = segments(sole)
        head = mask[top:top + h // 4]
        hx = np.where(head.any(0))[0]
        soles6[i] = mask[bottom - 5:bottom + 1].copy()
        rows.append({"i": i, "bottom": int(bottom), "top": int(top), "h": int(h), "soles": segs,
                     "head_cx": float((hx.min() + hx.max()) / 2)})
    # Auswertung
    tl = json.loads((ROOT / "demo/art/scene.json").read_text())["badger"]["timeline"]
    fps = json.loads((ROOT / "demo/art/scene.json").read_text())["badger"]["fps"]
    per = int(round(30 / fps))
    is_walk = lambda i: tl[min(len(tl) - 1, i // per)][0] == "walk"
    bots = [r["bottom"] for r in rows if r]
    print(f"Fußlinie: min {min(bots)} max {max(bots)} (Spanne {max(bots) - min(bots)} px)")
    print("Bild  Fußlinie  Höhe  Sohlen (x-Bereiche in den untersten 3 Zeilen)")
    for r in rows:
        if r and (r["i"] % 2 == 0):
            print(f"{r['i']:4d}  {r['bottom']:5d}  {r['h']:4d}  {r['soles']}")
    # Standfuß: Beim Laufen nach rechts bleibt die Ferse (linkes Ende der hintersten Sohle) stehen, solange der Fuß
    # aufsetzt. Läufe aus 15-fps-Bildern (jedes 2. Bild), in denen sich die Ferse um höchstens 2 px bewegt, gelten als
    # Standphase; gemeldet wird die größte Abweichung innerhalb solcher Läufe.
    walk = [r for r in rows if r and r["i"] % per == 0 and is_walk(r["i"])]
    heels = [r["soles"][0][0] for r in walk]
    runs, cur = [], [0]
    for j in range(1, len(heels)):
        if abs(heels[j] - heels[cur[0]]) <= 2:
            cur.append(j)
        else:
            runs.append(cur)
            cur = [j]
    runs.append(cur)
    stance = [r for r in runs if len(r) >= 2]
    dev = max((max(heels[j] for j in r) - min(heels[j] for j in r)) for r in stance) if stance else None
    print(f"Laufen: {len(stance)} Standphasen aus je {[len(r) for r in stance]} Bildern ({fps} fps), "
          f"größte Fersen-Abweichung darin {dev} px")
    # Schlupf je Bildwechsel (Prüfung 1): Verschiebung, bei der die untersten 6 Zeilen von Bild i+1 am besten auf Bild i
    # liegen (IoU). Steht derselbe Fuß in beiden Bildern, ist das der Schlupf des Standfußes (soll 0 ±1 sein). Beim
    # Fußwechsel (Doppelstand) ist die IoU klein und der Wert nicht aussagekräftig; dort gilt der von Hand gemessene
    # Vorschub aus assets/badger_ai_override.json (Begründung dort).
    slips = []
    wf = [r["i"] for r in walk]
    for a_, b_ in zip(wf, wf[1:]):
        A, B = soles6[a_], soles6[b_]
        best = max(((A & np.roll(B, d, 1)).sum() / max(1, (A | np.roll(B, d, 1)).sum()), -d) for d in range(-8, 9))
        slips.append({"from": a_, "to": b_, "iou": round(float(best[0]), 2), "shift": int(best[1])})
    same = [x for x in slips if x["iou"] >= 0.7]
    swap = [x for x in slips if x["iou"] < 0.7]
    print(f"Schlupf Standfuß (gleicher Fuß, IoU >= 0.7, {len(same)} Wechsel): "
          f"{sorted(set(x['shift'] for x in same))} px; {len(swap)} Fußwechsel (Doppelstand, IoU < 0.7) nicht so messbar")
    stand = [r["bottom"] for r in rows if r and not is_walk(r["i"])]
    if stand:
        print(f"Stehen/Drehen/Winken: Fußlinie {min(stand)}..{max(stand)}")
    (ROOT / "assets/check").mkdir(parents=True, exist_ok=True)
    (ROOT / "assets/check/badger_measure.json").write_text(json.dumps({"frames": rows, "slips": slips}, indent=0))
    print("gespeichert: assets/check/badger_measure.json")


if __name__ == "__main__":
    main()
