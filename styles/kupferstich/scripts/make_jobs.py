#!/usr/bin/env python3
"""Schreibt die Bildaufträge des Eintrags kupferstich (Format von tools/genimg.py --jobs).

    .venv/bin/python styles/kupferstich/scripts/make_jobs.py bg          -> assets/jobs_bg.json
    .venv/bin/python styles/kupferstich/scripts/make_jobs.py bg2         -> assets/jobs_bg2.json (zweiter Versuch)
    .venv/bin/python styles/kupferstich/scripts/make_jobs.py figures     -> assets/jobs_figures.json (Laufbogen, Ornamente, Maske)
    .venv/bin/python styles/kupferstich/scripts/make_jobs.py walk_small  -> assets/jobs_walk_small.json
    .venv/bin/python styles/kupferstich/scripts/make_jobs.py mask        -> assets/jobs_mask.json

Aufbau jedes Prompts nach PIPELINE.md: Stilblock + Motivblock (wörtlich aus data/motif.json) + Hinweise +
Schutzregeln + Formatangabe. Die Prompts landen zusätzlich als Text in prompts/<name>.txt.
"""
import json, pathlib, sys

ROOT = pathlib.Path(__file__).resolve().parents[3]
SD = ROOT / "styles/kupferstich"
M = json.loads((ROOT / "data/motif.json").read_text())
SCENE, BG_ONLY, BADGER, GUARDS = (M["scene"]["block_en"], M["scene"]["background_only_en"],
                                  M["character"]["block_en"], M["guards_en"])
RAW = "styles/kupferstich/assets/raw"

ENGRAVING = (
    "Technique: a copper-plate engraving with etching, printed in a single dark sepia-brown ink on plain white "
    "paper. Everything is built only from engraved lines: long parallel hatching, cross-hatching in two or three "
    "directions for the darks, swelling lines that are thick in the shadows and taper to hair-thin points in the "
    "light, short flicks and stipple dots for stone and rock, contour lines that follow the forms. The tone values "
    "come only from the thickness and spacing of the lines: no grey wash, no aquatint, no tonal gradients, no "
    "airbrush, no smudged pencil shading, no colour; between the lines the paper stays white. "
)
# Für Figuren und Ornamente gleich in Schwarz (der Druckton kommt erst in Godot dazu).
ENGRAVING_BLACK = ENGRAVING.replace("printed in a single dark sepia-brown ink on plain white paper",
                                    "printed in a single pure black ink on pure white paper (no tinted ground)")

BG_STYLE = (
    "A full-page illustration plate from a 19th-century adventure book about the sea. " + ENGRAVING +
    "The sky is ruled with long, perfectly even horizontal lines, close together and thick at the top of the sky, "
    "thinning out towards a light band at the horizon; the low clouds are shaped only by thicker and thinner "
    "ruling and a few contour lines. The calm sea is drawn with long horizontal, slightly wavy lines with white "
    "gaps for the reflections. Nocturne mood with strong contrast: deep cross-hatched darks in the cottage, the "
    "rocks and the boat hulls; bare white paper only at the lights, the horizon band and the reflections. "
    "The lines must be crisp, clearly separated and bold enough to stay readable when the picture is shown at "
    "screen size: about 200 lines across the height of the picture in the sky and the water, never a dense grey "
    "mush. Not a photograph, not a 3D render, not a painting, not a pencil drawing, not a woodcut, not a "
    "cartoon, not a postcard. No aged paper texture, no stains, no frame, no border line, no plate mark, no "
    "caption."
)

BG_LAYOUT = (
    "Composition for a wide game screen; the picture will later be cropped to a wide panoramic strip, so keep "
    "every important element between 17 % and 83 % of the picture height: above that only ruled sky, below that "
    "only plain quay paving. Eye-level view from the quay. The near quay is a broad, empty band of large "
    "cobblestones across the whole width, from about 66 % of the picture height down to the bottom edge: the "
    "character will walk there from the left to the middle, so keep it free and calm. The stone cottage stands "
    "at the far left (0 to 22 % of the width), its chimney against open sky. The iron lantern on its wooden post "
    "stands at the back edge of the near quay at about 30 % of the width, the lantern itself against open sky. "
    "The short wooden jetty with the two moored boats lies in the middle (35 to 65 % of the width), the horizon "
    "at about 47 % of the picture height. The lighthouse on its rocky headland stands at about 80 % of the width, "
    "its lamp against open sky. The two barrels, the stack of crates and the coil of rope stand on the near quay "
    "at the right (75 to 98 % of the width); the barrels are about a fifth of the picture height tall. Leave "
    "wide areas of open ruled sky above the jetty and of calm open water in front of it."
)

