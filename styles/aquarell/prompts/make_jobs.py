#!/usr/bin/env python3
"""Schreibt die Bildaufträge des Eintrags "aquarell" nach assets/image_jobs.json (Format genimg.py --jobs, Pfade
relativ zum Projektordner, in Prioritätsreihenfolge). Prompt = Stilblock + Kompositions-/Layoutblock + Motivblock
(wörtlich aus data/motif.json) + Hinweise zu später animierten Teilen + Schutzregeln + Formatangabe.

    .venv/bin/python styles/aquarell/prompts/make_jobs.py [--print] [--fix]

Aufträge:
  1. raw/bg.png     Hintergrund 1536x1024, ohne Referenz
  2. raw/walk.png   Bogen 2x5: 8 Laufbilder, Stehen, Dreiviertel-Drehung. Referenzen: Blender-Layout (Posen),
                    Master-Sheet (Kostüm), raw/bg.png aus Auftrag 1 (Maltechnik und Palette)
  3. raw/front.png  Bogen 2x3 zur Kamera: Stehen, drei Winkposen, Blinzeln, Sprechen. Referenzen: Blender-Layout,
                    raw/walk.png aus Auftrag 2 (Stil der Figur), Master-Sheet
Die Layouts erzeugen blender/pose_layout.py und tools/make_layouts.py (assets/ref/).
"""
import json, pathlib, sys

ROOT = pathlib.Path(__file__).resolve().parents[3]
HERE = pathlib.Path(__file__).resolve().parent
S = "styles/aquarell"
RAW = f"{S}/assets/raw"
M = json.loads((ROOT / "data/motif.json").read_text())

# --- Hintergrund -----------------------------------------------------------------------------------------------
STYLE_BG = (
    "Traditional transparent watercolour painting on rough cold-pressed watercolour paper: a hand-painted "
    "background for a 2D narrative adventure game. Technique: loose wet-in-wet washes that bleed softly into one "
    "another, then a few transparent glazes laid over the dried washes; the white of the paper shines through every "
    "colour and is left completely unpainted for the brightest lights; hard, slightly darker pigment rims where a "
    "wash dried (tide lines, small blooms and backruns); visible paper grain and pigment granulation, especially in "
    "the blue and violet washes; a few dry-brush strokes on stone and wood. Strong simplification: large simple "
    "shapes, few objects, details only suggested with one or two brush marks, soft lost edges in the distance and a "
    "few crisp edges in front, no fine lines, no pen or ink outlines, no hatching. Limited palette of transparent "
    "pigments: ultramarine blue, indigo, quinacridone rose, burnt sienna, raw sienna and a little sap green; a dusk "
    "mood but light, airy values, nothing pitch black, shadows are transparent blue-violet glazes. It must look like "
    "a real watercolour painted by hand on paper: not a photograph, not a 3D render, not a digital painting, not oil "
    "or gouache, not a postcard, no heavy saturated sunset, no dramatic lighting effects."
)
COMPOSITION_BG = (
    "Composition for a wide game screen (the picture will be cropped a little at the top and bottom), eye-level side "
    "view across the harbour: the horizon lies a little below the middle of the picture. The cottage stands at the "
    "left edge, the lighthouse on its low rocky headland at about three quarters of the width, the jetty with the two "
    "boats in the middle distance between them, open sea at the right edge. The lighthouse is short and stout and "
    "its top stays well below the upper quarter of the picture, with open sky above it; the masts of the boats are "
    "short. The iron lantern on its wooden post stands at the back edge of the quay a little right of the middle of "
    "the picture. The lower fifth of the picture is a broad, plain, empty strip of quay paving across the full width, "
    "seen from slightly above, where characters will walk; the barrels, the crates and the rope stand at the back "
    "edge of the quay next to the water, not on this strip. The painting fills the whole sheet to all four edges (no "
    "white border, no vignette, no frame)."
)
ANIM_BG = (
    "Important for the game version: some things move in the game and are added later as separate animated layers, "
    "so paint them exactly as described here, even where the description above says otherwise. No smoke at all above "
    "the chimney: the chimney top stands clean against the sky. The lighthouse lamp only as a small warm spot of bare "
    "paper with a touch of yellow, without any light beam, rays or halo. The lit window and the lantern only as small "
    "warm spots, without large glows. The sky a soft wet-in-wet gradient with only a few faint, low cloud streaks "
    "near the horizon and no large clouds; the first stars only as a few tiny specks of white paper. The water calm, "
    "with only a few soft horizontal strokes and reflections. No birds."
)

