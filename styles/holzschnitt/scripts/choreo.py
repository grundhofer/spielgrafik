#!/usr/bin/env python3
"""Ablauf des Dachses für die 6-s-Demo: Bild und Lage je Takt (30 Takte/s).

    .venv/bin/python styles/holzschnitt/scripts/choreo.py

Vorschub je Bildwechsel aus dem Standfuß des KI-Laufbogens (KI-Pixel, Zellkoordinaten; Kopf steht in allen Zellen
gleich): Einzelstand-Wechsel (1->2, 2->3, 5->6, 6->7) über die Sohlen-Überdeckung der untersten 3-10 Zeilen
gemessen (15, 32, 25, 26), Doppelstand-Wechsel am Drehpunkt gelesen: Fußspitze des abrollenden bzw. Ferse des
aufsetzenden Fußes (0->1: 15, 3->4: 15, 4->5: 24, 7->0: 16). walk_1 -> stand: 31 (flacher Fuß auf flachen Fuß).
Der Vorschub fällt nur beim Bildwechsel an; die Haltezeit jedes Bildes ist proportional zum Vorschub davor
(2, 3 oder 4 Takte), damit der Rumpf gleichmäßig vorankommt. Lage = gerundete laufende Summe (ganze Pixel).
Ausgang: assets/timeline.json und demo/art/timeline.json
"""
import json, pathlib

ROOT = pathlib.Path(__file__).resolve().parents[1]
B = json.loads((ROOT / "assets/badger.json").read_text())
S = B["scale"]
NAMES = B["names"]
ADV = {("walk_0", "walk_1"): 15, ("walk_1", "walk_2"): 15, ("walk_2", "walk_3"): 32, ("walk_3", "walk_4"): 15,
       ("walk_4", "walk_5"): 24, ("walk_5", "walk_6"): 25, ("walk_6", "walk_7"): 26, ("walk_7", "walk_0"): 16,
       ("walk_1", "stand"): 31, ("stand", "turn"): 12, ("turn", "blink"): 0, ("blink", "turn"): 0}
PX_PER_TICK = 3.75           # Zieltempo des Rumpfs in Druckstock-Pixeln je Takt (≈ 112 px/s)

TICKS = 180
STOP = 126                   # ab hier steht er (4,2 s)
TURN = 144                   # dreht sich zur Kamera (4,8 s)
BLINK = (165, 169)           # blinzelt (5,5 s)
STAND_X = 404                # linke Bildkante des Standbilds im Druckstock (Körpermitte bei etwa x = 480)
FOOT_Y = 560                 # Sohlenlinie im Druckstock


def hold(adv_ai):
    return max(2, round(adv_ai * S / PX_PER_TICK))


def main():
    # Laufsequenz rückwärts vom Halt aufbauen: ... walk_0, walk_1 | stand
    cyc = [f"walk_{i}" for i in range(8)]
    seq = []                 # (name, Haltetakte), vorwärts
    t = STOP
    name = "walk_1"
    while t > 0:
        prev = cyc[(cyc.index(name) - 1) % 8]
        h = hold(ADV[(prev, name)])
        seq.insert(0, (name, h))
        t -= h
        name = prev
    # erstes Bild ggf. kürzen, damit der Halt genau auf STOP fällt
    over = -t
    seq[0] = (seq[0][0], seq[0][1] - over)
    seq += [("stand", TURN - STOP), ("turn", BLINK[0] - TURN), ("blink", BLINK[1] - BLINK[0]),
            ("turn", TICKS - BLINK[1] + 2)]
    # Lage: laufende Summe der Vorschübe, am Ende = STAND_X beim Standbild
    xs = [0.0]
    for (a, _), (b, _) in zip(seq, seq[1:]):
        xs.append(xs[-1] + ADV[(a, b)] * S)
    off = STAND_X - xs[[n for n, _ in seq].index("stand")]
    ticks = []
    for (n, h), x in zip(seq, xs):
        for _ in range(h):
            ticks.append({"f": NAMES.index(n), "x": int(round(x + off)), "y": FOOT_Y})
    ticks = ticks[:TICKS + 2]
    out = {"fps": 30, "sole_y": B["sole_y"], "frame_w": B["frame_w"], "frame_h": B["frame_h"],
           "frames": B["frames"], "seq": seq, "ticks": ticks}
    for d in (ROOT / "assets", ROOT / "demo/art"):
        (d / "timeline.json").write_text(json.dumps(out, indent=0))
    print("Sequenz:", " ".join(f"{n}:{h}" for n, h in seq))
    print("Start x", ticks[0]["x"], "Halt x", ticks[STOP]["x"], "Takte", len(ticks))


if __name__ == "__main__":
    main()
