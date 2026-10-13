#!/usr/bin/env python3
"""Vergleichstafel assets/compare_badger.png aus den Ansichten von blender/compare_views.py.

Zeilen: TripoSR roh (Eckpunktfarben) | gesäubert, nur Eckpunktfarben gebacken | gesäubert, Vorderansicht
projiziert (in der Demo) | Versuch mit Dreiviertel-Bild als Eingabe. Spalten: KI-Bild, vorn, rechts, hinten.
Mit --props stattdessen die drei Requisiten (Fass, Laterne, Boot) in der Fassung der Demo.

    .venv/bin/python styles/ki-3d-modell/scripts/compose_compare.py <ansichten-ordner> <ausgabe.png> [--props]
"""
import json, sys, pathlib
from PIL import Image, ImageDraw, ImageFont

E = pathlib.Path(__file__).resolve().parent.parent
src, out = pathlib.Path(sys.argv[1]), sys.argv[2]
S, LW, TOP = 300, 300, 46
font = ImageFont.truetype(str(E / "demo/fonts/SourceSans3.ttf"), 20)
small = ImageFont.truetype(str(E / "demo/fonts/SourceSans3.ttf"), 16)
raw_n = json.load(open(E / "work/tsr/badger_front/tsr.json"))["faces"]
rows = [
    ("raw", f"TripoSR roh: {raw_n:,} Dreiecke,".replace(",", " ") + "\nEckpunktfarben, nichts gesäubert", "badger_front"),
    ("vc", "Gesäubert: 8 000 Dreiecke,\nnur Eckpunktfarben gebacken", "badger_front"),
    ("proj", "Gesäubert + Vorderansicht\nprojiziert (in der Demo)", "badger_front"),
    ("q34", "Versuch: Dreiviertel-Bild als\nEingabe (Schnauze, aber Rücken\nund Gesicht schlechter)", "badger_34"),
]
def de(x):
    """Zahl in deutscher Schreibweise: 4 000, 30,5"""
    return f"{x:,}".replace(",", " ") if isinstance(x, int) else f"{x:g}".replace(".", ",")


if "--props" in sys.argv:
    rep = {n: json.load(open(E / f"assets/models/{n}.json")) for n in ("barrel", "lantern", "boat")}
    rows = [
        ("barrel", f"Fass: {de(rep['barrel']['tris'])} Dreiecke,\naufgerichtet um {de(abs(rep['barrel']['tilt_deg']))}°", "barrel"),
        ("lantern", f"Laterne: {de(rep['lantern']['tris'])} Dreiecke,\nKette zerfallen: Laterne\nverschoben, Stab ergänzt", "lantern"),
        ("boat", f"Boot: {de(rep['boat']['tris'])} Dreiecke,\naufgerichtet um {de(abs(rep['boat']['tilt_deg']))}°,\nlange Achse nach x", "boat"),
    ]
cols = ["", "KI-Bild", "vorn", "rechts", "hinten"]
W = LW + 4 * S
img = Image.new("RGB", (W, TOP + len(rows) * S), (38, 40, 46))
d = ImageDraw.Draw(img)
for i, c in enumerate(cols[1:]):
    d.text((LW + i * S + 10, 12), c, font=font, fill=(235, 232, 225))
for r, (key, label, inp) in enumerate(rows):
    y = TOP + r * S
    d.multiline_text((14, y + 20), label, font=small, fill=(235, 232, 225), spacing=4)
    im = Image.open(E / f"assets/raw/{inp}.png").convert("RGBA")
    bb = im.getchannel("A").point(lambda a: 255 if a > 127 else 0).getbbox()
    im = im.crop(bb)
    im.thumbnail((S - 30, S - 30), Image.LANCZOS)
    tile = Image.new("RGB", (S, S), (92, 92, 92))
    tile.paste(im, ((S - im.width) // 2, (S - im.height) // 2), im)
    img.paste(tile, (LW, y))
    for i, v in enumerate(("front", "right", "back")):
        img.paste(Image.open(src / f"{key}_{v}.png").convert("RGB").resize((S, S), Image.LANCZOS), (LW + (i + 1) * S, y))
img.save(out)
print(out, img.size)
