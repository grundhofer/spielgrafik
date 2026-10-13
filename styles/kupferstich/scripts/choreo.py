#!/usr/bin/env python3
"""Rechnet den Ablauf der Figur für alle Bilder der Aufnahme vor (30 fps): Bild im Bogen, Lage, Schatten.

    .venv/bin/python styles/kupferstich/scripts/choreo.py

Laufen: Die KI-Laufbilder haben ungleiche Schritte (der Standfuß wandert je Bild 3 bis 18 Spielpixel). Damit der
Standfuß steht, rückt die Figur nur beim Bildwechsel vor, und zwar genau um den gemessenen Vorschub
(assets/badger_override.json). Die Haltezeit jedes Bildes ist proportional zum Vorschub (Tempo V px je Takt),
gerundet auf ganze Takte, mindestens 2 (also höchstens 15 Bilder/s): große Schritte stehen länger, Zwischenposen
kurz. V ist so gewählt, dass nur Halte von 2 und 3 Takten entstehen (15 und 10 Bilder/s, beide gehen in 30 fps auf):
bei V = 4,4 stand der 18-px-Schritt 4 Takte (7,5 Bilder/s); jedes V von 5,2 bis 5,5 ergibt 2-2-3-2-3-2-3.
Der Takt ist bewusst ungleich: Ein fester Takt ließe die Figur bei 3 px und 18 px Vorschub gleich lange stehen.
Positionen sind ganze Pixel (Linien bleiben scharf); gerundet wird die laufende Summe, nicht jeder Schritt.
Ausgabe: assets/timeline.json (+ Kopie demo/art): je Takt {"f": Bildindex im Bogen, "x": linke Kante, "y": obere
Kante} in Plattenkoordinaten.
"""
import json, shutil

import inklib as K

FPS = 30
TICKS = 300          # 10 s, die Aufnahme nutzt 180
V = 5.3              # Spielpixel je Takt beim Laufen (Haltezeit = Vorschub / V; nur 2er- und 3er-Halte)
FEET_Y = 497         # Fußlinie in Plattenkoordinaten (Quellzeile ~802, vor den Fässern)
STOP_CX = 420        # Mitte der Figur beim Anhalten (rechts neben dem Laternenpfahl)
START_FRAME = "walk_3"
CYCLES = 5
MIN_HOLD = 2
STAND_TICKS = 9
BLINKS = [(156, 3), (171, 2)]   # (Takt, Dauer) in der Dreiviertelansicht


def main():
    meta = json.loads((K.SD / "assets/badger.json").read_text())
    ov = json.loads((K.SD / "assets/badger_override.json").read_text())
    names = meta["frames"]
    cyc = ov["cycle"]
    seq = cyc[cyc.index(START_FRAME):] + cyc * CYCLES
    steps = []                      # (Bildname, Takte, Vorschub danach in Spielpixeln)
    for n in seq:
        adv = ov["advance"][n]
        steps.append((n, max(MIN_HOLD, round(adv / V)), adv))
    assert all(t in (2, 3) for _, t, _ in steps), "Haltezeiten außerhalb 2/3 Takte: V anpassen"
    walk_dist = sum(a for _, _, a in steps[:-1])
    cx_in_frame = meta["frame_w"] / 2
    x_end = float(int(STOP_CX - cx_in_frame))      # ganze Pixel: alle Vorschübe sind ganzzahlig
    x = x_end - walk_dist
    y = FEET_Y - meta["foot"][1]
    tl = []
    for i, (n, ticks, adv) in enumerate(steps):
        for _ in range(ticks):
            tl.append({"f": names.index(n), "x": round(x), "y": round(y)})
        if i < len(steps) - 1:
            x += adv
    x += ov["stand_after_walk_6"]
    for _ in range(STAND_TICKS):
        tl.append({"f": names.index("stand"), "x": round(x), "y": round(y)})
    x += ov["turn_after_stand"]
    while len(tl) < TICKS:
        tl.append({"f": names.index("turn"), "x": round(x), "y": round(y)})
    for t0, d in BLINKS:
        for k in range(t0, t0 + d):
            if tl[k]["f"] == names.index("turn"):
                tl[k]["f"] = names.index("blink")
    walk_ticks = sum(t for _, t, _ in steps)
    info = {"fps": FPS, "frame_w": meta["frame_w"], "frame_h": meta["frame_h"], "frames": names,
            "walk_ticks": walk_ticks, "stand_tick": walk_ticks, "turn_tick": walk_ticks + STAND_TICKS,
            "feet_y": FEET_Y, "holds": [[n, t] for n, t, _ in steps[:8]], "timeline": tl}
    out = K.SD / "assets/timeline.json"
    out.write_text(json.dumps(info))
    shutil.copy(out, K.SD / "demo/art/timeline.json")
    print("walk", walk_ticks, "ticks =", round(walk_ticks / FPS, 2), "s; start x", tl[0]["x"], "stop x", tl[-1]["x"],
          "holds", [t for _, t, _ in steps[:8]])


if __name__ == "__main__":
    main()
