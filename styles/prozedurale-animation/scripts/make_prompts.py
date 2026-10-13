#!/usr/bin/env python3
"""Baut die Bild-Prompts für prozedurale-animation: Stilblock + Motivblock (wörtlich aus data/motif.json)
+ Schutzregeln + Formatangabe.

    .venv/bin/python styles/prozedurale-animation/scripts/make_prompts.py

Schreibt assets/prompts/{bg,badger,boats}.txt und assets/jobs.json (Format von genimg.py --jobs).
"""
import json, pathlib

ROOT = pathlib.Path(__file__).resolve().parents[3]
SD = pathlib.Path(__file__).resolve().parents[1]
OUT = SD / "assets" / "prompts"
m = json.loads((ROOT / "data" / "motif.json").read_text())
scene, char, guards = m["scene"]["block_en"], m["character"]["block_en"], m["guards_en"]
bg_only = m["scene"]["background_only_en"]

# Stil wie das Referenzblatt der Figur (sauberer dunkler Umriss, flache Zellschattierung), damit die
# Figur aus Codex ohne nachgezogene Kontur vor dem Hintergrund aus agy steht.
PAINT = (
    "2D hand-painted cartoon look for a modern side-view adventure game: clean dark brown outlines of even "
    "weight around every shape, flat cel shading with two or three tones per surface, simple rounded shapes, "
    "a little painterly texture inside the flat areas, moderate detail"
)

BG_STYLE = (
    f"Style: background painting for a 2D game, {PAINT}. Sky and sea painted with soft broad gradients and a "
    "few simple stylised cloud shapes. Palette: dusty violet, slate blue and teal for sky, sea and shadows, "
    "warm amber and orange only for the horizon band and the lights; mid values overall, so that characters "
    "painted in front stay readable. Not a photograph, not a 3D render, not a postcard, not pixel art, no "
    "lens effects, no vignette."
)

BG_COMPOSITION = (
    "Composition: a plain side view from the eye level of a small character standing on the quay. Flat sea "
    "horizon at about 45 % of the image height. The stone quay is a wide, flat, walkable pavement that fills "
    "the lower 30 % of the image across the full width; its front edge, a straight row of stone blocks, runs "
    "horizontally at about 70 % of the image height with the water directly behind it. The paving stones are "
    "large and calm, and the quay from 8 % to 72 % of the image width stays completely empty as a walking "
    "path. The cottage stands set back at the left edge, filling the left 18 % of the width, its door about "
    "25 % of the image height tall, the lit window facing the viewer, the chimney against open sky. The iron "
    "lantern on its wooden post stands at the back edge of the quay at about 35 % of the width, its lantern at "
    "about 40 % of the image height against the sea. A short wooden jetty on posts leads from the quay out "
    "into the water at about 60 % of the width. The barrels, the crate stack and the rope coil stand together "
    "on the right of the quay, from 80 % to 100 % of the width. The rocky headland rises from the sea on the "
    "right; the lighthouse stands on it at about 86 % of the width, its top at about 14 % of the image height. "
    "Keep a margin of plain sky above the lighthouse and the chimney and plain pavement at the bottom edge "
    "(the image will be cropped to 16:9). "
    "Important: there are NO boats in this picture: the two fishing boats and their mooring lines are added "
    "later as separate animated sprites, so the calm water between 22 % and 78 % of the width, left and right "
    "of the jetty, stays open and empty. The lighthouse lamp is only a small glowing spot without any beam, "
    "there is no smoke from the chimney, no glow halo around the lantern and no birds in the sky: beam, smoke, "
    "glow, boats and birds are animated separately in the game."
)

BADGER_STYLE = (
    f"Character parts sheet for a 2D game in which a single painted character image is animated by code "
    f"(bobbing, tilting, squash and stretch, legs moved by inverse kinematics, scarf end and satchel swinging "
    f"on simulated springs). Painted in the {PAINT}, exactly the drawing technique of the reference image. "
    "Neutral even light from the front-top (the game adds its own dusk lighting), no rim light, no cast "
    "shadows, no ground. The reference image is a character sheet with three views: take the costume, colours, "
    "proportions and drawing style from its middle side view, not its layout. Not a 3D render, not plush, not "
    "a photograph."
)