# --- Figur: gemeinsamer Stilblock ------------------------------------------------------------------------------
STYLE_FIG = (
    "Painting technique: traditional transparent watercolour, as in a hand-painted picture book: each shape laid in "
    "with one or two transparent washes, soft wet-in-wet transitions inside the fur and the clothes, slightly darker "
    "pigment rims where a wash dried, a little pigment granulation, the lightest parts of fur and shirt very pale, "
    "almost white, only a few loose brush marks for fur, folds and the knitted scarf. No pen or ink outlines, no black "
    "contour lines, no hatching, no airbrush gradients, no glossy highlights. The colours of the figures are opaque against the background: the background colour "
    "never shows through or tints the figures. Clear, readable colours: cap and vest a "
    "clear dark green, the shirt cream, the scarf red, satchel and parcel warm brown, the fur dark grey-brown and "
    "creamy white, the broad black-and-white stripes of the face clearly readable, small dark eyes. Soft, even light "
    "from the upper left, mid-light values, no backlight, no rim light, no glow around the figure. It must look like "
    "a real watercolour painted by hand: not a 3D render, not a digital painting, not a plush toy, not a cartoon with "
    "outlines."
)
SHEET_END = (
    "Each figure isolated on a fully transparent background, with clear empty space between the figures; no ground, "
    "no cast shadow, no frame borders, no paper texture around the figures, nothing cut off at the edge of the sheet."
)

WALK_LAYOUT = (
    "Sprite sheet for a 2D side-view narrative game: ten figures of the same character, painted by hand in "
    "watercolour. The first reference image gives the exact layout and the exact poses: ten figures in two rows of "
    "five, all at the same scale, the feet of each row on the same baseline. Figures one to eight (in reading order) "
    "are a walk cycle to the right in strict side view; figure nine stands still in side view, both feet flat on the "
    "ground; figure ten has turned three-quarters towards the viewer. Copy every pose, the positions of both legs and "
    "feet, the arms, the parcel and the satchel, and the place and size of each figure exactly from the first "
    "reference; only the painting changes. The second reference image only shows the costume, the face and the "
    "proportions of the character: do not copy its drawing style, its outlines or its three-view layout. The third "
    "reference image only shows the watercolour technique and the palette of the game: do not copy anything "
    "of its content."
)
FRONT_LAYOUT = (
    "Sprite sheet for a 2D narrative game: six figures of the same character facing the viewer, painted by hand in "
    "watercolour. The first reference image gives the exact layout and the exact poses: six figures in two rows of "
    "three, all at the same scale, the feet of each row on the same baseline. Figure one stands facing the viewer, "
    "arms down. Figure two raises one arm sideways. Figure three waves with the arm raised high, the hand turned "
    "outwards. Figure four waves with the arm raised high, the hand turned inwards next to the head. Figure five is "
    "figure one with the eyes closed (blinking). Figure six is figure one with the mouth open as if speaking. Apart "
    "from the waving arm, the eyes and the mouth, all six figures are identical: the same body, face, costume and "
    "brush marks. Copy the poses, the place and the size of each figure exactly from the first reference; only the "
    "painting changes. The second reference image shows the same character already painted in the target "
    "watercolour style: match its painting technique, colours and level of detail exactly. The third reference image "
    "only shows the costume, the face and the proportions: do not copy its drawing style, its outlines or its "
    "three-view layout."
)


# --- Nachbesserung nach Prüfung 1 (direkt mit genimg.py, nicht über die Warteschlange) ---------------------------
# Die Figur aus den Aufträgen 2/3 kam als deckende Filz-/Plüsch-Gouache. Neu: flache Lasuren je Kostümteil,
# Papierweiß in hellen Flächen, harte Trockenränder; ausdrücklich kein Fell, kein Filz, keine runde 3D-Schattierung.
# Stilreferenz ist ein Ausschnitt mit echter Lasur aus raw/bg.png (assets/ref/wash_style.png, tools/make_style_ref.py)
# statt des ganzen Hintergrunds; das Blender-Layout bleibt erste Referenz, das Master-Sheet nur für das Kostüm.
STYLE_FIG_V2 = (
    "Painting technique: traditional transparent watercolour on white cold-pressed paper, simple and flat like a "
    "quick hand-painted picture-book sketch. Each costume part one or two flat transparent washes: one flat wash of "
    "its local colour and at most one second flat, hard-edged glaze for the shadow side. White paper left visible "
    "inside light areas: the lightest parts of the shirt, the white face stripes and the white fur, and small "
    "highlights on the cap, the parcel and the satchel stay bare paper. Hard pigment rims at wash edges: every wash "
    "ends in a thin, slightly darker line of pigment where it dried; in places a narrow gap of bare paper between "
    "two neighbouring washes. A little pigment granulation in the dark grey fur and in the green. No fur texture, no "
    "individual hairs, no felt, no knitted or woven texture, no soft rounded 3D shading, no plush, no smooth "
    "gradients, no airbrush, no glossy highlights. No pen or ink outlines, no black contour lines, no hatching. "
    "The figures are cut out of the painted paper: everything inside each silhouette is fully opaque, and bare "
    "paper inside a figure shows as solid warm white paper colour, never as a transparent hole. Clear, readable "
    "colours: cap and vest a clear dark green, the shirt pale cream, the scarf red, satchel and parcel warm brown, "
    "the fur dark grey-brown and creamy white, the broad black-and-white stripes of the face clearly readable, small "
    "dark eyes. Light from the upper left, mid-light values, no backlight, no rim light, no glow around the figure. "
    "It must look like a real watercolour painted by hand: not a 3D render, not a digital painting, not gouache, "
    "not a plush toy, not a cartoon with outlines."
)
WALK_LAYOUT_V2 = WALK_LAYOUT.replace(
    "only the painting changes.",
    "only the painting changes. The first reference is a plain 3D render: take only the layout and the poses from "
    "it, never its smooth rounded shading or its plastic 3D look.").replace(
    "The third reference image only shows the watercolour technique and the palette of the game: do not copy anything "
    "of its content.",
    "The third reference image shows only the watercolour technique of the game (flat transparent washes with hard "
    "pigment rims and granulation on rough paper, as on its paving stones, crates and barrels): paint the figures "
    "with exactly this technique, but do not copy any of its content or its brown and violet colours.")