# Zweiter Versuch (bg2): näher an der Figur (Dachs etwa 30 % der Bildhöhe), Druck in Schwarz auf reinweißem Papier
# (der erste Versuch kam braun getönt mit Flächenton zwischen den Linien) und gröbere Linien.
BG2_STYLE = (
    "A full-page illustration plate from a 19th-century adventure book about the sea. " + ENGRAVING +
    "Printed in pure black ink on pure white paper: between the lines the paper is pure white, no tinted ground, "
    "no brown or sepia toning, no red, no colour at all. Bold, widely spaced engraved lines like a coarse steel "
    "engraving for an illustrated weekly: about 150 lines across the height of the picture, every line clearly "
    "separated from the next by white paper, the lines swelling to fill the darks and thinning out in the "
    "light. The sky is ruled with long, perfectly even horizontal lines, thick at the top of the sky and thinning "
    "out towards a light band at the horizon; the low clouds are shaped only by thicker and thinner ruling and a "
    "few contour lines. The calm sea is drawn with long horizontal, slightly wavy lines with white gaps for the "
    "reflections. Nocturne mood with strong contrast: deep cross-hatched darks in the cottage, the rocks and the "
    "boat hulls; bare white paper only at the lights, the horizon band and the reflections. Not a photograph, "
    "not a 3D render, not a painting, not a pencil drawing, not a woodcut, not a cartoon, not a postcard. No aged "
    "paper texture, no stains, no frame, no border line, no plate mark, no caption."
)

BG2_LAYOUT = (
    "Composition for a wide game screen; the picture will later be cropped to a wide panoramic strip, so keep "
    "every important element between 15 % and 85 % of the picture height: above that only ruled sky, below that "
    "only plain quay paving. The viewpoint is close to the near quay, at the eye height of a small character: a "
    "character standing on the near quay will be about 30 % of the picture height tall, so everything on the near "
    "quay is large. The near quay paving is a band across the whole width from about 70 % of the picture height "
    "to the bottom edge; the character will walk along it at about 82 % of the height from the left edge to the "
    "middle, so keep the left two thirds of the near quay free and calm. In the near foreground at the right "
    "(72 to 98 % of the width), standing on the near quay at 82 % of the height: two large barrels, each about a "
    "quarter of the picture height tall, a stack of crates and a coil of rope. The iron lantern on its wooden post "
    "stands at the back edge of the near quay at about 30 % of the width, the post about half the picture height "
    "tall, the lantern itself against open sky. The stone cottage stands further back on the left (0 to 22 % of "
    "the width), small enough that its roof and chimney are fully in the picture, the chimney top at about 20 % "
    "of the picture height against open sky. The short wooden jetty with the two moored boats lies in the middle "
    "distance (35 to 65 % of the width), the horizon at about 50 % of the picture height. The lighthouse on its "
    "rocky headland stands in the distance at about 82 % of the width, its top at about 20 % of the picture "
    "height, its lamp against open sky. Wide areas of open ruled sky above the jetty and of calm open water in "
    "front of it."
)

BG_ANIM = (
    "The lighthouse lamp, the lantern and the lit window are only small areas of bare white paper, without any "
    "beam or rays of light; the chimney without smoke; no birds in the sky. Light beam, smoke and gulls are "
    "animated separately in the game."
)

FIG_STYLE = (
    "Sprite sheet for a 2D side-view narrative game: ten figures of the same character, drawn as copper-plate "
    "engravings for a 19th-century book. The first reference image gives the exact layout and the exact poses: "
    "ten figures in two rows of five, all at the same scale, the feet of each row on the same baseline. Figures "
    "one to eight (in reading order) are a walk cycle to the right in strict side view; figure nine stands still "
    "in side view, both feet flat on the ground; figure ten has turned three-quarters towards the viewer. Copy "
    "every pose, the positions of both legs and feet, the arms, the parcel and the satchel, and the place and "
    "size of each figure exactly from the first reference; only the drawing changes. The first reference is a "
    "plain 3D render: take only the layout and the poses from it, never its smooth shading or its plastic 3D "
    "look. The second reference image only shows the costume, the face and the proportions of the character: do "
    "not copy its drawing style, its colours or its three-view layout. The third reference image shows the "
    "engraving technique and line weight of the game: draw the figures with exactly this technique, but do not "
    "copy any of its content.\n\n" + ENGRAVING_BLACK +
    "A firm, clear contour line around every shape; the hatching curves around the round body, the arms, the "
    "legs and the cap; short engraved flicks for the fur. Light from the upper left. The colours of the costume "
    "become tone values: the dark fur and the dark face stripes in dense cross-hatching, the white face stripes "
    "and the light belly almost bare white paper with a few fine lines, the cream shirt light with sparse "
    "hatching, the dark green cap and vest in medium-dark hatching, the red scarf in medium hatching with the "
    "knitting hinted by short strokes, the satchel dark, the parcel light with its string clearly drawn. Keep the "
    "face clearly readable: a small dark eye with a white highlight, a black nose, the broad stripes of the face. "
    "The lines must be bold and clearly separated so that the figure stays readable when shown about 250 pixels "
    "tall: about 60 to 80 hatching lines across the height of a figure, never a grey mush. Not a cartoon, not "
    "a comic, not a 3D render, not a painting, not a pencil sketch, no colour."
)

