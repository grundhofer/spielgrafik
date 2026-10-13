#!/usr/bin/env python3
"""Prompts für parallax-2-5d aus Bausteinen + data/motif.json (Motiv-, Figuren-, Schutzblock wörtlich).

Schreibt assets/prompts/{bg,depth,badger,plate}.txt, assets/ref/badger_layout.png (Pose-Vorlage auf Magenta)
und assets/prompts/jobs_*.json für tools/genimg.py --jobs.

    .venv/bin/python styles/parallax-2-5d/tools/prompts.py
"""
import json, pathlib
from PIL import Image

S = pathlib.Path(__file__).resolve().parent.parent
ROOT = S.parent.parent
M = json.loads((ROOT / "data/motif.json").read_text())
P = S / "assets/prompts"
REF = S / "assets/ref"
RAW = S / "assets/raw"

BG_STYLE = (
    "A finished painted background for a 2D narrative adventure game: a single digital painting with visible, "
    "confident brushwork in the manner of traditional gouache and oil sketching, painterly edges, simplified "
    "shapes, rich atmospheric perspective and a limited dusk palette of deep blue, violet and teal with warm orange "
    "accents only at the horizon, in the lit window and in the lamps. "
    "The picture is designed for a slow camera move in depth, so it is built from clearly separated depth planes "
    "with clean, readable silhouettes: every object stands out from what lies behind it by a clear change of value "
    "and colour (no ink outlines), and there is no fog, mist or haze blurring the edges between near and far objects. "
    "Eye-level view from the quay, as if standing on it: the camera is about two metres above the paving and looks "
    "straight out to sea, the horizon is a straight level line at 40 % of the picture height from the top. "
    "Composition from near to far: the nearest things are two barrels, a stack of crates and a coil of rope standing "
    "on the quay at the lower right, a few metres from the viewer, clearly in front of the sea; the open paving of "
    "the quay fills the lower middle of the picture and stays completely free (game characters walk there later); "
    "the iron lantern on its wooden post stands on the quay at about 40 % of the picture width in the middle ground; "
    "the harbour-master's cottage stands on the quay in the left third, its front facing the viewer, a little behind "
    "the walking area; the wooden jetty reaches out into the water in the centre with the two boats moored beside it; "
    "farther away on the right a rocky headland with the lighthouse at about 80 % of the picture width; behind "
    "everything the calm open sea, distant islands at the horizon and the sky. "
    "Keep every object at least 6 % away from the picture edges: the frame will be cropped and moved. "
    "Effects that the game animates are not painted: the lighthouse lamp only as a small glowing spot without any "
    "beam, rays or halo, no smoke from the chimney, no birds, no lens flare, the lantern glass glows with only a "
    "very small soft glow around it. "
    "Not a photograph, not a 3D render, not a postcard, not a cartoon with ink outlines, no heavy fog."
)

DEPTH = (
    "Turn the reference painting into its depth map. Output a grayscale depth map of exactly the same picture: "
    "identical composition, framing, perspective, object positions and object outlines, aligned pixel for pixel "
    "with the reference painting, same image size. Encoding: brightness means nearness. The nearest things (the "
    "quay paving at the bottom edge and the barrels, crates and rope at the lower right) are white or very light "
    "grey; everything gets gradually darker with distance; the horizon line and the distant islands are nearly "
    "black; the whole sky including clouds and stars is pure black. Surfaces that recede from the viewer (the quay "
    "paving, the sea surface, the jetty planks) are smooth continuous gradients that get darker toward the "
    "horizon. Every standing object (cottage, chimney, lantern and its post, barrels, crates, rope coil, boats, "
    "masts, jetty posts, headland, lighthouse) is a solid shape with a smooth tone that matches its distance, a "
    "little lighter on parts that reach toward the viewer, with crisp sharp edges exactly along the silhouette of "
    "the object in the painting, and a clear step in brightness wherever a nearer object overlaps something farther "
    "away. Thin things like the masts, ropes and the lantern post keep their exact position and width. "
    "No colours, no texture, no brush strokes, no lighting, no shadows, no glow, no outlines, no text: a clean, "
    "noise-free depth image like the output of a depth-estimation network. Image format: landscape 3:2."
)

