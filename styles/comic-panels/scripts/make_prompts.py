#!/usr/bin/env python3
"""Setzt die Bild-Prompts des Eintrags aus Stilblock, Motivblöcken (data/motif.json, wörtlich) und Schutzregeln zusammen.

    .venv/bin/python styles/comic-panels/scripts/make_prompts.py

Schreibt prompts/<name>.txt für genimg.py.
"""
import json, pathlib

ROOT = pathlib.Path(__file__).resolve().parents[1]
PROJ = ROOT.parents[1]
P = ROOT / "prompts"
motif = json.loads((PROJ / "data/motif.json").read_text())
SCENE = motif["scene"]["block_en"]
BG_ONLY = motif["scene"]["background_only_en"]
CHAR = motif["character"]["block_en"]
GUARDS = motif["guards_en"]
STYLE = (P / "style_block.txt").read_text().strip()
FMT = "Image format: landscape 3:2."

BG_COMPOSITION = (
    "Composition for a game panel: a wide establishing shot at eye level. The harbour-master's cottage stands at the "
    "left edge, its lit window clearly visible. The white lighthouse with its red band stands on its rocky headland at "
    "the right, about 80 percent across, its top about 15 percent below the upper edge. The iron lantern on its "
    "wooden post stands on the quay a little left of the centre. The jetty with the two moored boats lies in the "
    "middle distance between the cottage and the headland. Horizon at about 45 percent from the top. The front edge "
    "of the stone quay, the bottom fifth of the picture, is an empty, flat paved walkway seen close up, running "
    "straight across the whole width: characters are added there later. Barrels, crates and the rope stand further "
    "back on the quay, out of that walkway. The upper left corner is calm sky (a caption box is placed there later). "
    "The lighthouse lamp only as a small bright yellow spot without any beam of light; the lantern glass flat yellow "
    "without glow or rays; no smoke from the chimney; no birds (beam, glow, smoke and seagulls are animated "
    "separately).")

LANTERN = (
    "A close-up panel from the same American adventure comic book of the early 1960s as the reference image, with the "
    "same inking, the same flat printer's colours and the same dusk light. " + STYLE + "\n\n"
    "Subject of this panel: a close-up of the iron harbour lantern on its weathered wooden post, the same lantern as in "
    "the reference image, seen slightly from below. The lantern is large in the right half of the picture: its black "
    "iron cage, the four glass panes and the small flame inside are drawn clearly with bold contours; the wooden post "
    "runs down out of the bottom edge, the iron arm holds the lantern. The glass panes are a flat bright yellow, the "
    "flame a simple yellow-orange teardrop shape; no glow, no halo, no light rays around the lantern (the flickering "
    "light is animated separately). Behind it on the left: the stone wall and the lit yellow window of the "
    "harbour-master's cottage and a part of its slate roof; above, the dusk sky in flat bands with the first stars. "
    "The upper left quarter of the picture is calm sky with nothing important in it (a caption box is placed there "
    "later). No smoke, no birds.\n\n"
    "Location of the story, for context only (this panel shows only the close-up described above): " + SCENE)

BUST = (
    "A close-up panel from the same American adventure comic book of the early 1960s as the second reference image, "
    "with the same inking, the same flat printer's colours and the same dusk light. " + STYLE + "\n\n"
    "Subject of this panel: a medium close-up of the badger courier from the waist up, in three-quarter view, turned "
    "towards the left, looking at the viewer with a friendly, confident half-smile, mouth closed. One paw holds the "
    "parcel against his chest, the satchel strap crosses his chest. Take only the costume and the proportions of the "
    "character from the first reference image; do not copy its painterly drawing style, its fur texture or its "
    "three-view layout. Draw him as a comic-book character: bold brush contours with line-weight variation, solid "
    "black shadow shapes under the cap brim, under the chin, on the shadow side of the face and the vest; the fur "
    "suggested only by a few jagged brush flicks at the silhouette, not painted fur; big clear shapes; a clear, "
    "expressive eye with a white highlight, a black nose, the mouth line clearly drawn. The dark fur is a flat dark "
    "blue-grey with solid black shadow shapes, the white stripes and the muzzle are cream white. The badger fills the "
    "right two thirds of the picture, his head in the upper half, the cap not cut off. Behind him, simplified: the "
    "dusk sky in flat bands, the sea and, small in the distance on the left, the white lighthouse with its red band "
    "on its headland. The upper left third of the picture is open sky with nothing important in it (a speech balloon "
    "is placed there later).\n\n" + CHAR)

