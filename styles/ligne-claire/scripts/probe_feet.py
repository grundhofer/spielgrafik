#!/usr/bin/env python3
"""Füße des Dachses in der Godot-Aufnahme messen (Differenzbild: Lauf mit Figur minus Lauf ohne Figur).

    .venv/bin/python styles/ligne-claire/scripts/probe_feet.py [--keep DIR]

Zwei Aufnahmen mit Movie Maker (30 fps, 6 s): "--probe-no-shadow" (Figur ohne Schatten) und "--probe-no-badger".
Alles andere läuft deterministisch gleich, die Differenz ist genau die Figur. Je Bild: unterste Zeile der Figur
(Fußlinie) und die Pixelläufe, mit denen sie den Boden berührt (unterste 3 Zeilen).

Prüfungen:
  * Laufen: Zwischen zwei aufeinanderfolgenden Laufbildern (15 fps) bleibt der Standfuß stehen: Streifenabgleich
    des Fußstreifens oder Kantenprüfung (Zehenspitze/Ferse in den untersten 4 Zeilen) ergibt höchstens 1 px
    (Begründung für die zwei Messungen unten im Code).
  * Stehen, Winken, Idle (während die Sprechblase steht): die Fußlinie ist in allen Bildern gleich.
    Beim Laufen und Drehen schwankt sie um 1-2 px, weil die Kamera 5° von oben schaut: der hintere Fuß steht im
    Bild höher als der vordere (Perspektive, kein Fehler).
"""
import argparse, pathlib, shutil, subprocess, sys, tempfile

import numpy as np
from PIL import Image

HERE = pathlib.Path(__file__).resolve().parent.parent
ap = argparse.ArgumentParser()
ap.add_argument("--keep", help="Einzelbilder hierhin schreiben statt in ein Temp-Verzeichnis")
a = ap.parse_args()

WALK_FRAMES, F_TURN, F_WAVE = 59, 59, 64


def record(flag, d):
    d.mkdir(parents=True, exist_ok=True)
    r = subprocess.run(["godot", "--path", str(HERE / "demo"), "--position", "20000,20000", "--resolution", "1280x720",
                        "--write-movie", str(d / "f.png"), "--fixed-fps", "30", "--quit-after", "180", "--", flag],
                       capture_output=True, text=True, timeout=600)
    bad = [l for l in (r.stdout + r.stderr).splitlines() if "ERROR" in l]
    if bad:
        sys.exit("Godot-Fehler: " + bad[0])
    return sorted(d.glob("f*.png"))


td = tempfile.mkdtemp()
base = pathlib.Path(a.keep) if a.keep else pathlib.Path(td)
with_b = record("--probe-no-shadow", base / "with")
without = record("--probe-no-badger", base / "without")
n = min(len(with_b), len(without))
rows = []
for i in range(n):
    A = np.asarray(Image.open(with_b[i]).convert("RGB"), np.int16)
    B = np.asarray(Image.open(without[i]).convert("RGB"), np.int16)
    m = np.abs(A - B).max(2) > 40
    m[:400] = False                     # nur der Kai (Einschub und Himmel oben ignorieren)
    ys, xs = np.nonzero(m)
    if len(ys) == 0:
        rows.append(None)
        continue
    yb = ys.max()
    runs = []
    cols = np.nonzero(m[yb - 2:yb + 1].any(0))[0]
    if len(cols):
        start = prev = cols[0]
        for c in cols[1:]:
            if c > prev + 2:
                runs.append((int(start), int(prev)))
                start = c
            prev = c
        runs.append((int(start), int(prev)))
    rows.append({"yb": int(yb), "runs": runs, "top": int(ys.min()), "x0": int(xs.min()), "x1": int(xs.max())})


print("Bild  Spr  Fußlinie  Kopf  Bodenkontakt (x von-bis)")
for i in range(0, n, 2):
    r = rows[i]
    if r:
        print(f"{i:4d} {i // 2:4d} {r['yb']:6d} {r['top']:6d}   {r['runs']}")

