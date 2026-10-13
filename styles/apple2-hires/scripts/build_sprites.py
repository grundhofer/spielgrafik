"""Dachs-Kurier als Hi-Res-Sprite (Bits und Farbgruppe je Zeile), Vorschau und Export für die Demo.

    .venv/bin/python styles/apple2-hires/scripts/build_sprites.py

Zeichen: "#" = Punkt gesetzt, "o" = Punkt aus (deckt den Hintergrund ab), "." = durchsichtig.
Jede Zeile beginnt mit ihrer Farbgruppe (0 = Violett/Grün, 1 = Blau/Orange); das Sprite setzt Bit 7 aller Bytes,
die es in dieser Zeile berührt (wie eine echte Sprite-Routine mit vorverschobenen Formen).
Farben entstehen aus der Spalte: Die Figur steht immer auf gerader Bildschirmspalte (Schritte von 2 Punkten),
damit gilt: gesetzter Einzelpunkt auf ungerader lokaler Spalte = Grün (Gruppe 0) bzw. Orange (Gruppe 1),
auf gerader = Violett bzw. Blau, zwei Nachbarn = Weiß, eine Lücke zwischen zwei gesetzten = Fläche.

Aufbau wie in klassischen Abenteuern: fester Oberkörper (Mütze, Gesicht von vorn, Schal, Weste, Paket) + Schalende in
zwei Stellungen (Wind) + Beine je Pose. Beine: nahes Bein weiß (2 Punkte), fernes violett (1 Punkt), mindestens
2 Punkte Abstand; Vorschub 2 Punkte je Pose -> der Standfuß bleibt über 3 Posen in der Welt stehen.
"""
import json, pathlib
import numpy as np
from PIL import Image
from a2lib import render

HERE = pathlib.Path(__file__).resolve().parent
ENTRY = HERE.parent
W = 20

# Zeichen in den Entwürfen: Farbbuchstaben, aus denen build_sprites.py die Bits nach Spalte setzt
# G grün / V violett (Gruppe 0), O orange / B blau (Gruppe 1), W weiß (alle gesetzt), K schwarz (deckend aus),
# . durchsichtig. Farbflächen werden auf ungeraden (G, O) bzw. geraden (V, B) lokalen Spalten gesetzt; die
# Lücken dazwischen füllt das Farbmodell. Zeilen ohne G/V/O/B bekommen Gruppe 1.
UPPER = [
    ".......GGGGG........",   # 0 Mützenkuppe
    ".....GGGGGGGGG......",   # 1 Mütze
    "....GGGGGGGGGGG.....",   # 2
    "....GGGGGGGGGGGGGGG.",   # 3 Schirm nach vorn
    ".WWWWWKKWWWKKWWWWW..",   # 4 Ohrspitzen seitlich unter dem Schirm (je 2 Punkte über die Wangen hinaus)
    "...WWWKKWWWKKWWW....",   # 5 Gesicht von vorn: weiße Wangen, schwarze Augenstreifen, weißer Mittelstreif
    "...WWWKKWWWKKWWW....",   # 6 (Weiß 3 Punkte breit, sonst nur Säume; Schwarz 2 Punkte, sonst gefüllt)
    "....WWWWWWWWWWW.....",   # 7 Schnauze
    "......WWWKKWWW......",   # 8 schwarzer Nasenpunkt am unteren Ende des Mittelstreifs
    None,                     # 9 Schal (TAIL)
    None,                     # 10
    None,                     # 11
    "...GGGGGGGGGG.......",   # 12 Weste, Schultern
    "..GGGGGGGGGGWW.WWWWW",   # 13 Weste, Ärmel, Paket
    "..GGGGGGGGGGWWWWWKWW",   # 14 Paket; die Schnur ist eine Lücke von 1 Punkt -> farbig
    "..GGGGGGGGGG..WWWKWW",   # 15
    "..GGGGGGGGGG..WWWKWW",   # 16
    "..GGGGGGGGGGG.WWWWWW",   # 17
    "...GGGGGGGGGG.......",   # 18 Weste unten
    "..OOOO.WWWWWWW......",   # 19 Tasche (orange) hinten, weißer Bauch
    "..OOOO..WWWWW.......",   # 20
]
TAIL = {
    "a": ["...OOOOOOOOOOO......", ".OOOOOOOOOOOOO......", "OOO..OOO............"],
    "b": [".OOOOOOOOOOOOO......", "...OOOOOOOOOOO......", "..OOOO.OOO.........."],
}
LEG_ROWS = 6
# Beine: nahes Bein weiß (2 Punkte), fernes Bein violett (1 Punkt), Ferse = linke Spalte.
# Zwei Punkte Abstand zwischen den Beinen, sonst füllt das Farbmodell die Lücke.
def legs(near, far, near_up=False, far_up=False):
    rows = []
    for r in range(LEG_ROWS):
        line = ["."] * W
        fr = r + (1 if far_up else 0)
        if fr < LEG_ROWS:
            line[far] = "V"
        nr = r + (1 if near_up else 0)
        if nr < LEG_ROWS:
            line[near] = "W"
            line[near + 1] = "W"
            if nr == LEG_ROWS - 1:
                line[near + 2] = "W"      # Zehen nach vorn
        rows.append("".join(line))
    return rows


