"""Baut die Bild-Prompts: Stilblock + Lage/Teile + Motivblock (wörtlich aus data/motif.json) + Schutzregeln
+ Formatangabe. Ergebnis in assets/prompts/*.txt.

    .venv/bin/python styles/gummischlauch/scripts/make_prompts.py
"""
import json
import pathlib

HERE = pathlib.Path(__file__).resolve().parent.parent
ROOT = HERE.parent.parent
M = json.loads((ROOT / "data" / "motif.json").read_text())
SCENE, CHAR = M["scene"]["block_en"], M["character"]["block_en"]
BG_ONLY, GUARDS = M["scene"]["background_only_en"], M["guards_en"]

PALETTE = (
    "Palette of an early two-colour film print from around 1930: only warm salmon-orange, brick red, peach, "
    "teal blue-green, muted sage, cream, sepia browns and near-black; no pure blue, no violet, no purple, no "
    "lemon yellow, no saturated modern colours; slightly faded and warm."
)

BG = f"""A painted background from an early 1930s animated cartoon short of the rubber-hose era, the kind of \
background that is painted on paper and placed behind the inked character cels. Hand-painted with gouache and \
transparent watercolour washes on paper, soft tonal painting with gentle painted gradients, every shape outlined \
with a fine, slightly wobbly dark sepia ink line. Simple, rounded, slightly bulging cartoon shapes: clouds as \
round puffy scalloped balls, rocks as soft lumpy blobs, the sea as calm flat washes with only a few small curly \
wave strokes, the quay paving as a few big rounded stones. Large calm areas, low detail, no texture noise. \
{PALETTE} Not a photograph, not a 3D render, not a modern digital painting, not a postcard, no film grain, no \
scratches, no vignette (all of that is added later in the game).

Composition: take the layout from the reference image exactly, as if traced on a clear sheet laid on top of it: \
the horizon line, the low far islands on the left, the rocky headland on the right with its flat grassy top, the \
sea, the long stone quay across the whole bottom of the picture and the short wooden jetty in the middle. The \
reference is only a flat block sketch: do not copy its flat colours or its hard straight edges, paint it.

{SCENE}

This picture is only the empty background plate. Paint the sky with soft clouds, the sea, the far islands, the \
bare rocky headland, the stone quay and the wooden jetty. Leave out the lighthouse, the cottage, the two boats, \
the barrels, the crates, the coil of rope and the lantern post: they are separate animated cel drawings that are \
placed on top of this plate later. The flat grassy top of the headland stays empty (the lighthouse is added \
there later). No birds, no stars, no smoke, no light beams, no reflections of lights. {BG_ONLY}

{GUARDS}

Image format: landscape 3:2."""

PROPS = f"""A sheet of separate prop drawings for an early 1930s rubber-hose cartoon, drawn as animation cels in \
classic ink and paint: every object has a bold, even, slightly wobbly black ink outline, flat colours and one \
soft painted shading tone, small white shine marks, simple rounded shapes that bulge a little as if made of \
rubber, low detail, no texture noise. {PALETTE} Use the reference image only for its palette and its painted \
light; draw the objects as cels with ink outlines, not as a painting.

Eight separate objects, all seen straight from the front at eye level, evenly spaced on the sheet in two rows \
with generous empty space between them, nothing overlapping, nothing cut off at the border:
Top row, left to right: (1) a small stone harbour-master's cottage with a slate roof, a short chimney without \
any smoke, a wooden door and one lit window (the window glass simply flat warm cream-orange, no glow around \
it); (2) a tall white lighthouse with one red band, a gallery and a lamp room, the lamp only a small flat warm \
cream spot without any beam or rays; (3) an iron lantern hanging from the arm of a tall wooden post, the lantern \
glass flat warm cream, no glow around it.
Bottom row, left to right: (4) two wooden barrels side by side; (5) a stack of three wooden crates; (6) a coil \
of rope lying flat; (7) a small wooden fishing boat with a short mast and no sail, seen exactly from the side, \
bow to the right, the hull cut off by a straight horizontal line at the waterline; (8) a second, smaller fishing \
boat of a different colour, also from the side, bow to the left, also cut off straight at the waterline.

These props belong to this scene: {SCENE}

No ground, no shadows under the objects, no water, no sky. Isolated on a fully transparent background.

{GUARDS}

Image format: landscape 3:2."""