# Laufen: Standfuß zwischen aufeinanderfolgenden Sprite-Bildern. Im Fußstreifen (unterste 8 Zeilen der Figur) wird
# gezählt, wie viele Figurpixel bei einer waagerechten Verschiebung s im nächsten Bild farbgleich wieder auftauchen.
# Ein stehender Fuß ergibt eine Spitze bei s = 0 (±1 bei Rundung), der Schwungfuß eine zweite bei großem s.
# Gemessen wird die Spitze mit dem kleinsten |s| unter den Spitzen mit mindestens 40 % der höchsten Zahl.
def band(i):
    A = np.asarray(Image.open(with_b[i]).convert("RGB"), np.int16)
    B = np.asarray(Image.open(without[i]).convert("RGB"), np.int16)
    m = np.abs(A - B).max(2) > 40
    m[:400] = False
    yb = rows[i]["yb"]
    return A[yb - 7:yb + 1], m[yb - 7:yb + 1]


worst, pairs = 0, 0
slides = []
for k in range(0, WALK_FRAMES - 1):
    A0, m0 = band(2 * k)
    A1, m1 = band(2 * k + 2)
    if A0.shape != A1.shape:
        h = min(len(A0), len(A1))
        A0, m0, A1, m1 = A0[-h:], m0[-h:], A1[-h:], m1[-h:]
    counts = {}
    for sft in range(-14, 15):
        sa = slice(max(0, -sft), A0.shape[1] - max(0, sft))
        sb = slice(max(0, sft), A1.shape[1] - max(0, -sft))
        same = m0[:, sa] & m1[:, sb] & (np.abs(A0[:, sa] - A1[:, sb]).max(2) < 30)
        counts[sft] = int(same.sum())
    top = max(counts.values())
    peaks = [sft for sft, c in counts.items() if c >= 0.4 * top and c >= counts.get(sft - 1, 0) and c >= counts.get(sft + 1, 0)]
    s0 = min(peaks, key=abs)
    pairs += 1
    worst = max(worst, abs(s0))
    slides.append(s0)
print("Verschiebung des Standfußes je Laufbild:", " ".join(f"{x:+d}" for x in slides))
# Zyklusbild 0->1 und 4->5 sind Kontaktwechsel (ein Fuß hebt ab, der andere setzt auf): dort gibt es keinen Fuß, der
# in beiden Bildern steht, die Messung trifft dann den Körper (+5 = Vorschub). Bewertet werden die Standphasen.
# Die ersten beiden Laufbilder stehen teilweise hinter dem linken Panelrand und zählen nicht.
stance = [(k, x) for k, x in enumerate(slides) if k >= 2 and k % 8 not in (0, 4)]
exch = [(k, x) for k, x in enumerate(slides) if k >= 2 and k % 8 in (0, 4)]
print(f"Streifenabgleich in den Standphasen: größte Verschiebung {max(abs(x) for _, x in stance)} px")


# Zweite Messung, Kantenprüfung: In den untersten 4 Bildzeilen (gleiche Bildschirmzeilen in beiden Bildern) die
# linken und rechten Enden der Bodenläufe vergleichen; steht ein Fuß, bleibt mindestens ein Ende (Zehenspitze oder
# Ferse) auf 1 px gleich, alles, was mit dem Körper mitgeht, wandert 5 px.
# Beide Messungen haben blinde Flecken: Hebt sich die Ferse des Standfußes (Zyklusbild 7->0), ändert sich die Form des
# Fußstreifens, und der Streifenabgleich meldet bis zu 2 px, obwohl die Zehenspitze steht (seit der Glättung des
# Modells per Subdivision). Setzt der andere Fuß direkt davor auf (3->4), verschmelzen beide Füße zu einem Lauf, und
# die Kantenprüfung findet kein freies Ende. Ein Bildpaar gilt als stehend, wenn eine der beiden Messungen höchstens
# 1 px ergibt; ausgegeben wird je Paar der kleinere Wert.
def edges(i, y0, y1):
    A = np.asarray(Image.open(with_b[i]).convert("RGB"), np.int16)
    B = np.asarray(Image.open(without[i]).convert("RGB"), np.int16)
    m = np.abs(A - B).max(2) > 40
    out = {}
    for y in range(y0, y1 + 1):
        cols = np.flatnonzero(m[y])
        L, R = [], []
        if len(cols):
            s_ = p_ = cols[0]
            for c in cols[1:]:
                if c > p_ + 2:
                    L.append(int(s_)); R.append(int(p_)); s_ = c
                p_ = c
            L.append(int(s_)); R.append(int(p_))
        out[y] = (L, R)
    return out


