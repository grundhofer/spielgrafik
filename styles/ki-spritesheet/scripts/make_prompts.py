#!/usr/bin/env python3
"""Baut die Bild-Prompts für ki-spritesheet: Stilblock + Motivblock (wörtlich aus data/motif.json) + Schutzregeln.

    .venv/bin/python styles/ki-spritesheet/scripts/make_prompts.py

Schreibt assets/prompts/*.txt und assets/jobs_*.json (Format von genimg.py --jobs).
Der Weg dieses Eintrags: Nur das Referenzblatt (shared/badger/master_sheet.png) gibt Kostüm, Proportionen und
Zeichenstil vor, keine Posenvorlage (die zeigt rotoskopie). Das erste gelungene Blatt (Laufen) geht als zweite
Referenz in alle weiteren Blätter, damit Strich und Maßstab gleich bleiben.
"""
import json, pathlib

ROOT = pathlib.Path(__file__).resolve().parents[3]
ENTRY = pathlib.Path(__file__).resolve().parents[1]
REL = "styles/ki-spritesheet"
OUT = ENTRY / "assets" / "prompts"
m = json.loads((ROOT / "data" / "motif.json").read_text())
scene, char, guards = m["scene"]["block_en"], m["character"]["block_en"], m["guards_en"]
FMT = "Image format: landscape 3:2."

BG_STYLE = (
    "Style: 2D background art for a modern hand-drawn point-and-click adventure game whose characters are "
    "cartoon sprites with clean outlines. Clean, confident dark brown outlines of even weight around every "
    "shape, flat colour fills with one or two soft cel-shading steps, only a subtle painted texture inside large "
    "areas, simple rounded readable shapes, moderate detail, calm planes. Palette at dusk: deep blue-violet sky "
    "turning into a band of warm orange at the horizon, teal-blue sea, cool slate and violet shadows; warm amber "
    "only for the lit window, the lantern and the lighthouse lamp. Mid values overall, so that a character drawn "
    "in front stays readable. Not a photograph, not a 3D render, not a postcard, not pixel art, no heavy brush "
    "texture."
)

BG_COMPOSITION = (
    "Composition: side view from the eye level of a small character standing on the quay, close to the quay. "
    "Flat sea horizon at about 47 % of the image height. The stone quay is a wide, flat, walkable pavement that "
    "fills the lower 32 % of the image across the full width, with large calm paving stones; the middle of the "
    "quay from 8 % to 72 % of the image width stays completely empty as a walking path. The cottage stands set "
    "back on the quay at the left edge, filling the left 20 % of the width, the lit window facing the viewer, the "
    "chimney against open sky. The iron lantern on its wooden post stands on the quay at about 74 % of the width, "
    "its lantern against the sea and the sky. Barrels, the crate stack and the rope coil stand together at the "
    "right edge of the quay, from 80 % to 100 % of the width. Behind the quay, between 25 % and 60 % of the "
    "width, the short wooden jetty reaches into the water with the two boats moored at it. The rocky headland "
    "rises from the sea on the right; the lighthouse stands on it at about 88 % of the width, its top at about "
    "15 % of the image height. The upper middle of the image is open sky with a few low clouds. Keep a margin of "
    "plain sky above the lighthouse and the chimney and plain pavement at the bottom edge (the image will be "
    "cropped to 16:9). The lighthouse lamp is only a small glowing spot without any beam, there is no smoke from "
    "the chimney, no glow halo around the lantern and no birds: beam, smoke, glow and birds are animated "
    "separately in the game."
)

SPRITE_STYLE = (
    "Sprite sheet for a 2D adventure game. The character is the badger courier from the first reference image, "
    "a character sheet: keep exactly his costume, colours, body proportions and drawing style (clean dark "
    "outlines, flat colour fills with soft cel shading, hand-painted cartoon look); ignore its layout with three "
    "views and its magenta background. Neutral even light from the front-top, no rim light, no cast shadow, no "
    "ground. Not a 3D render, not plush, not a photograph."
)
SAME_AS_WALK = (
    " The second reference image is his walk cycle from the same game: draw him at exactly the same scale, with "
    "the same line weight, the same colours and the same level of detail as there."
)
SHEET_RULES = (
    "Every frame is a complete, separate drawing of the whole character at the same scale; clear empty space "
    "between neighbouring frames, nothing touching or overlapping, no frame borders, no numbers, no labels, no "
    "ground line. Isolated on a fully transparent background."
)

WALK = (
    "Layout: one single horizontal row of 8 animation frames of one walk cycle, evenly spaced across the full "
    "width, the badger seen exactly from the side, facing right, in every frame, the soles of the feet on the "
    "same baseline. The 8 phases in order from left to right: 1 contact – near leg stretched forward with the "
    "heel touching down, far leg stretched back on its toes; 2 down – weight on the near leg, knees bent, body at "
    "its lowest; 3 passing – the far leg swings forward past the standing near leg; 4 up – body at its highest, "
    "pushing off from the near toes; 5 contact – far leg stretched forward with the heel touching down, near leg "
    "stretched back; 6 down – weight on the far leg; 7 passing – the near leg swings forward past the standing "
    "far leg; 8 up. Every frame is a different pose, no two frames are the same. In every frame the parcel stays "
    "tucked under the near arm, the free far arm swings opposite to the legs, the scarf ends trail behind him."
)

