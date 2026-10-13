#!/usr/bin/env python3
"""Schreibt die Bildaufträge des Eintrags (Phase 1 laut PIPELINE.md → „Bildaufträge“).

Aufruf aus dem Projektordner:
    .venv/bin/python styles/anime-visual-novel/tools/make_jobs.py

Setzt jeden Prompt aus Stilblock + Motivblock (wörtlich aus data/motif.json) + Schutzregeln + Formatangabe
zusammen und schreibt
  assets/prompts/<name>.txt     lesbare Fassung jedes Prompts
  assets/image_jobs.json        Auftragsliste im Format von genimg.py --jobs, Prioritätsreihenfolge

Aufträge (höchstens 3):
  1. raw/sheet.png   Figurenblatt: der Dachs zweimal nebeneinander, gleiche Pose, links neutral, rechts freudig.
                     Referenzen: assets/ref_pair.png (Layout, aus tools/make_refs.py) und das Referenzblatt.
  2. raw/bg.png      Anime-Hintergrund mit großem Abendhimmel, Bühne für Figur und Textfenster.
  3. raw/faces.png   Bearbeitung von Auftrag 1 (gleiches Layout): links Augen zu und Mund offen (liefert
                     Blinzeln und Sprechen als getrennte Teile), rechts überrascht.
Auftrag 3 nimmt das Ergebnis von Auftrag 1 (sheet.png) als Bearbeitungsvorlage. Ursprünglich war das
Magenta-Original sheet.keyed-src.png vorgesehen, das genimg.py nur auf dem agy-Weg anlegt; tatsächlich kamen alle
drei Bilder über Codex mit echtem Alphakanal (keine keyed-src-Datei), und die Warteschlange lief Auftrag 3 mit
sheet.png. Das funktioniert auf beiden Wegen (bei agy ist sheet.png die freigestellte Fassung). Ein festes "backend": "agy" im Auftrag
wurde bewusst nicht gesetzt: tools/imagequeue.py prüft die agy-Sperre nur nach seinem eigenen --backend und
liefe bei gesperrtem agy und freiem Codex ohne Pause im Kreis.
"""
import json, pathlib

SD = pathlib.Path(__file__).resolve().parent.parent
ROOT = SD.parent.parent
REL = SD.relative_to(ROOT).as_posix()
MOTIF = json.loads((ROOT / "data" / "motif.json").read_text())
SCENE = MOTIF["scene"]["block_en"]
BG_ONLY = MOTIF["scene"]["background_only_en"]
CHAR = MOTIF["character"]["block_en"]
GUARDS = MOTIF["guards_en"]
SHEET = MOTIF["character"]["reference_sheet"]

# --- 1. Figurenblatt ------------------------------------------------------------------------------
SHEET_STYLE = (
    "Style: two character standing sprites for a Japanese-style visual novel, drawn as clean modern anime "
    "character art in a TV-anime cel look. Crisp, thin, even dark-brown line art with slightly tapered ends and a "
    "slightly thicker outer contour. Flat cel shading with exactly two tones per material: the base colour and one "
    "hard-edged shadow shape, plus a few small hard-edged highlights on the cap button, the nose and the eyes. A soft "
    "airbrushed pink blush on the cheeks is the only soft gradient. Large, glossy, expressive anime eyes with dark "
    "brown irises, one big white catchlight and one small one, clearly outlined so they read well inside the black "
    "face stripes. Simplified, rounded, appealing shapes; fur only as a few clean pointed tufts along the silhouette "
    "(cheeks, ears, elbows); the scarf knit suggested by a few clean lines. No fur texture, no fabric texture, no "
    "hatching, no grain. Even, neutral front lighting without cast shadows or scene light, so the sprites can be "
    "placed on any background. Not a photograph, not a 3D render, not a painterly or textured storybook "
    "illustration, not chibi, not watercolour."
)
SHEET_LAYOUT = (
    "Layout: exactly two figures side by side, the same character twice, each full body from the top of the cap "
    "to the feet and filling about nine tenths of the picture height, standing upright in front view and looking "
    "at the viewer, each centred in its half of the picture, the same size and the same baseline, with a clear gap of empty background between them. Both figures "
    "have exactly the same pose, body outline, clothes, head position and head angle: the parcel held under the arm "
    "on the left side of the picture, the other arm hanging relaxed, the satchel strap diagonally across the chest. "
    "Only the faces differ. Left figure: calm, friendly neutral expression, eyes open and looking at the viewer, "
    "eyebrows relaxed, mouth a small closed smile. Right figure: big happy smile, eyes closed into cheerful "
    "upward-curved arcs, eyebrows raised, mouth wide open in a laugh showing a little pink tongue, slightly stronger "
    "blush. No emote symbols, sweat drops, sparkles or motion lines (they are added separately in the game). Use "
    "the first attached image for the layout, pose, framing and size of both figures, and both attached images only "
    "for the character design: costume, colours of the clothes, face markings and body proportions. Line art, "
    "shading, eyes and level of detail follow this style description, not the references. Not a reference sheet "
    "with front, side and back views."
)