# Zweiter Laufbogen (walk_small): Figuren in Spielgröße (etwa 200 px), weil das Bildmodell den absoluten
# Linienabstand hält. Der erste Bogen (400 px hohe Figuren, Linienabstand 3–4 px) wurde beim Verkleinern grau.
FIG_SMALL = (
    "Sprite sheet for a 2D side-view narrative game: ten small figures of the same character, drawn as "
    "copper-plate engravings for a 19th-century book, each figure only about 200 pixels tall. The first reference "
    "image gives the exact layout, the exact size and the exact poses: ten figures in two rows of five, all at the "
    "same small scale, the feet of each row on the same baseline. Figures one to eight (in reading order) are a "
    "walk cycle to the right in strict side view; figure nine stands still in side view, both feet flat on the "
    "ground; figure ten has turned three-quarters towards the viewer. Copy every pose, the positions of both legs "
    "and feet, the arms, the parcel and the satchel, and the place and size of each figure exactly from the first "
    "reference; only the drawing changes. The first reference is a plain 3D render: take only the layout, the size "
    "and the poses from it, never its smooth shading or its plastic 3D look. The second reference image only shows "
    "the costume and the proportions of the character: do not copy its drawing style, its colours or its "
    "three-view layout. The third reference image shows the engraving technique and, most important, the line "
    "spacing and line width of the game at the size it is shown on screen: use exactly the same absolute spacing "
    "and width of the lines as in the third reference, so the small figures have fewer lines, not finer lines. The "
    "fourth reference image shows this character already drawn as an engraving at a larger size: keep its "
    "drawing, its face and its tone values, but draw it small with the coarser lines of the third reference; do "
    "not copy its layout or its size.\n\n" + ENGRAVING_BLACK +
    "A firm, clear contour line around the figure and around every costume part; the hatching curves around the "
    "round body, the arms, the legs and the cap. Light from the upper left. The colours of the costume become tone "
    "values: the dark fur and the dark face stripes in dense, bold cross-hatching, the white face stripes and the "
    "light belly bare white paper inside a contour line, the cream shirt white with a few lines in the shadow, the "
    "dark green cap and vest in medium-dark hatching, the red scarf in medium hatching, the satchel dark, the "
    "parcel white with its string. Keep the face readable at this small size: a small black eye, a black nose, "
    "the broad white stripe of the face clearly separated from the dark stripe. Bold, open, clearly separated "
    "lines with white paper between them, never a grey mush and never fine hair lines. Not a cartoon, not a comic, "
    "not a 3D render, not a painting, not a pencil sketch, no colour."
)

FIG_ISO = (
    "Each figure isolated on a fully transparent background; inside the figure the white paper between the lines "
    "is opaque white. Clear empty space between the figures; no ground, no cast shadow, no frame borders, nothing "
    "cut off at the edge of the sheet."
)

ORN = (
    "A sheet of three separate printer's ornaments for a 19th-century book, each one a copper-plate engraving "
    "printed in a single pure black ink on pure white paper, crisp engraved lines, parallel hatching and "
    "cross-hatching, tone only through line thickness and spacing, no grey wash, no colour, no gradients. "
    "The three ornaments stand apart from each other with wide white space between them:\n"
    "1. On the left half: a square decorative initial block, as tall as half of the sheet, with a fine double "
    "ruled border line. Inside the border a dense engraved maritime ornament of rope, an anchor, sea waves, "
    "seaweed and a small lighthouse, all around a large EMPTY square of plain white paper in the middle (half "
    "the width of the block) where a letter will be printed later: the inner square must stay completely empty "
    "and white, no letter in it.\n"
    "2. Top right: a small oval tailpiece vignette: a coil of rope with a small anchor and a gull, finely "
    "engraved, fading out at the edges into white paper.\n"
    "3. Bottom right: a long, thin horizontal ornamental divider rule with a small knot of rope in the middle "
    "and swelling, tapering flourishes towards both ends.\n"
    "No tinted ground, no colour at all. The reference image only shows the engraving technique and the line weight: use the same technique, do not copy any of its content. "
    "Not a 3D render, not a painting, not a woodcut, no paper texture, no stains, no frame around the sheet."
)