comb = []
for k, x in stance:
    Y = max(rows[2 * k]["yb"], rows[2 * k + 2]["yb"])
    e0, e1 = edges(2 * k, Y - 3, Y), edges(2 * k + 2, Y - 3, Y)
    best = 99
    for y in e0:
        for side in (0, 1):
            for u in e0[y][side]:
                for v in e1[y][side]:
                    best = min(best, abs(u - v))
    d = min(abs(x), best)
    comb.append((k, d))
    if d > 1:
        print(f"  Standfuß rutscht: Sprite {k}->{k + 1} (Zyklusbild {k % 8}->{(k + 1) % 8}): Streifen {x:+d} px, "
              f"Fußende {best} px")
worst = max(d for _, d in comb)
print(f"Standphasen: {len(comb)} Bildpaare, Standfuß bewegt sich höchstens {worst} px (je Paar der kleinere Wert aus "
      f"Streifenabgleich und Kantenprüfung: " + " ".join(f"{d}" for _, d in comb) + "); Kontaktwechsel (nicht "
      "bewertet, Streifenabgleich): " + " ".join(f"{x:+d}" for _, x in exch))
# Halbbilder: innerhalb eines Sprite-Bildes darf sich nichts bewegen
jit = max(abs(rows[2 * k]["x0"] - rows[2 * k + 1]["x0"]) for k in range(WALK_FRAMES) if rows[2 * k] and rows[2 * k + 1])
stand = [rows[i]["yb"] for i in range(2 * F_WAVE, n) if rows[i]]
turn = [rows[i]["yb"] for i in range(2 * F_TURN, 2 * F_WAVE) if rows[i]]
walk_yb = [rows[i]["yb"] for i in range(0, 2 * WALK_FRAMES) if rows[i]]
print(f"Laufen: Versatz innerhalb eines Sprite-Bildes {jit} px")
print(f"Fußlinie beim Laufen {min(walk_yb)}..{max(walk_yb)}, beim Drehen {min(turn)}..{max(turn)}, "
      f"beim Stehen/Winken/Sprechen {min(stand)}..{max(stand)}")
ok = worst <= 1 and jit == 0 and max(stand) - min(stand) == 0
print("ok" if ok else "PROBLEM")
if a.keep:
    # Kontaktbogen der Füße (Sprite-Bilder 40-55, 4-fach vergrößert) zum Ansehen
    tiles = []
    for k in range(40, 56):
        yb = rows[2 * k]["yb"]
        im = Image.open(with_b[2 * k]).convert("RGB").crop((200, yb - 56, 380, yb + 8))
        tiles.append(im.resize((im.width * 2, im.height * 2), Image.NEAREST))
    sheet = Image.new("RGB", (tiles[0].width * 4, tiles[0].height * 4), "white")
    for j, tl in enumerate(tiles):
        sheet.paste(tl, ((j % 4) * tl.width, (j // 4) * tl.height))
    sheet.save(pathlib.Path(a.keep) / "feet_sheet.png")
shutil.rmtree(td, ignore_errors=True)