# --- 2. Hintergrund -------------------------------------------------------------------------------
BG_STYLE = (
    "Style: a background painting for a Japanese-style visual novel, like the hand-painted background art of a "
    "modern anime feature film. Clean, highly detailed 2D digital painting: crisp hard-edged shapes, sharp clean "
    "silhouettes, smooth clean colour gradients, small details (stones, planks, ropes, window frames) rendered "
    "precisely; no outlines. The sky is the main subject and fills the upper half of the picture: towering, "
    "sculpted cumulus clouds with crisp edges and long thin streaks of cirrus, the cloud undersides glowing peach, "
    "coral and pink from the sun that has just set, the cloud tops cool lavender and slate blue; a vivid gradient "
    "from deep ultramarine and violet at the top to warm orange and pale gold at the horizon; the first bright stars "
    "in the deep blue. Light: bright warm rim light and crisp edge highlights on clouds, roof edges, rocks and the "
    "lighthouse; cool blue-violet shadows; the calm sea mirrors the sky in long horizontal streaks. Saturated but "
    "harmonious colours, high clarity, strong contrast between warm light and cool shadow. Not a photograph, not a "
    "3D render, no photographic texture, no film grain, no depth-of-field blur, no lens flare, not an oil painting, "
    "not a watercolour, not a postcard."
)
BG_LAYOUT = (
    "Composition: eye-level view from the quay, a stage for a dialogue scene (a large character will stand in the "
    "middle and a dialogue box will cover the bottom quarter). The small stone cottage stands at the left edge "
    "(left 15 % of the width), the iron lantern on its wooden post just right of it at about 20 % of the width. "
    "The lighthouse on its rocky headland stands at about 84 % of the width, its lamp about one fifth of the picture "
    "height below the top edge. The middle of the picture (25 % to 62 % of the width) shows open quay, the calm sea, "
    "the horizon slightly below the middle of the picture and the big sky; the wooden jetty with the two boats runs "
    "out into the sea between 63 % and 78 % of the width. The lower quarter is plain paved quay with little detail. "
    "Effects are animated separately in the game, so do not paint them: the lighthouse lamp only as a small "
    "glowing spot without any beam, rays or halo, no smoke from the chimney, no birds, the lantern and the window "
    "lit but without a large glow, no sparkles on the water."
)
BG_REMINDER = ("In this picture the chimney shows no smoke and the lighthouse lamp has no beam: both are animated "
               "separately.")

# --- 3. Mimik-Bearbeitung -------------------------------------------------------------------------
FACES_EDIT = (
    "Edit the first attached image. It shows two character standing sprites for a Japanese-style visual novel, the "
    "same badger character twice in the same pose, drawn as clean modern anime character art (crisp thin dark-brown "
    "line art, flat two-tone cel shading with hard-edged shadows, soft pink blush) on a flat magenta background. "
    "Keep everything exactly as it is: both figures, their poses, outlines, sizes and positions in the picture, the "
    "head positions and head outlines, the ears, the cap, the clothes, scarf, satchel and parcel, all colours, the "
    "line art and the flat magenta background. Change only the eyes, eyebrows and mouths inside the two faces. "
    "Left figure: both eyes fully closed in a calm blink, each closed eye a single gently downward-curved line with "
    "a small lash flick at the outer corner, at the same place and width as the open eye and clearly visible on "
    "the dark face stripe; at the same time the mouth is open in the middle of speaking a word, a small rounded "
    "open mouth showing the dark mouth interior and a little pink tongue; eyebrows unchanged. Right figure: "
    "startled surprise, the eyes wide open and perfectly round with small pupils and bright white catchlights, the "
    "eyebrows raised high, the mouth a small open round shape. No emote symbols, sweat drops or motion lines. The "
    "second attached image is only the original design sheet of this character: use it for the face markings, "
    "ignore its layout and its drawing style. Not a photograph, not a 3D render, no painterly texture."
)

TRANSPARENT = "The figures are isolated on a fully transparent background."


def join(*parts):
    return "\n\n".join(p.strip() for p in parts if p)


JOBS = [
    {"name": "sheet", "out": f"{REL}/assets/raw/sheet.png", "size": "1536x1024",
     "refs": [f"{REL}/assets/ref_pair.png", SHEET],
     "prompt": join(SHEET_STYLE, SHEET_LAYOUT, CHAR, TRANSPARENT, GUARDS, "Image format: landscape 3:2.")},
    {"name": "bg", "out": f"{REL}/assets/raw/bg.png", "size": "1536x1024",
     "prompt": join(BG_STYLE, BG_LAYOUT, SCENE, BG_REMINDER, BG_ONLY, GUARDS, "Image format: landscape 3:2.")},
    {"name": "faces", "out": f"{REL}/assets/raw/faces.png", "size": "1536x1024",
     "refs": [f"{REL}/assets/raw/sheet.png", SHEET],
     "prompt": join(FACES_EDIT, CHAR, TRANSPARENT, GUARDS, "Image format: landscape 3:2.")},
]


def main():
    pdir = SD / "assets" / "prompts"
    pdir.mkdir(parents=True, exist_ok=True)
    out = []
    for j in JOBS:
        (pdir / f"{j['name']}.txt").write_text(j["prompt"] + "\n")
        job = {k: v for k, v in j.items() if k != "name"}
        out.append(job)
        print(f"{j['name']:6} {len(j['prompt']):5d} Zeichen  refs={j.get('refs', [])}")
    (SD / "assets" / "image_jobs.json").write_text(json.dumps(out, ensure_ascii=False, indent=1) + "\n")
    print(f"{REL}/assets/image_jobs.json: {len(out)} Aufträge")


if __name__ == "__main__":
    main()
