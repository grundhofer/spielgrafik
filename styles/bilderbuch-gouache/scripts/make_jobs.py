#!/usr/bin/env python3
"""Schreibt die Bildaufträge des Eintrags "bilderbuch-gouache" (Format genimg.py --jobs, Pfade relativ zum
Projektordner) und legt jeden Prompt zusätzlich als Text unter assets/prompts/<name>.txt ab.

    .venv/bin/python styles/bilderbuch-gouache/scripts/make_jobs.py [--print]

Prompt = Stilblock + Kompositions-/Layoutblock + Motivblock (wörtlich aus data/motif.json) + Hinweise zu später
animierten Teilen + Schutzregeln + Formatangabe.

Aufträge (direkt mit genimg.py erzeugt, Reihenfolge = Abhängigkeit):
  1. raw/bg.png     Hintergrund 1536x1024 ohne Boote, Rauch, Lichtschein; keine Referenz
  2. raw/walk.png   Bogen 2x5: 8 Laufbilder, Stehen, Dreiviertel-Drehung. Referenzen: Blender-Layout (Posen),
                    Master-Sheet (Kostüm), raw/bg.png (Maltechnik und Palette)
  3. raw/boats.png  zwei Boote als Sprites. Referenz: raw/bg.png (Maltechnik und Palette)
  4. raw/front.png  Bogen 2x3 zur Kamera: Stehen, drei Winkposen, Blinzeln, Sprechen. Referenzen: Blender-Layout,
                    raw/walk.png (Stil der Figur), Master-Sheet
Die Layouts erzeugen blender/pose_layout.py und scripts/make_layouts.py (assets/ref/).
"""
import json, pathlib, sys

ROOT = pathlib.Path(__file__).resolve().parents[3]
S = "styles/bilderbuch-gouache"
RAW = f"{S}/assets/raw"
M = json.loads((ROOT / "data/motif.json").read_text())

# --- Hintergrund -------------------------------------------------------------------------------------------------
STYLE_BG = (
    "Hand-painted illustration from a classic children's picture book, painted with opaque gouache on warm off-white "
    "watercolour paper. Matte, chalky, fully opaque paint laid down in flat colour shapes with visible brush marks; "
    "dry-brush edges where the paper grain shows through; lighter colours painted on top of darker ones; fine flecks "
    "of paper texture everywhere. Simple, rounded, friendly shapes for young children: soft round cloud shapes, a "
    "plump, slightly leaning lighthouse, a small cottage with soft wobbly walls and a rounded roof, round smooth "
    "rocks, naive, slightly flattened perspective. Few large objects and very little small detail: the stones of the "
    "quay only hinted with a few loose rounded dabs, no fine rigging, no fine wood grain, no flowers. Warm limited "
    "palette of mixed gouache colours: apricot, peach and coral glow along the horizon, warm dusty teal and deep warm "
    "blue in the upper sky and the sea, ochre, terracotta, sage green and cream on the buildings; the darkest colour "
    "is a warm deep blue-violet, never black. Soft, calm dusk light with gentle contrast. No black outlines. Not a "
    "photograph, not a 3D render, not smooth digital airbrush, not a detailed postcard, not transparent watercolour, "
    "not an oil painting."
)
COMPOSITION_BG = (
    "Composition for a fixed side-view adventure game screen. The picture will be cropped to a wide 16:9 format: "
    "the top 8% and the bottom 8% are cut off, so keep everything important inside the middle band. Horizon at about "
    "46% of the picture height. The stone quay runs as one continuous, level band across the whole width of the "
    "picture: its back edge at the water runs straight and level at about 70% of the picture height, and its flat "
    "paved top, seen from slightly above, fills the picture from there down to the bottom edge; this broad strip is "
    "free and walkable from left to right. On the left (left fifth of the width) the cottage stands on the quay, its "
    "chimney top at about 22% of the picture height. On the right the rocky headland with the lighthouse at about 82% "
    "of the width, the top of the lighthouse at about 18% of the picture height. The short wooden jetty starts from "
    "the back edge of the quay at about 45% of the width and leads out into the water. The two barrels and the coil "
    "of rope stand close to the cottage, the stack of crates near the right edge, the lantern post at the back edge "
    "of the quay at about 62% of the width; the middle of the quay stays free. The upper middle of the sky, between "
    "25% and 72% of the width and down to about 33% of the picture height, is a calm, almost empty area of flat "
    "colour with only a few small stars: the story text of the page will be placed there."
)
ANIM_BG = (
    "Important for the game version: some things move in the game and are added later as separate animated "
    "layers, so paint them exactly as described here, even where the description above says otherwise. Leave out "
    "the two fishing boats: they are painted separately and animated as sprites, so the water on both sides of the "
    "jetty stays empty. The lighthouse lamp only as a small warm glowing spot without any beam, the lantern only as "
    "a small warm spot without a halo, the window warm and lit, no smoke at all above the chimney (smoke and lights "
    "are animated separately). No birds."
)

