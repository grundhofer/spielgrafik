#!/usr/bin/env python3
"""Ablauf des Dachses in den zwei Einstellungen der 6-s-Demo (30 Takte/s).
Aufbau nach styles/art-deco/scripts/choreo.py (Vorschub nur beim Bildwechsel, Lage als laufende Summe).

    .venv/bin/python styles/jugendstil/scripts/choreo.py

Weltkoordinaten = Pixel von bg.png. Einstellungen aus assets/layout.json: Totale (Takt 0-89), Nahaufnahme ab
Takt CUT. Die Figur hat je Einstellung ein eigenes Bild in Zielgröße (badger_far, badger_close); die Lage wird
in Weltkoordinaten geführt und je Einstellung auf ganze Bildschirmpixel gerundet.

Vorschub je Bildwechsel in KI-Pixeln, abgelesen an den Kontaktspannen (scripts/measure_stride.py, k = 0-20
unterste Sohlenzeilen) am Drehpunkt des Standfußes:
  0->1  Ferse des aufsetzenden Fußes 191 -> 167 (k=2), Spitze 272 -> 250: 23
  1->2  Stand: Ferse 165 -> 143 (k=4), Spitze 245 -> 226: 21
  2->3  Stand: Ferse 137 -> 116 (k=20), Spitze 228 -> 204: 22
  3->4  Fuß rollt ab (Drehpunkt Spitze): 202 -> 171 (k=4): 31
  4->5  anderer Fuß setzt auf (Drehpunkt Ferse): 174 -> 159 (k=4): 15
  5->6  Stand: Ferse 159 -> 145 (k=4), Spitze 243 -> 227: 15
  6->7  Stand: Ferse 140 -> 117 (k=20), Spitze 230 -> 205: 24
  7->0  Fuß rollt ab (Drehpunkt Spitze): 203 -> 186 (k=4): 18
  Summe 169 KI-px je Doppelschritt (74 Weltpixel). Die KI hat walk_4 etwa 8 px weiter hinten in die Zelle
  gezeichnet (Nase 278 statt 286-292), deshalb der große Wert bei 3->4 und der kleine bei 4->5.
  walk_6 -> stand: Standfuß bleibt, Ferse 140 -> 128 (k=20): +12;  stand -> turn: Körpermitte 162,9 -> 154,7: +8.
  Der Kopf rückt trotz der ungleichen Vorschübe gleichmäßig vor (21-22 KI-px je Wechsel), weil build_badger.py
  den Oberkörper jedes Laufbilds passend schert (HEAD_SHIFT); Füße und damit die Vorschübe ändert das nicht.
  walk_4 in der Zelle nach vorn zu schieben (Vorschläge 23/23 statt 31/15) ändert dagegen nichts im Bild: Bei
  festem Standfuß landet das Bild an derselben Stelle.
Idle nach der Drehung: Atmen aus drei Stufen der Drehpose (turn, turn_b1, turn_b2; Oberkörper 0/2/4 KI-px
gestreckt) im Takt BREATH_SEQ, Blinzeln in der jeweiligen Stufe (blink, blink_b1, blink_b2).
Die Werte werden mit dem Prüflauf (scripts/probe_feet.py) nachgemessen.
Ausgang: assets/timeline.json und demo/art/timeline.json
"""
import json, pathlib

ROOT = pathlib.Path(__file__).resolve().parents[1]
B = json.loads((ROOT / "assets/badger.json").read_text())
L = json.loads((ROOT / "assets/layout.json").read_text())
NAMES = B["names"]
ADV = {("walk_0", "walk_1"): 23, ("walk_1", "walk_2"): 21, ("walk_2", "walk_3"): 22, ("walk_3", "walk_4"): 31,
       ("walk_4", "walk_5"): 15, ("walk_5", "walk_6"): 15, ("walk_6", "walk_7"): 24, ("walk_7", "walk_0"): 18,
       ("walk_6", "stand"): 12, ("stand", "turn"): 8}
IDLE = ("turn", "blink")         # Drehpose, Atemstufen und Blinzeln stehen am selben Ort
HOLD = 2                     # Takte je Laufbild (15 Bilder/s)
TICKS = 180
CUT = 90                     # Schnitt auf die Nahaufnahme (3,0 s)
STOP = 116                   # ab hier steht er (3,87 s), letztes Laufbild walk_6
TURN = 134                   # dreht sich zur Kamera (4,47 s)
BLINK = (158, 162)           # blinzelt (5,27 s)
BREATH_SEQ = [("", 12), ("_b1", 6), ("_b2", 12), ("_b1", 6)]   # Atemzug 1,2 s ab TURN
STAND_CX = 470.0             # Körpermitte im Stand (Welt-x), links der Laterne


def main():
    cyc = [f"walk_{i}" for i in range(8)]
    assert STOP % HOLD == 0
    seq = []
    name = "walk_6"
    for _ in range(STOP // HOLD):
        seq.insert(0, (name, HOLD))
        name = cyc[(cyc.index(name) - 1) % 8]
    seq += [("stand", TURN - STOP)]
    pat = [suf for suf, n in BREATH_SEQ for _ in range(n)]
    for t in range(TURN, TICKS + 2):
        n = ("blink" if BLINK[0] <= t < BLINK[1] else "turn") + pat[(t - TURN) % len(pat)]
        if seq[-1][0] == n:
            seq[-1] = (n, seq[-1][1] + 1)
        else:
            seq.append((n, 1))
    sc = B["scale_world"]
    xs = [0.0]
    for (a, _), (b, _) in zip(seq, seq[1:]):
        idle = a.startswith(IDLE) and b.startswith(IDLE)
        xs.append(xs[-1] + (0 if idle else ADV[(a, b)]) * sc)
    i_stand = [n for n, _ in seq].index("stand")
    stand_cx = B["measure"][NAMES.index("stand")]["cx_ai"] * sc
    off = STAND_CX - stand_cx - xs[i_stand]
    foot_y = L["foot_y"]
    shots = L["shots"]
    keys = ["far", "close"]
    ticks = []
    for (n, h), x in zip(seq, xs):
        for _ in range(h):
            t = len(ticks)
            shot = 0 if t < CUT else 1
            S = shots[shot]
            z, (px, py) = S["zoom"], S["pos"]
            k = keys[shot]
            wx = x + off                                   # linke Rahmenkante in Welt-x
            sx = round(px + wx * z)
            sy = round(py + foot_y * z - B["sole_y_" + k])
            ticks.append({"s": shot, "f": NAMES.index(n), "x": sx, "y": sy, "wx": round(wx, 2)})
    ticks = ticks[:TICKS + 2]
    out = {"fps": 30, "hold": HOLD, "cut": CUT, "frames": B["frames"], "shots": shots, "foot_y": foot_y,
           "seq": seq, "ticks": ticks}
    for d in (ROOT / "assets", ROOT / "demo/art"):
        (d / "timeline.json").write_text(json.dumps(out, indent=0))
    print("Sequenz:", " ".join(f"{n}:{h}" for n, h in seq))
    cx0 = ticks[0]["wx"] + stand_cx
    print("Start Körpermitte (Welt)", round(cx0, 1), " Schnitt bei Takt", CUT, "Welt-x", ticks[CUT]["wx"],
          " Halt Welt-x", ticks[STOP]["wx"], " Takte", len(ticks))


if __name__ == "__main__":
    main()
