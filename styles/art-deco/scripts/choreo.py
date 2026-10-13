#!/usr/bin/env python3
"""Ablauf des Dachses und der zwei Einstellungen für die 6-s-Demo (30 Takte/s).
Aufbau nach styles/ukiyo-e/scripts/choreo.py (Vorschub nur beim Bildwechsel, Lage als laufende Summe).

    .venv/bin/python styles/art-deco/scripts/choreo.py

Weltkoordinaten = Pixel des Plakatbildes (1536x1024). Zwei feste Einstellungen:
  Totale      Takt 0-89:   ganzes Plakat in voller Breite, Faktor 1280/1536, Ausschnitt ab Weltzeile 56
  Nahaufnahme ab Takt 90:  Faktor 1,35 (1,62-fache Totale), Ausschnitt ab Welt (20, 339); Sonne ganz im Bild
Die Figur hat je Einstellung ein eigenes Bild in Zielgröße (badger_far, badger_close); die Lage wird in Welt-
koordinaten geführt und je Einstellung auf ganze Bildschirmpixel gerundet.

Vorschub je Bildwechsel in KI-Pixeln, gemessen am eigenen Bogen (scripts/measure_stride.py, Kontaktspannen der
untersten 2-4 Sohlenzeilen; die KI hat die Figuren in den Zellen unterschiedlich weit vorn gezeichnet, deshalb
schwanken die Werte stark):
  0->1  Doppelstand -> Stand auf L: Ferse des aufsetzenden Fußes 183 -> 181, Spitze des hinteren 177 -> 176: 2
  1->2  Stand L: Ferse 181 -> 159 (22), Mitte 210 -> 196 (14): 17
  2->3  Stand L: Ferse 158 -> 136 (22), Spitze 235 -> 209 (26): 24
  3->4  L rollt ab (Drehpunkt Spitze): 209 -> 184 (k=4) bzw. 205 -> 179 (k=2): 25
  4->5  R setzt auf (Drehpunkt Ferse): 187 -> 161 bzw. 188 -> 163: 25
  5->6  Stand R: Ferse 161 -> 148 (13), Spitze 239 -> 231 (8): 11
  6->7  Stand R: Ferse 148 -> 137 (11), Spitze 231 -> 218 (13): 12
  7->0  R rollt ab (Drehpunkt Spitze): 218 -> 177 bzw. 216 -> 175: 41
  Summe 157 KI-px je Doppelschritt (44 Weltpixel).
  walk_7 -> stand: Standfuß R bleibt, Ferse 137 -> 142: -5;  stand -> turn: Körpermitte 175,1 -> 173,6: +2.
Die Werte wurden mit dem Prüflauf (scripts/probe_feet.py) nachgemessen, siehe style.json.
Ausgang: assets/timeline.json und demo/art/timeline.json
"""
import json, pathlib

ROOT = pathlib.Path(__file__).resolve().parents[1]
B = json.loads((ROOT / "assets/badger.json").read_text())
NAMES = B["names"]
ADV = {("walk_0", "walk_1"): 2, ("walk_1", "walk_2"): 17, ("walk_2", "walk_3"): 24, ("walk_3", "walk_4"): 25,
       ("walk_4", "walk_5"): 25, ("walk_5", "walk_6"): 11, ("walk_6", "walk_7"): 12, ("walk_7", "walk_0"): 41,
       ("walk_7", "stand"): -5, ("stand", "turn"): 2, ("turn", "blink"): 0, ("blink", "turn"): 0}
HOLD = 2                     # Takte je Laufbild (15 Bilder/s)
TICKS = 180
CUT = 90                     # Schnitt auf die Nahaufnahme (3,0 s)
STOP = 114                   # ab hier steht er (3,8 s), letztes Laufbild walk_7
TURN = 132                   # dreht sich zur Kamera (4,4 s)
BLINK = (156, 160)           # blinzelt (5,2 s)
STAND_CX = 340.0             # Körpermitte im Stand (Welt-x)
FOOT_Y = 798.0               # Sohlenlinie (Welt-y), vordere Plattenreihe des Kais
SHOTS = [{"zoom": 1280 / 1536, "origin": [0.0, 56.0], "sheet": "far"},
         {"zoom": 1.35, "origin": [20.0, 339.0], "sheet": "close"}]


def main():
    cyc = [f"walk_{i}" for i in range(8)]
    assert STOP % HOLD == 0
    seq = []
    name = "walk_7"
    for _ in range(STOP // HOLD):
        seq.insert(0, (name, HOLD))
        name = cyc[(cyc.index(name) - 1) % 8]
    seq += [("stand", TURN - STOP), ("turn", BLINK[0] - TURN), ("blink", BLINK[1] - BLINK[0]),
            ("turn", TICKS - BLINK[1] + 2)]
    sc = B["scale_world"]
    xs = [0.0]
    for (a, _), (b, _) in zip(seq, seq[1:]):
        xs.append(xs[-1] + ADV[(a, b)] * sc)
    i_stand = [n for n, _ in seq].index("stand")
    stand_cx = B["measure"][NAMES.index("stand")]["cx_ai"] * sc
    off = STAND_CX - stand_cx - xs[i_stand]
    ticks = []
    for (n, h), x in zip(seq, xs):
        for _ in range(h):
            t = len(ticks)
            shot = 0 if t < CUT else 1
            S = SHOTS[shot]
            z, (ox, oy) = S["zoom"], S["origin"]
            key = "_" + S["sheet"]
            wx = x + off                                   # linke Rahmenkante in Welt-x
            sx = round((wx - ox) * z)
            sy = round((FOOT_Y - oy) * z - B["sole_y" + key])
            ticks.append({"s": shot, "f": NAMES.index(n), "x": sx, "y": sy, "wx": round(wx, 2)})
    ticks = ticks[:TICKS + 2]
    out = {"fps": 30, "hold": HOLD, "cut": CUT, "frames": B["frames"], "shots": SHOTS, "foot_y": FOOT_Y,
           "seq": seq, "ticks": ticks}
    for d in (ROOT / "assets", ROOT / "demo/art"):
        (d / "timeline.json").write_text(json.dumps(out, indent=0))
    print("Sequenz:", " ".join(f"{n}:{h}" for n, h in seq))
    cx0 = ticks[0]["wx"] + stand_cx
    print("Start Körpermitte (Welt)", round(cx0, 1), " Schnitt bei Takt", CUT, "Welt-x", ticks[CUT]["wx"],
          " Halt Welt-x", ticks[STOP]["wx"], " Takte", len(ticks))


if __name__ == "__main__":
    main()