# --- Figuren: gemeinsamer Stilblock ---------------------------------------------------------------------------------
STYLE_FIG = (
    "Painting technique: opaque gouache as in a classic hand-painted children's picture book, the same paint, paper "
    "grain and warm palette as the background of the game. Every costume part is a flat shape of fully opaque, matte, "
    "chalky paint in one clear colour, with only one or two lighter or darker opaque brush strokes to show the form; "
    "visible brush marks inside the colour shapes, slightly dry-brushed, soft, slightly wobbly edges. Simple, rounded, "
    "friendly shapes for young children: a plump, round body, short round legs, small round paws, a soft rounded "
    "head and muzzle. The fur is smooth flat colour with a few brush marks, the scarf a flat red shape with the "
    "knitting only hinted by a few strokes. No fur texture, no individual hairs, no felt or plush look, no knitted "
    "texture, no soft rounded 3D shading, no airbrush gradients, no glossy highlights, no black outlines. Clear, "
    "warm, readable colours: cap and vest a clear dark green, the shirt cream, the scarf red, satchel and parcel warm "
    "brown, the fur warm dark grey and creamy white, the broad dark-and-white stripes of the face clearly readable, "
    "small dark eyes. Soft, even light from the upper left, mid-light values, no backlight, no rim light, no glow "
    "around the figure. It must look like a real gouache painting made by hand: not a 3D render, not a digital "
    "painting, not a plush toy, not a cartoon with outlines."
)
SHEET_END = (
    "Each figure isolated on a fully transparent background, with clear empty space between the figures; no ground, "
    "no cast shadow, no frame borders, no paper texture around the figures, nothing cut off at the edge of the sheet."
)
WALK_LAYOUT = (
    "Sprite sheet for a 2D side-view narrative game: ten figures of the same character, painted by hand in gouache. "
    "The first reference image gives the exact layout and the exact poses: ten figures in two rows of five, all at "
    "the same scale, the feet of each row on the same baseline. Figures one to eight (in reading order) are a walk "
    "cycle to the right in strict side view; figure nine stands still in side view, both feet flat on the ground; "
    "figure ten has turned three-quarters towards the viewer. Copy every pose, the positions of both legs and feet, "
    "the arms, the parcel and the satchel, and the place and size of each figure exactly from the first reference; "
    "only the painting changes. The first reference is a plain 3D render: take only the layout and the poses from "
    "it, never its smooth shading or its plastic 3D look. The second reference image only shows the costume, the "
    "face and the proportions of the character: do not copy its drawing style, its outlines or its three-view "
    "layout. The third reference image shows the gouache technique and the palette of the game: paint the figures "
    "with exactly this technique, but do not copy any of its content."
)
FRONT_LAYOUT = (
    "Sprite sheet for a 2D narrative game: six figures of the same character facing the viewer, painted by hand in "
    "gouache. The first reference image gives the exact layout and the exact poses: six figures in two rows of "
    "three, all at the same scale, the feet of each row on the same baseline. Figure one stands facing the viewer, "
    "arms down. Figure two raises one arm sideways. Figure three waves with the arm raised high, the hand turned "
    "outwards. Figure four waves with the arm raised high, the hand turned inwards next to the head. Figure five is "
    "figure one with both eyes closed (a blink: both eyes shut, each a short curved line, symmetric). Figure six is "
    "figure one with the mouth open as if speaking. In figures one, two, three, four and six both eyes are open. "
    "Apart from the waving arm, the eyes and the mouth, all six figures are identical: the same body, face, costume "
    "and brush marks. Copy the poses, the place and the size of each figure exactly from the first reference; only "
    "the painting changes. The first reference is a plain 3D render: take only the layout and the poses from it, "
    "never its smooth shading or its plastic 3D look. The second reference image shows the same character already "
    "painted in the target gouache style: match its painting technique, colours, proportions and level of detail "
    "exactly. The third reference image only shows the costume, the face and the proportions: do not copy its "
    "drawing style, its outlines or its three-view layout."
)