TALK = (
    "Redraw the reference image exactly, as if traced on a clear sheet laid on top of it: the same composition, the "
    "same size and position of everything, the same lines, the same flat colours, the same background. The only "
    "change: the badger's mouth is open as if he is speaking a word (a small open mouth with a dark inside and a "
    "little pink tongue, the lower jaw slightly lowered). Everything else stays exactly the same.")

WALK = (
    "Sprite sheet for a 2D side-view narrative game: ten figures of the same character, drawn and inked like a "
    "character in an American adventure comic book of the early 1960s, each figure about 400 pixels tall. The first "
    "reference image gives the exact layout, the exact size and the exact poses: ten figures in two rows of five, all "
    "at the same scale, the feet of each row on the same baseline. Figures one to eight (in reading order) are a walk "
    "cycle to the right in strict side view; figure nine stands still in side view, both feet flat on the ground; "
    "figure ten has turned three-quarters towards the viewer. Copy every pose, the positions of both legs and feet, "
    "the arms, the parcel and the satchel, and the place and size of each figure exactly from the first reference; "
    "only the drawing changes. The first reference is a plain 3D render: take only the layout, the size and the poses "
    "from it, never its smooth shading or its plastic 3D look. The second reference image only shows the costume and "
    "the proportions of the character: do not copy its painterly drawing style, its fur texture, its colours or its "
    "three-view layout. The third reference image is the comic panel this character walks in: draw the character "
    "with the same bold brush inking and the same flat printer's colours, so that he belongs in that panel.\n\n"
    "Technique: a bold black brush contour around each figure with strong line-weight variation (thick on the outside "
    "and on the shadow side, thinner inside), interior lines only where costume parts meet, solid spotted black "
    "shadow shapes on the shadow side (the back of the legs, under the arm, under the cap brim, under the parcel), the "
    "fur suggested only by a few jagged brush flicks at the silhouette. Flat, solid, unmodulated colour fills, each "
    "costume part one flat colour plus solid black for its shadow: the dark fur a flat dark blue-grey, the face "
    "stripe, cheeks and belly cream white, the cap and the vest olive green, the shirt pale cream, the scarf bright "
    "red, the satchel brown, the parcel tan with dark string, the button yellow. No gradients, no soft shading, no "
    "airbrush, no fur texture, no halftone dots or screen tones. Keep the face readable at game size: a clear cream "
    "stripe from the nose over the forehead between the two dark stripes, a small black eye with a white highlight, "
    "a black nose. Not a 3D render, not a painting, not a cel-shaded render.\n\n" + CHAR + "\n\n"
    "Each figure isolated on a fully transparent background; inside the figure all areas are opaque. Clear empty "
    "space between the figures; no ground, no cast shadow, no frame borders, nothing cut off at the edge of the sheet.")

PROMPTS = {
    "bg": "\n\n".join([STYLE, SCENE, BG_COMPOSITION, BG_ONLY, GUARDS, FMT]),
    "lantern": "\n\n".join([LANTERN, GUARDS, FMT]),
    "bust": "\n\n".join([BUST, GUARDS, FMT]),
    "bust_talk": "\n\n".join([TALK, GUARDS, FMT]),
    "walk": "\n\n".join([WALK, GUARDS, FMT]),
}
for name, text in PROMPTS.items():
    (P / f"{name}.txt").write_text(text + "\n")
    print(name, len(text))
