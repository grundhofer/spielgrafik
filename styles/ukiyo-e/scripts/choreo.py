#!/usr/bin/env python3
"""Ablauf des Dachses für die 6-s-Demo: Einstellung, Bild und Lage je Takt (30 Takte/s).
Aufbau nach styles/holzschnitt/scripts/choreo.py; Vorschübe am eigenen KI-Laufbogen gemessen.

    .venv/bin/python styles/ukiyo-e/scripts/choreo.py

Zwei feste Einstellungen (scene.json "closeup"): Totale bis Takt 90 (3,0 s), dann Nahaufnahme (Druckausschnitt ab
view, 1,6-fach). In der Totale ist der Dachs 113 px hoch (Bogen badger.png, Faktor 0,26875) und passt damit zu Tür
(103 px, weiter hinten), Fässern (75 px) und Laterne; in der Nahaufnahme zeigt badger_close.png (Faktor 0,43,
181 px) den Druckstil der Figur. Beide Bögen kommen aus denselben KI-Zellen, die Lage wird in Druckkoordinaten
geführt und je Einstellung auf ganze Bildschirmpixel gerundet.

Vorschub je Bildwechsel aus dem Standfuß des KI-Laufbogens (KI-Pixel, Zellkoordinaten; die Nasenspitze steht in
allen Laufzellen auf ±3 KI-px gleich, x bleibt deshalb in Zellkoordinaten):
  Einzelstand-Wechsel 1->2, 2->3, 5->6, 6->7: Verschiebung, bei der sich die untersten 6 Sohlenzeilen beider
  Bilder am besten decken (19, 28, 27, 11).
  Doppelstand-Wechsel am Drehpunkt: Ferse des aufsetzenden Fußes 0->1: 190->169 = 21; 4->5: Fersenhinterkante
  zwei Zeilen über der Sohle 182->166 = 16, unterster Fersenpunkt 190->176 = 14, also 15 (die erste Fassung hatte
  hier 21; in der Aufnahme rückte die Ferse dabei 3-4 px vor);
  Spitze des abrollenden Fußes (3->4: 196->177 = 19, 7->0: 203->182 = 21).
  walk_1 -> stand: 18 (untere 12 Sohlenzeilen), stand -> turn: 0 (Drehung auf der Stelle, x bleibt).
Jedes Laufbild steht 3 Takte (10 Bilder/s, gleichmäßiger Takt); der Vorschub fällt nur beim Bildwechsel an, der
Rumpf kommt deshalb je Bild unterschiedlich weit (11-28 KI-px), die Füße stehen. Lage = laufende Summe.
Ausgang: assets/timeline.json und demo/art/timeline.json
"""
import json, pathlib

ROOT = pathlib.Path(__file__).resolve().parents[1]
B = json.loads((ROOT / "assets/badger.json").read_text())
SC = json.loads((ROOT / "assets/scene.json").read_text())
NAMES = B["names"]
ADV = {("walk_0", "walk_1"): 21, ("walk_1", "walk_2"): 19, ("walk_2", "walk_3"): 28, ("walk_3", "walk_4"): 19,
       ("walk_4", "walk_5"): 15, ("walk_5", "walk_6"): 27, ("walk_6", "walk_7"): 11, ("walk_7", "walk_0"): 21,
       ("walk_1", "stand"): 18, ("stand", "turn"): 0, ("turn", "blink"): 0, ("blink", "turn"): 0}
HOLD = 3                     # Takte je Laufbild (10 Bilder/s)
TICKS = 180
STOP = 114                   # ab hier steht er (3,8 s)
TURN = 138                   # dreht sich zur Kamera (4,6 s)
BLINK = (162, 166)           # blinzelt (5,4 s)
STAND_X = 170.0              # linke Kante des Standbilds in Druckkoordinaten (Körpermitte bei etwa x = 213)
FOOT_Y = 497.0               # Sohlenlinie in Druckkoordinaten (vordere Hälfte des Kaipflasters)
ORIGIN = SC["print_origin"]


def main():
    cu = SC["closeup"]
    cut, z, (vx, vy) = cu["from_tick"], cu["zoom"], cu["view"]
    cyc = [f"walk_{i}" for i in range(8)]
    assert STOP % HOLD == 0
    seq = []
    name = "walk_1"
    for _ in range(STOP // HOLD):
        seq.insert(0, (name, HOLD))
        name = cyc[(cyc.index(name) - 1) % 8]
    seq += [("stand", TURN - STOP), ("turn", BLINK[0] - TURN), ("blink", BLINK[1] - BLINK[0]),
            ("turn", TICKS - BLINK[1] + 2)]
    xs = [0.0]
    for (a, _), (b, _) in zip(seq, seq[1:]):
        xs.append(xs[-1] + ADV[(a, b)] * B["scale"])
    off = STAND_X - xs[[n for n, _ in seq].index("stand")]
    ticks = []
    for (n, h), x in zip(seq, xs):
        for _ in range(h):
            t = len(ticks)
            xp = x + off
            if t < cut:
                sx = round(ORIGIN[0] + xp)
                sy = round(ORIGIN[1] + FOOT_Y - B["sole_y"])
                shot = 0
            else:
                sx = round(ORIGIN[0] + z * (xp - vx))
                sy = round(ORIGIN[1] + z * (FOOT_Y - vy) - B["sole_y_close"])
                shot = 1
            ticks.append({"s": shot, "f": NAMES.index(n), "x": sx, "y": sy, "xp": round(xp, 2)})
    ticks = ticks[:TICKS + 2]
    out = {"fps": 30, "hold": HOLD, "cut": cut, "frames": B["frames"], "seq": seq, "ticks": ticks}
    for d in (ROOT / "assets", ROOT / "demo/art"):
        (d / "timeline.json").write_text(json.dumps(out, indent=0))
    print("Sequenz:", " ".join(f"{n}:{h}" for n, h in seq))
    print("Start x (Druck)", ticks[0]["xp"], "Schnitt bei Takt", cut, "x", ticks[cut]["xp"], "Halt x", ticks[STOP]["xp"],
          "Takte", len(ticks))


if __name__ == "__main__":
    main()
