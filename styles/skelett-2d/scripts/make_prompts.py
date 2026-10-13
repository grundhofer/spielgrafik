#!/usr/bin/env python3
"""Baut die Bild-Prompts für skelett-2d aus Stilblock + Motivblock (wörtlich aus data/motif.json) + Schutzregeln.

    .venv/bin/python styles/skelett-2d/scripts/make_prompts.py

Schreibt assets/prompts/bg.txt und assets/prompts/parts.txt.
"""
import json, pathlib

ROOT = pathlib.Path(__file__).resolve().parents[3]
OUT = pathlib.Path(__file__).resolve().parents[1] / "assets" / "prompts"
m = json.loads((ROOT / "data" / "motif.json").read_text())
scene, char, guards = m["scene"]["block_en"], m["character"]["block_en"], m["guards_en"]

BG_STYLE = (
    "Style: hand-painted 2D background for a modern side-view adventure game whose characters are animated "
    "with 2D skeletal mesh rigs. Painted with textured digital brushes in a matte, slightly gouache-like "
    "manner: visible brush strokes, clean simplified shapes with soft edges, gentle stylisation with rounded, "
    "slightly leaning forms, moderate detail, calm readable planes. Thin contour lines only where shapes need "
    "separating, always in a darker shade of the local colour, never black. Palette: dusty violet, teal blue "
    "and slate for sky, sea and shadows, warm amber and orange only for the horizon band and the lights; mid "
    "values overall, so that a character painted in front stays readable. Not a photograph, not a 3D render, "
    "not a postcard, not pixel art, no paper cut-out look."
)

BG_COMPOSITION = (
    "Composition: side view from the eye level of a small character standing on the quay, close to the quay. "
    "Flat sea horizon at about 46 % of the image height. The stone quay is a wide, flat, walkable pavement that "
    "fills the lower 34 % of the image across the full width; its paving stones are large and calm, and the "
    "middle of the quay from 10 % to 75 % of the image width stays completely empty as a walking path. The "
    "cottage stands set back on the quay at the left edge, filling the left 22 % of the width, its door about "
    "30 % of the image height tall, the lit window facing the viewer, the chimney against open sky. The iron "
    "lantern on its wooden post stands on the quay at about 70 % of the width, its lantern at about 38 % of the "
    "image height against the sea and sky. The barrels, the crate stack and the rope coil stand together on the "
    "right of the quay, from 78 % to 100 % of the width. Behind the quay, between 25 % and 60 % of the width, the "
    "short wooden jetty reaches into the water with the two boats moored at it. The rocky headland rises from "
    "the sea on the right behind the props; the lighthouse stands on it at about 86 % of the width, its top at "
    "about 14 % of the image height. Keep a margin of plain sky above the top of the lighthouse and the chimney "
    "and plain pavement at the bottom edge (the image will be cropped to 16:9). The lighthouse lamp is only a "
    "small glowing spot without any beam, there is no smoke from the chimney, no glow halo around the lantern "
    "and no birds: beam, smoke, glow and birds are animated separately in the game."
)

PART_STYLE = (
    "Character parts sheet for 2D skeletal mesh animation in a game, painted in the technique of the second "
    "reference image (a painted harbour background): textured digital brushes in a matte, slightly gouache-like "
    "manner, visible brush strokes, clean readable shapes, gentle stylisation, thin contour lines in a darker "
    "shade of each local colour (dark brown, dark green, dark red; never black ink). Soft painted shading in a "
    "few value steps, neutral even light from the front-top (the game adds its own lights), no rim light, no "
    "cast shadows, no ground. The first reference image is a character sheet: take only the costume, the "
    "colours and the proportions from it, not its drawing style and not its layout with three views. Not a 3D "
    "render, not plush, not a photograph."
)

PART_LAYOUT = (
    "Layout of the sheet: the badger courier seen exactly from the side, facing right. Left third of the "
    "image: the complete assembled character standing upright in a neutral pose, both feet flat on one "
    "baseline, the near leg slightly in front of the far leg, the far arm hanging down behind the body, the "
    "near arm holding the parcel against the side of the body, the loose ends of the scarf hanging down his "
    "back. Right two thirds of the image: the same character taken apart into separate pieces for the rig, each "
    "piece complete and painted at exactly the same scale as the assembled figure, laid out in a loose grid "
    "with clear empty space between all pieces; no piece touches or overlaps another. The pieces: (1) the body: "
    "head with cap and ears, the scarf wrapped around the neck, the torso with shirt, vest, satchel strap and "
    "satchel, the belly and the short tail, WITHOUT arms and WITHOUT legs; where arms and legs would attach, "
    "the shirt, vest and fur are painted complete, with no holes and no cut edges. (2) the near arm: rolled-up "
    "cream sleeve, dark furry forearm and paw, holding the parcel tied with string. (3) the far arm: the same "
    "arm without the parcel, hanging straight down, a little darker because it is in shadow. (4) the near leg: "
    "a short, stout, dark furry leg with a large paw with claws, seen from the side, standing straight, the top "
    "of the leg rounded where it goes into the hip. (5) the far leg: the same leg, a little darker. (6) the two "
    "loose ends of the red knitted scarf with their fringes, hanging straight down. No labels, no arrows, no "
    "guide lines, no frames."
)

OUT.mkdir(parents=True, exist_ok=True)
(OUT / "bg.txt").write_text("\n".join([
    BG_STYLE, scene, BG_COMPOSITION, m["scene"]["background_only_en"], guards, "Image format: landscape 3:2."]) + "\n")
(OUT / "parts.txt").write_text("\n".join([
    PART_STYLE, PART_LAYOUT, char,
    "All pieces isolated on a fully transparent background.", guards, "Image format: landscape 3:2."]) + "\n")
print("ok", [p.name for p in OUT.glob("*.txt")])