PLATE = (
    "Edit the reference painting into its clean background plate for a 2.5D camera move. Output exactly the same "
    "painting with the same size, framing, perspective, horizon line, colours, light and brushwork, aligned pixel for "
    "pixel with the reference, but with these objects removed: the harbour-master's cottage with its chimney, plants "
    "and lamp, the lantern on its wooden post, the wooden jetty with all its posts and ropes, the two boats with their "
    "masts and rigging, the barrels, the crates, the coil of rope and the bollard. Where an object is removed, paint "
    "what would be seen behind it, continuing the surroundings seamlessly in the same painterly technique: the sky "
    "and clouds continue behind the cottage and the lantern, the calm sea with its horizontal ripples and reflections "
    "continues where the boats and the jetty were, and the stone paving of the quay with its edge along the water "
    "continues where the barrels, crates and the cottage stood. Keep the warm reflections of the evening light on "
    "the wet paving and on the water where they are. Keep unchanged: the sky, the stars, the distant islands, the sea, "
    "the rocky headland with the white lighthouse with the red band and its small house, the open quay paving. "
    "Do not add anything new, no people, no animals, no birds, no boats."
)

BADGER = (
    "Repaint the character of the first reference image in exactly the same pose, size and position on the canvas: "
    "a stout badger courier walking to the right, seen from the side, mid-stride with the near leg straight under "
    "the body and the far leg lifted behind. Keep the silhouette, the pose of the legs and arms, the parcel under "
    "the arm, the satchel, the scarf ends, the cap and every costume detail where they are. "
    "Change only the painting technique: paint it in the technique of the second reference image (a painted "
    "harbour at dusk for a narrative adventure game): visible confident brushwork like gouache and oil sketching, "
    "simplified shapes, a few clear value steps, painterly edges, only a little fine fur detail. No dark ink "
    "outlines around the figure or inside it: shapes are separated by changes of value and colour like the painted "
    "objects in the second reference image. No cel shading, no 3D render look, no plastic shading, no comic look. "
    "The outer silhouette stays clear, simple and readable. Light: soft, even, slightly cool dusk light from above, "
    "mid values; no strong light from one side and no rim light (the game adds the lights). The dark green cap and "
    "vest stay clearly green, the scarf red, the cream shirt light, the black-and-white face stripes and the eye "
    "readable. The third reference image is only a check for the costume and its colours: do not copy its layout, "
    "its several views or its drawing style. "
    + M["character"]["block_en"]
    + " One single figure, isolated on a fully transparent background, no ground, no shadow."
)


def bg_prompt():
    s = M["scene"]
    return "\n".join([BG_STYLE, s["block_en"], s["background_only_en"], M["guards_en"],
                      "Image format: landscape 3:2."])


def depth_prompt():
    return "\n".join([DEPTH, M["guards_en"]])


def plate_prompt():
    return "\n".join([PLATE, M["guards_en"], "Image format: landscape 3:2."])


def badger_prompt():
    return "\n".join([BADGER, M["guards_en"], "Image format: square 1:1."])


def layout_ref():
    """Bild 3 (Durchgang) aus shared/badger/walk_painted.png auf Magenta, 1024×1024, wie bei painterly-digital."""
    sheet = Image.open(ROOT / "shared/badger/walk_painted.png").convert("RGBA")
    fig = sheet.crop((741, 100, 1062, 660))
    k = 830 / fig.height
    fig = fig.resize((round(fig.width * k), round(fig.height * k)), Image.LANCZOS)
    canvas = Image.new("RGBA", (1024, 1024), (255, 0, 255, 255))
    canvas.alpha_composite(fig, ((1024 - fig.width) // 2, 1024 - 70 - fig.height))
    REF.mkdir(parents=True, exist_ok=True)
    canvas.convert("RGB").save(REF / "badger_layout.png")


def main():
    P.mkdir(parents=True, exist_ok=True)
    (P / "bg.txt").write_text(bg_prompt())
    (P / "depth.txt").write_text(depth_prompt())
    (P / "badger.txt").write_text(badger_prompt())
    layout_ref()
    rel = lambda p: str(p.relative_to(ROOT))
    (P / "jobs_bg.json").write_text(json.dumps([
        {"out": rel(RAW / "bg.png"), "size": "1536x1024", "prompt": bg_prompt()}], indent=1))
    (P / "jobs_depth_badger.json").write_text(json.dumps([
        {"out": rel(RAW / "depth.png"), "size": "1536x1024", "prompt": depth_prompt(),
         "refs": [rel(RAW / "bg.png")], "ref_note": ""},
        {"out": rel(RAW / "badger.png"), "size": "1024x1024", "prompt": badger_prompt(),
         "refs": [rel(REF / "badger_layout.png"), rel(RAW / "bg.png"), "shared/badger/master_sheet.png"]},
    ], indent=1))
    (P / "plate.txt").write_text(plate_prompt())
    (P / "jobs_plate.json").write_text(json.dumps([
        {"out": rel(RAW / "plate.png"), "size": "1536x1024", "prompt": plate_prompt(),
         "refs": [rel(RAW / "bg.png")], "ref_note": ""}], indent=1))
    for f in sorted(P.glob("*.txt")):
        print(f.name, len(f.read_text()), "Zeichen")


if __name__ == "__main__":
    main()