BADGER_LAYOUT = (
    "Layout of the sheet: the badger courier seen exactly from the side, facing right, all pieces at exactly "
    "the same scale. Left third of the image: the complete assembled character standing upright in a neutral "
    "pose, both feet flat on one baseline, the near arm holding the parcel against the side of the body, the "
    "satchel hanging at the back of the hip on its strap that runs from the shoulder, the loose end of the scarf "
    "hanging down his back. Right two thirds of the image: the same character taken apart into four separate "
    "pieces, each complete, laid out with clear empty space between all pieces; no piece touches or overlaps "
    "another. (1) The body: head with cap and ears, the scarf wrapped around the neck with a small knot at the "
    "back of the neck, the torso with shirt and vest, the near arm holding the parcel against the side of the "
    "body, the belly and the short tail, WITHOUT legs, WITHOUT the satchel and WITHOUT its strap, and WITHOUT "
    "the loose scarf end; the bottom of the belly and hips is rounded and painted complete with fur where the "
    "legs would attach, no holes, no cut edges. (2) One leg: a short, stout, dark furry hind leg seen from the "
    "side, standing straight, a column of even width from a rounded top down to the ankle, with a large paw "
    "with claws pointing right and a flat sole. (3) The loose end of the red knitted scarf, a straight strip "
    "hanging straight down, with a straight top edge and the fringe at the bottom. (4) The brown leather "
    "satchel alone without its strap, seen from the side, with its flap, a brass buckle and two small metal "
    "rings at the top corners where a strap would attach. No labels, no arrows, no guide lines, no frames."
)

BOATS_STYLE = (
    f"Two game sprites for a 2D game, painted in the {PAINT}. Soft dusk light from the left, muted colours: "
    "weathered brown and grey-blue wood, dull white and faded red paint. Not a 3D render, not a photograph."
)

BOATS_LAYOUT = (
    "Two small wooden fishing boats of a northern island harbour, each seen exactly from the side (profile) "
    "and very slightly from above, side by side with clear empty space between them, same scale: (1) on the "
    "left a small fishing boat about three times as long as high, with a short mast, a furled reddish-brown "
    "sail tied to the boom, a small open wooden cabin roof at the stern and a few nets and a buoy on board, bow "
    "pointing left; (2) on the right a smaller rowing boat with two oars resting inside, painted white with a "
    "faded red stripe, bow pointing right. Each complete hull is visible down to the keel; no water, no "
    "reflection, no ripples, no mooring ropes, no ground, no shadow."
)

TRANSPARENT = "All pieces isolated on a fully transparent background."

prompts = {
    "bg": "\n".join([BG_STYLE, scene, BG_COMPOSITION, bg_only, guards, "Image format: landscape 3:2."]),
    "badger": "\n".join([BADGER_STYLE, BADGER_LAYOUT, char, TRANSPARENT, guards,
                         "Image format: landscape 3:2."]),
    "boats": "\n".join([BOATS_STYLE, BOATS_LAYOUT, TRANSPARENT, guards, "Image format: landscape 3:2."]),
}
OUT.mkdir(parents=True, exist_ok=True)
for k, v in prompts.items():
    (OUT / f"{k}.txt").write_text(v + "\n")

rel = "styles/prozedurale-animation/assets/raw"
jobs = [
    {"out": f"{rel}/bg.png", "size": "1536x1024", "prompt": prompts["bg"]},
    {"out": f"{rel}/badger.png", "size": "1536x1024", "prompt": prompts["badger"],
     "refs": ["shared/badger/master_sheet.png"]},
    {"out": f"{rel}/boats.png", "size": "1536x1024", "prompt": prompts["boats"]},
]
(SD / "assets" / "jobs.json").write_text(json.dumps(jobs, indent=1, ensure_ascii=False) + "\n")
print("ok", {k: len(v) for k, v in prompts.items()})