# --- Boote ---------------------------------------------------------------------------------------------------------
BOATS = (
    "Two small wooden fishing boats as separate sprites for a 2D picture-book game, painted by hand in opaque gouache "
    "in exactly the technique, paper grain, warm palette and level of simplification of the reference image (the "
    "background of the same game): flat opaque colour shapes with visible brush marks and dry-brush edges, simple, "
    "rounded, friendly shapes for young children, no black outlines. Both boats seen from the side and a little from "
    "above, as boats moored in calm water look from a harbour quay, bow to the right, both at the same scale and "
    "side by side with clear empty space between them, each about 40% of the width of the sheet. Boat one (left): a "
    "plump, round-bellied wooden fishing boat with a terracotta-red hull, a cream stripe below the gunwale, a tiny "
    "cream wheelhouse with one small square window and a short, thick mast. Boat two (right): a slightly smaller "
    "open fishing boat with a dusty teal hull, an ochre stripe below the gunwale, a short, thick mast and one "
    "furled ochre sail. At most two simple lines of rigging per boat, no fine detail, no nets, no figures, no text "
    "or numbers on the hulls. Each hull ends at the bottom in a straight horizontal waterline: only the part above "
    "the water is painted, nothing below the waterline, no water, no reflection, no ripples. Each boat isolated on a "
    "fully transparent background; no ground, no cast shadow, no frame, nothing cut off at the edge of the sheet."
)


def bg_prompt():
    return "\n\n".join([STYLE_BG, COMPOSITION_BG, M["scene"]["block_en"], ANIM_BG, M["scene"]["background_only_en"],
                        M["guards_en"], "Image format: landscape 3:2."])


def fig_prompt(layout):
    return "\n\n".join([layout, STYLE_FIG, M["character"]["block_en"], SHEET_END, M["guards_en"],
                        "Image format: landscape 3:2."])


def boats_prompt():
    return "\n\n".join([BOATS, M["guards_en"], "Image format: landscape 3:2."])


def jobs():
    sheet = M["character"]["reference_sheet"]
    return {
        "bg": {"out": f"{RAW}/bg.png", "size": "1536x1024", "prompt": bg_prompt(), "refs": []},
        "walk": {"out": f"{RAW}/walk.png", "size": "1536x1024", "prompt": fig_prompt(WALK_LAYOUT),
                 "refs": [f"{S}/assets/ref/walk_layout.png", sheet, f"{RAW}/bg.png"]},
        "boats": {"out": f"{RAW}/boats.png", "size": "1536x1024", "prompt": boats_prompt(),
                  "refs": [f"{RAW}/bg.png"]},
        "front": {"out": f"{RAW}/front.png", "size": "1536x1024", "prompt": fig_prompt(FRONT_LAYOUT),
                  "refs": [f"{S}/assets/ref/front_layout.png", f"{RAW}/walk.png", sheet]},
    }


if __name__ == "__main__":
    js = jobs()
    pdir = ROOT / S / "assets/prompts"
    pdir.mkdir(parents=True, exist_ok=True)
    for name, j in js.items():
        (pdir / f"{name}.txt").write_text(j["prompt"] + "\n")
        (pdir / f"job_{name}.json").write_text(json.dumps([j], ensure_ascii=False, indent=1) + "\n")
    (pdir / "job_walk_boats.json").write_text(json.dumps([js["walk"], js["boats"]], ensure_ascii=False, indent=1)
                                              + "\n")
    print("ok", len(js), "Aufträge in", pdir.relative_to(ROOT))
    if "--print" in sys.argv:
        for n, j in js.items():
            print(f"\n=== {n}: {j['out']}  {j['size']}  refs={j['refs']}\n{j['prompt']}")