IDLE = (
    "Layout: one single horizontal row of 6 animation frames of a standing idle loop, evenly spaced across the "
    "full width, the badger seen exactly from the side, facing right, as in his walk cycle. Both feet stay "
    "planted flat on the same baseline in every frame, the near foot slightly in front. The 6 phases in order "
    "from left to right: 1 relaxed standing pose; 2 breathing in, chest and shoulders rise slightly; 3 fully "
    "breathed in; 4 the same as 3 but with both eyes closed (blink); 5 breathing out; 6 relaxed standing pose "
    "again. Only small changes between frames; the parcel stays under the near arm, the far arm hangs relaxed, "
    "the scarf ends hang down his back."
)

JUMP = (
    "Layout: one single horizontal row of 6 animation frames of a small happy hop on the spot, evenly spaced "
    "across the full width, the badger seen exactly from the side, facing right, as in his walk cycle. The 6 "
    "phases in order from left to right: 1 anticipation – crouching, knees bent, body squashed down; 2 take-off "
    "– legs stretching, toes pushing off, body stretched upwards; 3 rising – legs tucked up under the body; 4 "
    "top of the hop – body stretched, the scarf ends floating up; 5 falling – legs reaching down for the "
    "ground; 6 landing – crouched again, knees bent, body squashed. Draw every frame with the lowest point of the "
    "figure on the same baseline; the height of the hop is added later in the game engine. The parcel stays "
    "tucked under the near arm in every frame."
)

WAVE = (
    "Layout: one single horizontal row of 6 animation frames of a friendly greeting wave, evenly spaced across "
    "the full width. The badger stands still, turned three-quarters towards the viewer (body facing front-right, "
    "face and smile turned to the viewer), both feet planted on the same baseline in every frame. The parcel "
    "stays tucked under one arm in every frame, the other paw waves: 1 standing, the paw down; 2 the paw rising "
    "to shoulder height; 3 the paw raised high above the cap, open palm, tilted to the left; 4 the same raised "
    "paw tilted to the right; 5 tilted to the left again; 6 the paw lowering to shoulder height. Big friendly "
    "smile, eyes open, everything except the waving arm stays the same."
)

# Zweiter Versuch nach dem ersten Winkblatt: Dort wechselten Paket und Winkarm in Bild 3 und 5 die Seite.
# Gegenmittel im Prompt: Seiten aus Sicht des Bildes benennen und den Wechsel ausdrücklich verbieten.
WAVE2 = (
    "Layout: one single horizontal row of 6 animation frames of a friendly greeting wave, evenly spaced across "
    "the full width. The badger stands still, turned three-quarters towards the viewer (body facing front-right, "
    "face and smile turned to the viewer), both feet planted on the same baseline in every frame. Sides are "
    "given as seen in the image: the parcel is tucked under the arm on the LEFT side of the image in every "
    "single frame, the satchel hangs on the left side of the image in every frame, and it is always the arm on "
    "the RIGHT side of the image that waves; the parcel never changes arms and the waving arm never changes "
    "sides. The waving paw: 1 down at his side; 2 rising to shoulder height; 3 raised high above the cap, open "
    "palm, tilted to the left; 4 the same raised paw tilted to the right; 5 tilted to the left again; 6 lowering "
    "to shoulder height. Big friendly smile, eyes open; body, head, legs, parcel and scarf stay exactly the same "
    "in all six frames, only the waving arm moves."
)

SHEET = ROOT / "shared" / "badger" / "master_sheet.png"


def sprite_prompt(layout, second_ref):
    return "\n".join([SPRITE_STYLE + (SAME_AS_WALK if second_ref else ""), char, layout, SHEET_RULES, guards, FMT])


prompts = {
    "bg": "\n".join([BG_STYLE, scene, BG_COMPOSITION, m["scene"]["background_only_en"], guards, FMT]),
    "walk": sprite_prompt(WALK, False),
    "idle": sprite_prompt(IDLE, True),
    "jump": sprite_prompt(JUMP, True),
    "wave": sprite_prompt(WAVE, True),
    "wave2": sprite_prompt(WAVE2, True),
}
OUT.mkdir(parents=True, exist_ok=True)
for k, v in prompts.items():
    (OUT / f"{k}.txt").write_text(v + "\n")

raw = f"{REL}/assets/raw"
ref = "shared/badger/master_sheet.png"
# Welle 1: Hintergrund (agy, Lastverteilung) und Laufblatt (Transparenz: Codex zuerst)
wave1 = [
    {"out": f"{raw}/walk.png", "size": "1536x1024", "prompt": prompts["walk"], "refs": [ref]},
    {"out": f"{raw}/bg.png", "size": "1536x1024", "prompt": prompts["bg"]},
]
# Welle 2: weitere Blätter mit Referenzblatt + eigenem Laufblatt (gebunden an dasselbe Modell)
wave2 = [
    {"out": f"{raw}/{k}.png", "size": "1536x1024", "prompt": prompts[k], "refs": [ref, f"{raw}/walk.png"]}
    for k in ("idle", "jump", "wave")
]
wave3 = [{"out": f"{raw}/wave2.png", "size": "1536x1024", "prompt": prompts["wave2"],
          "refs": [ref, f"{raw}/walk.png"]}]
(ENTRY / "assets" / "jobs_wave3.json").write_text(json.dumps(wave3, ensure_ascii=False, indent=1))
(ENTRY / "assets" / "jobs_wave1.json").write_text(json.dumps(wave1, ensure_ascii=False, indent=1))
(ENTRY / "assets" / "jobs_wave2.json").write_text(json.dumps(wave2, ensure_ascii=False, indent=1))
print("ok", sorted(p.name for p in OUT.glob("*.txt")))