MASK = (
    "A flat colour-code segmentation map of the reference image, for a game engine. Keep the exact composition, "
    "the exact positions, sizes and outlines of everything in the reference image; only replace the drawing by "
    "flat, uniform colour areas with hard edges, no lines, no hatching, no shading, no gradients, no "
    "anti-aliasing. Colour codes: the whole sky including clouds pure blue #0000FF; all open water of the sea "
    "and the harbour pure cyan #00FFFF; the two boats with their masts and rigging pure magenta #FF00FF; the lit "
    "window of the cottage pure yellow #FFFF00; the glass of the iron lantern pure orange #FF8000; the lamp at "
    "the top of the lighthouse pure red #FF0000; the chimney of the cottage pure green #00FF00; everything else "
    "(cottage, lighthouse tower, rocks, jetty, quay, barrels, crates, rope, lantern post) pure black #000000. "
    "No text, no labels, no legend. Image format: landscape 3:2."
)


def write(name, text):
    (SD / "prompts").mkdir(exist_ok=True)
    (SD / "prompts" / f"{name}.txt").write_text(text + "\n")
    return text


def main():
    which = sys.argv[1] if len(sys.argv) > 1 else "bg"
    jobs = []
    if which == "bg":
        p = "\n\n".join([BG_STYLE, BG_LAYOUT, SCENE, BG_ANIM, BG_ONLY, GUARDS, "Image format: landscape 3:2."])
        jobs.append({"out": f"{RAW}/bg.png", "size": "1536x1024", "prompt": write("bg", p)})
    elif which == "bg2":
        p = "\n\n".join([BG2_STYLE, BG2_LAYOUT, SCENE, BG_ANIM, BG_ONLY, GUARDS, "Image format: landscape 3:2."])
        jobs.append({"out": f"{RAW}/bg2.png", "size": "1536x1024", "prompt": write("bg2", p)})
    elif which == "figures":
        p = "\n\n".join([FIG_STYLE, BADGER, FIG_ISO, GUARDS, "Image format: landscape 3:2."])
        jobs.append({"out": f"{RAW}/walk.png", "size": "1536x1024", "prompt": write("walk", p),
                     "refs": ["styles/kupferstich/assets/ref/walk_layout.png", "shared/badger/master_sheet.png",
                              "styles/kupferstich/assets/ref/style_engraving.png"]})
        jobs.append({"out": f"{RAW}/ornaments.png", "size": "1536x1024",
                     "prompt": write("ornaments", ORN + "\n\n" + "No text, letters, numbers, signatures, "
                                     "watermarks or logos anywhere in the image.\n\nImage format: landscape 3:2."),
                     "refs": ["styles/kupferstich/assets/ref/style_engraving.png"]})
        jobs.append({"out": f"{RAW}/mask.png", "size": "1536x1024", "prompt": write("mask", MASK),
                     "refs": [f"{RAW}/bg2.png"], "ref_note": ""})
    elif which == "walk_small":
        p = "\n\n".join([FIG_SMALL, BADGER, FIG_ISO, GUARDS, "Image format: landscape 3:2."])
        jobs.append({"out": f"{RAW}/walk_small.png", "size": "1536x1024", "prompt": write("walk_small", p),
                     "refs": ["styles/kupferstich/assets/ref/walk_small_layout.png", "shared/badger/master_sheet.png",
                              "styles/kupferstich/assets/ref/style_engraving.png", f"{RAW}/walk.png"]})
    elif which == "mask":
        jobs.append({"out": f"{RAW}/mask.png", "size": "1536x1024", "prompt": write("mask", MASK),
                     "refs": [f"{RAW}/bg2.png"], "ref_note": ""})
    else:
        sys.exit("bg | bg2 | figures | walk_small | mask")
    out = SD / "assets" / f"jobs_{which}.json"
    out.write_text(json.dumps(jobs, indent=1, ensure_ascii=False))
    print(out)


if __name__ == "__main__":
    main()