FRONT_LAYOUT_V2 = FRONT_LAYOUT.replace(
    "Figure five is figure one with the eyes closed (blinking).",
    "Figure five is figure one with both eyes closed (a blink: both eyes shut, each a short curved line, "
    "symmetric). In figures one, two, three, four and six both eyes are open.").replace(
    "only the painting changes.",
    "only the painting changes. The first reference is a plain 3D render: take only the layout and the poses from "
    "it, never its smooth rounded shading or its plastic 3D look.").replace(
    "match its painting technique, colours and level of detail exactly.",
    "match its painting technique (flat transparent washes, bare paper in the light areas, hard pigment rims, no fur "
    "texture), colours and level of detail exactly.")


def fig_prompt_v2(layout):
    return "\n\n".join([layout, STYLE_FIG_V2, M["character"]["block_en"], SHEET_END, M["guards_en"],
                        "Image format: landscape 3:2."])


def fix_jobs():
    return [
        {"out": f"{RAW}/walk_v2.png", "size": "1536x1024", "prompt": fig_prompt_v2(WALK_LAYOUT_V2),
         "refs": [f"{S}/assets/ref/walk_layout.png", M["character"]["reference_sheet"],
                  f"{S}/assets/ref/wash_style.png"]},
        {"out": f"{RAW}/front_v2.png", "size": "1536x1024", "prompt": fig_prompt_v2(FRONT_LAYOUT_V2),
         "refs": [f"{S}/assets/ref/front_layout.png", f"{RAW}/walk_v2.png", M["character"]["reference_sheet"]]},
    ]


def bg_prompt():
    return "\n\n".join([STYLE_BG, COMPOSITION_BG, M["scene"]["block_en"], ANIM_BG, M["scene"]["background_only_en"],
                        M["guards_en"], "Image format: landscape 3:2."])


def fig_prompt(layout):
    return "\n\n".join([layout, STYLE_FIG, M["character"]["block_en"], SHEET_END, M["guards_en"],
                        "Image format: landscape 3:2."])


def jobs():
    return [
        {"out": f"{RAW}/bg.png", "size": "1536x1024", "prompt": bg_prompt(), "refs": []},
        {"out": f"{RAW}/walk.png", "size": "1536x1024", "prompt": fig_prompt(WALK_LAYOUT),
         "refs": [f"{S}/assets/ref/walk_layout.png", M["character"]["reference_sheet"], f"{RAW}/bg.png"]},
        {"out": f"{RAW}/front.png", "size": "1536x1024", "prompt": fig_prompt(FRONT_LAYOUT),
         "refs": [f"{S}/assets/ref/front_layout.png", f"{RAW}/walk.png", M["character"]["reference_sheet"]]},
    ]


if __name__ == "__main__":
    fix = "--fix" in sys.argv          # Nachbesserung: assets/fix_jobs.json (einzeln an genimg.py --jobs geben)
    js = fix_jobs() if fix else jobs()
    out = ROOT / S / ("assets/fix_jobs.json" if fix else "assets/image_jobs.json")
    out.write_text(json.dumps(js, ensure_ascii=False, indent=1) + "\n")
    print("ok", out.relative_to(ROOT), len(js), "Aufträge")
    if "--print" in sys.argv:
        for j in js:
            print(f"\n=== {j['out']}  {j['size']}  refs={j['refs']}\n{j['prompt']}")
