#!/usr/bin/env python3
"""Schreibt die Bildaufträge assets/image_jobs.json (Format genimg.py --jobs, Prioritätsreihenfolge) und die
Prompts als Text (prompts/<name>.txt). Aufbau je Prompt: Stilblock + Motivblock (wörtlich aus data/motif.json)
+ background_only_en + Schutzregeln + Formatangabe.

    .venv/bin/python styles/ega-adventure/prompts/make_jobs.py

Auftrag 1  bg_flat.png   Hintergrund in flachen EGA-Farbflächen, sauber in hoher Auflösung gezeichnet; wird von
                         scripts/process_raw.py auf 160×168 Doppelpixel gerastert und in Zeichenbefehle zerlegt.
Auftrag 2  bg_lines.png  Strichvorlage: dasselbe Bild (Referenz = Ergebnis von Auftrag 1) als geschlossene schwarze
                         Linien auf Weiß, wie die Vorzeichnung, die in den Vorbildern Linie für Linie nachgezogen und
                         dann flutgefüllt wurde. Liefert saubere Flächengrenzen; die Farben kommen aus Auftrag 1.
"""
import json, pathlib

HERE = pathlib.Path(__file__).resolve().parent
SD = HERE.parent
ROOT = HERE.parents[2]
motif = json.loads((ROOT / "data/motif.json").read_text())
scene = motif["scene"]
RAW = "styles/ega-adventure/assets/raw"

PALETTE = ("only these 16 fixed, fully saturated colours and nothing in between: black, dark blue, dark green, "
           "dark cyan, dark red, dark magenta, brown, light grey, dark grey, bright blue, bright green, bright cyan, "
           "bright red, bright magenta, yellow, white")

LAYOUT = (
    "Composition for a wide panorama crop: all important content lies between 12% and 88% of the image height; "
    "the strips above and below may be cut away. The harbour-master's cottage stands at the far left, the jetty "
    "with the two moored boats in the middle, the lighthouse on its rocky headland at the far right; the horizon "
    "lies at about 40% of the image height. The quay is a flat walkable floor of plain light grey stone paving "
    "with dark grey joints across the whole lower third, its front edge running parallel to the bottom of the "
    "image. The stack of crates and the coil of rope stand at the back of the quay beside the cottage. The iron "
    "lantern on its tall wooden post and the two barrels stand in the foreground at the very front of the quay on "
    "the right half, their bases at about 84% of the image height; between them and the water lies a wide free "
    "strip of plain paving."
)

ANIMATED = (
    "Light is shown only by colour: the cottage window and the lantern glass are plain yellow areas; the "
    "lighthouse lamp is only a small yellow spot without any beam or rays, and no smoke rises from the chimney "
    "(lamp light and smoke are animated separately)."
)

STYLE_FLAT = (
    "Background picture for a mid-1980s PC parser adventure game with 16-colour EGA graphics, redrawn cleanly at "
    "high resolution so that it can be traced into lines and flood fills afterwards. Palette: " + PALETTE + ". "
    "Every shape is filled with exactly one flat, solid colour: no gradients, no shading, no highlights, no "
    "shadows, no texture, no noise, no dithering, no soft or blurred edges, no glow, no haze. Drawn like an early "
    "computer picture built from straight lines and flood fills: simple angular shapes with hard straight edges and "
    "stair-like diagonals, large plain areas, few objects, each object in two or three flat colours; details such "
    "as planks, roof tiles, paving joints, window bars and waves are bold solid lines in a darker or lighter "
    "colour, never hairlines. The dusk sky is a stack of flat horizontal colour bands with hard borders: black at "
    "the top with a few single white star dots, then dark blue, dark magenta, bright red, and a yellow band right "
    "at the horizon; the low clouds are flat elongated shapes in dark magenta and dark blue. The sea is one flat "
    "dark blue area with a few short horizontal strokes in bright blue, bright cyan and yellow. Naive flat side "
    "view like a stage set: perfectly horizontal horizon, no perspective depth, no vanishing lines, no "
    "foreshortening. Every shape must be big and simple: the picture will be reduced to 160 by 168 pixels, so no "
    "detail is smaller than one hundredth of the image width. " + LAYOUT + " " + ANIMATED + " "
    "Not a painting, not a modern vector illustration, not modern detailed pixel art, not a photograph, not a 3D "
    "render, not a postcard."
)

STYLE_LINES = (
    "Line-art tracing sheet for a mid-1980s PC adventure game background. Redraw the attached reference picture as "
    "a clean black line drawing on plain white paper: keep its composition and every shape, position and size "
    "exactly as in the reference, but ignore its colours. The sheet will be traced line by line on a drawing tablet "
    "and then flood-filled with colour, so every area that has its own colour in the reference is enclosed by a "
    "closed outline without gaps: each band of the sky, each cloud, the sea, the headland, the lighthouse and its "
    "red band, the cottage wall, roof, door and window, each boat, the jetty, the paving, the crates, the barrels, "
    "the lantern post and the lantern glass. Only pure black lines of one constant, bold width on pure white: no "
    "colour, no grey, no filled black areas, no shading, no hatching, no texture, no stippling, no sketchy or "
    "doubled lines. Few, simple, angular shapes with straight lines wherever possible; small details such as "
    "planks, paving joints and waves as single straight strokes; stars as small black dots. The lighthouse lamp is "
    "only a small closed outline without any beam or rays, and there is no smoke above the chimney. Not a colouring "
    "book with decorative detail, not a comic, not an engraving."
)


def prompt(style):
    return "\n\n".join([style, scene["block_en"], scene["background_only_en"], motif["guards_en"],
                        "Image format: landscape 3:2."])


jobs = [
    {"out": f"{RAW}/bg_flat.png", "size": "1536x1024", "prompt": prompt(STYLE_FLAT)},
    {"out": f"{RAW}/bg_lines.png", "size": "1536x1024", "prompt": prompt(STYLE_LINES), "refs": [f"{RAW}/bg_flat.png"]},
]
for j in jobs:
    (HERE / f"{pathlib.Path(j['out']).stem}.txt").write_text(j["prompt"] + "\n")
(SD / "assets").mkdir(exist_ok=True)
(SD / "assets/image_jobs.json").write_text(json.dumps(jobs, indent=1, ensure_ascii=False) + "\n")
print("ok", [j["out"] for j in jobs])
