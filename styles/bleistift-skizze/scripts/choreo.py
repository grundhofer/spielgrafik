#!/usr/bin/env python3
"""Ablauftabelle des Dachses für die Demo (ein Eintrag je Takt, 30 Takte/s).

    .venv/bin/python styles/bleistift-skizze/scripts/choreo.py

Grundlage: demo/art/badger.json (scripts/build_badger.py). Der Vorschub je Bildwechsel stammt aus dem
gemessenen Standfuß (assets/walk_advance.json); der Oberkörper ist in build_badger.py so geschert, dass der Kopf
je Bildwechsel gleich weit vorrückt. Deshalb hält jedes Laufbild gleich lang (3 Takte = 10 Bilder/s) und das
Sprite springt beim Bildwechsel um den gemessenen Vorschub (auf ganze Pixel gerundet, über die Summe, damit
sich keine Rundungsfehler aufaddieren).

Ablauf: Start am linken Bildrand angeschnitten, 44 Laufbilder (4,4 s), dann Stehen (Seitenansicht), ab 4,7 s
Dreiviertelansicht zur Kamera, zweimal Blinzeln. Das letzte Laufbild muss walk_2 oder walk_6 sein (nur für diese
beiden ist der Schritt ins Stehen gemessen).
Ergebnis: demo/art/timeline.json und assets/timeline.json (Kopie).
"""
import json, pathlib, shutil

SD = pathlib.Path(__file__).resolve().parents[1]
HOLD = 3                 # Takte je Laufbild (10 Bilder/s)
N_WALK = 44              # Laufbilder
START = 3                # erstes Laufbild (walk_3 … endet nach 44 Bildern auf walk_6)
STOP_CENTER = 452.0      # Kopfmitte beim Stehen (Bildschirm-x): rechts vom Laternenpfahl
FEET_Y = 548.0           # Sohlenkante auf dem Kai (Bildschirm-y)
STAND_TICKS = 9          # 0,3 s Seitenansicht, dann Dreiviertelansicht
BLINKS = [(156, 3), (171, 3)]   # (erster Takt, Dauer) – 5,2 s und 5,7 s
TICKS = 200


def main():
    m = json.loads((SD / "demo/art/badger.json").read_text())
    order = m["order"]
    adv = m["advance"]
    head = m["head_x"]
    names = [f"walk_{(START + i) % 8}" for i in range(N_WALK)]
    last = names[-1]
    if last not in m["advance_to_stand"]:
        raise SystemExit(f"letztes Laufbild {last} hat keinen gemessenen Schritt ins Stehen")
    # relative Lage (Quellpixel x Faktor, schon in Spielpixeln) jedes Laufbilds zum ersten
    rel = [0.0]
    for i in range(1, N_WALK):
        k = int(names[i - 1].split("_")[1])
        rel.append(rel[-1] + adv[k])
    rel_stand = rel[-1] + m["advance_to_stand"][last]
    rel_turn = rel_stand + m["stand_to_turn"]
    x0 = STOP_CENTER - head["stand"] - rel_stand
    y = round(FEET_Y - m["sole_y"])
    line = []
    for tick in range(TICKS):
        i = tick // HOLD
        if i < N_WALK:
            name, x = names[i], x0 + rel[i]
        elif tick < N_WALK * HOLD + STAND_TICKS:
            name, x = "stand", x0 + rel_stand
        else:
            name, x = "turn", x0 + rel_turn
            for b0, bl in BLINKS:
                if b0 <= tick < b0 + bl:
                    name = "blink"
        line.append({"f": order.index(name), "x": int(round(x)), "y": y})
    walk_px = rel[-1]
    out = {"_comment": "Ein Eintrag je Takt (30/s): f = Bild im Bogen badger.png, x/y = linke obere Ecke des Bildes. "
                       "Erzeugt von scripts/choreo.py.",
           "frames": order, "frame_w": m["frame_w"], "frame_h": m["frame_h"], "feet_y": FEET_Y, "hold": HOLD,
           "walk_seconds": N_WALK * HOLD / 30.0, "walk_px": round(walk_px, 1),
           "speed_px_s": round(walk_px / ((N_WALK - 1) * HOLD / 30.0), 1), "timeline": line}
    (SD / "demo/art/timeline.json").write_text(json.dumps(out, indent=0))
    shutil.copy(SD / "demo/art/timeline.json", SD / "assets/timeline.json")
    print(f"Start x={line[0]['x']} ({names[0]}), Stehen x={line[N_WALK * HOLD]['x']}, Dreiviertel x={line[-1]['x']}, "
          f"y={y}, Laufweg {walk_px:.0f} px in {N_WALK * HOLD / 30:.1f} s ({out['speed_px_s']} px/s)")
    steps = sorted({line[t + 1]["x"] - line[t]["x"] for t in range(N_WALK * HOLD - 1)})
    print("Sprungweiten beim Laufen (px):", steps)


if __name__ == "__main__":
    main()