POSES = {
    # (nahes Bein, fernes Bein, nahes angehoben, fernes angehoben); Vorschub 2 Punkte je Pose.
    # Standfuß in der Welt: nahes Bein 11 -> 9 -> 7 (walk1–3), fernes 12 -> 10 -> 8 (walk3, walk4, walk1).
    "stand": (13, 10, False, False),  # Schlussschritt nach walk4: fernes Bein bleibt, nahes setzt vorn auf
    "walk1": (11, 8, False, False),   # Kontakt: nahes Bein vorn
    "walk2": (9, 10, False, True),    # Durchgang: nahes Bein steht, fernes schwingt (angehoben)
    "walk3": (7, 12, False, False),   # Kontakt: fernes Bein vorn
    "walk4": (9, 10, True, False),    # Durchgang: fernes Bein steht, nahes schwingt
}


def frame(pose, tail):
    rows = []
    for i, r in enumerate(UPPER):
        rows.append(TAIL[tail][i - 9] if r is None else r)
    rows += legs(*POSES[pose])
    return rows


def parse(rows):
    """Entwurf in Farbbuchstaben -> bits (H, W) 0/1, opaque (H, W) bool, hib (H,) int"""
    H = len(rows)
    bits = np.zeros((H, W), np.uint8)
    opq = np.zeros((H, W), bool)
    hib = np.ones(H, np.int8)
    for y, r in enumerate(rows):
        s_ = r.ljust(W, ".")[:W]
        groups = {0 if c in "GV" else 1 for c in s_ if c in "GVOB"}
        if len(groups) > 1:
            raise SystemExit(f"Zeile {y}: Farben aus beiden Gruppen: {r}")
        if groups:
            hib[y] = groups.pop()
        for x, c in enumerate(s_):
            if c == ".":
                continue
            opq[y, x] = True
            if c == "W" or (c in "GO" and x % 2 == 1) or (c in "VB" and x % 2 == 0):
                bits[y, x] = 1
    return bits, opq, hib


def compose(mem, fr, x0, y0):
    """Sprite in Hi-Res-Speicher (rows, 40) schreiben, x0 gerade. Bytes mit deckenden Punkten bekommen Bit 7."""
    bits, opq, hib = fr
    H = bits.shape[0]
    for y in range(H):
        yy = y0 + y
        if not (0 <= yy < mem.shape[0]):
            continue
        touched = set()
        for x in range(W):
            if not opq[y, x]:
                continue
            xx = x0 + x
            if not (0 <= xx < 280):
                continue
            b, k = divmod(xx, 7)
            v = int(mem[yy, b])
            v = (v | (1 << k)) if bits[y, x] else (v & ~(1 << k))
            mem[yy, b] = v
            touched.add(b)
        for b in touched:
            mem[yy, b] = (int(mem[yy, b]) & 0x7F) | (int(hib[y]) << 7)
    return mem


def main():
    frames = {}
    for pose in POSES:
        for tail in TAIL:
            frames[f"{pose}_{tail}"] = parse(frame(pose, tail))
    # Vorschau: alle Bilder nebeneinander auf Schwarz und vor dem Kai der Demo
    names = list(frames)
    bg = np.load(ENTRY / "assets" / "picture_build.npz")["mem"]
    rows_out = []
    for back in ("black", "scene"):
        mem = np.zeros((30, 40), np.uint8) if back == "black" else bg[130:160].copy()
        for i, n in enumerate(names):
            compose(mem, frames[n], 2 + 26 * (i % 10), 1)
        rows_out.append(render(mem, "crisp"))
        rows_out.append(np.full((2, 280, 3), 60, np.uint8))
    img = np.vstack(rows_out)
    Image.fromarray(np.repeat(np.repeat(img, 4, 0), 4, 1)).save(ENTRY / "assets" / "sprites_preview.png")
    out = {"width": W, "height": len(frames[names[0]][0]), "frames": {}}
    for n, (bits, opq, hib) in frames.items():
        out["frames"][n] = {
            "rows": ["".join("#" if bits[y, x] else ("o" if opq[y, x] else ".") for x in range(W))
                     for y in range(bits.shape[0])],
            "hib": [int(h) for h in hib],
        }
    (ENTRY / "demo" / "data").mkdir(parents=True, exist_ok=True)
    (ENTRY / "demo" / "data" / "sprites.json").write_text(json.dumps(out))
    print(f"{len(frames)} Bilder, {out['width']}×{out['height']}")


if __name__ == "__main__":
    main()