BADGER = f"""Cutout puppet parts sheet for a character in an early 1930s rubber-hose cartoon, drawn as \
animation cels in exactly the same ink-and-paint technique as the second reference image: bold, even black ink \
outline, flat colours with one soft shading tone, small white shine marks, no fur texture. {PALETTE}

The character: {CHAR}
Take only the costume (cap, vest, shirt, scarf, satchel, parcel) and its colours from the first reference image. \
Redesign the body as a classic rubber-hose cartoon character: a big round head, a short pear-shaped body, the \
badger's face simplified to a few clear black and white shapes, two large white oval eyes with black pie-cut \
pupils (each pupil is a black oval with a small triangular wedge cut out of it), a small shiny black nose, a wide \
happy grin, very simple bold shapes, no claws, no fur strands.

Both body pieces show the same character with identical colours and proportions; each body piece is drawn \
large, about half as tall as the sheet. Draw these separate pieces, all at the same scale, evenly spaced with \
generous empty space between them, nothing overlapping:
(1) Left: the head and body in side view, facing right, WITHOUT arms and WITHOUT legs. The body ends at the hips \
in a smooth rounded dark-furred bottom. At the shoulder only the short rolled-up cream shirt sleeve is drawn, as \
a small rounded puff with an open dark end (the arms are added later as thin black rubber hose tubes coming out \
of the sleeve). Cap, scarf with its hanging end, vest and the satchel on its strap belong to this piece.
(2) Middle: the same head and body in front view, looking at the viewer, also WITHOUT arms and WITHOUT legs, a \
short sleeve puff at each shoulder, the body ending at the hips in the same rounded dark-furred bottom.
(3) Right, in a column: four white cartoon gloves, each with a rolled cuff and three stitch lines on the back, \
four fingers: a relaxed open hand seen from the side; a fist seen from the side; an open hand seen from the front \
with the fingers spread and pointing up (waving); a hand seen from the side gripping something, thumb on top.
(4) The brown paper parcel tied with string, alone, seen from the side.

No ground, no shadows. Isolated on a fully transparent background.

{GUARDS}

Image format: landscape 3:2."""


BG_B = BG.replace(
    "the quay paving as a few big rounded stones",
    "the quay floor as large flat flagstones drawn as simple rounded slabs lying flat on the ground",
).replace(
    """Composition: take the layout from the reference image exactly, as if traced on a clear sheet laid on top of it: \
the horizon line, the low far islands on the left, the rocky headland on the right with its flat grassy top, the \
sea, the long stone quay across the whole bottom of the picture and the short wooden jetty in the middle. The \
reference is only a flat block sketch: do not copy its flat colours or its hard straight edges, paint it.""",
    """Composition: the reference image is an earlier version of this plate. Keep its sky, clouds, sea, far islands, \
rocky headland, wooden jetty and its painting technique exactly, as if traced on a clear sheet laid on top of it. \
Change only the quay in the lower part: it must be a flat surface to walk on. Along the waterline, where the \
reference has a row of big round boulders, there is only a low kerb of squared stone blocks, no higher than the \
planks of the jetty. In front of the kerb, from there down to the bottom edge of the picture, lies a wide, flat, \
paved quay floor seen slightly from above, made of large flat flagstones with ink outlines and soft painted \
shading. No boulders, no wall, no steps.""",
)


def main():
    out = HERE / "assets" / "prompts"
    out.mkdir(parents=True, exist_ok=True)
    for name, text in [("bg", BG), ("bg_b", BG_B), ("props", PROPS), ("badger", BADGER)]:
        (out / f"{name}.txt").write_text(text + "\n")
        print(name, len(text))


if __name__ == "__main__":
    main()
