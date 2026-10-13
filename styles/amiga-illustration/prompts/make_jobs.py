#!/usr/bin/env python3
"""Schreibt assets/image_jobs.json (Format genimg.py --jobs) für die zentrale Bild-Warteschlange.

    .venv/bin/python styles/amiga-illustration/prompts/make_jobs.py

Motiv-, Hintergrund- und Schutzblock kommen wörtlich aus data/motif.json; Stil- und Kompositionsblock stehen hier.
Die Komposition (Anteile der Bildhöhe/-breite) ist mit scripts/load_ai.py → HINTS abgestimmt: Dort sucht die
Verarbeitung Horizont, Kaikante, Leuchtfeuer, Laterne, Fenster und Schornstein. Wer hier Lagen ändert, ändert
sie dort mit.

Auftrag 1 (wichtigster): das Hafenbild als gemalte Vorlage; build_assets.py verkleinert es auf 320x144 und bringt
es mit Muster-Dithering auf 32 aus 4096 Farben.
Auftrag 2: Nahaufnahme des Dachses am selben Ort (Referenzen: Auftrag 1 für Technik/Palette/Ort,
Referenzblatt nur für Kostüm/Proportionen); erscheint in der Demo nach der Eingabe "nimm paket".
"""
import json
import pathlib

ROOT = pathlib.Path(__file__).resolve().parents[3]
SLUG = "amiga-illustration"
RAW = f"styles/{SLUG}/assets/raw"
motif = json.loads((ROOT / "data/motif.json").read_text())
SCENE = motif["scene"]["block_en"]
BG_ONLY = motif["scene"]["background_only_en"]
CHAR = motif["character"]["block_en"]
GUARDS = motif["guards_en"]
SHEET = motif["character"]["reference_sheet"]

BG_STYLE = (
    "Style: the location picture of an illustrated text adventure of the late 1980s, prepared as the original "
    "painted artwork from which the small screen picture is made later. A realistic, finely observed book "
    "illustration painted by hand in opaque gouache and acrylic on illustration board: near-photographic "
    "perspective, proportions, light and materials, but clearly painted, with calm, deliberate brushwork. The "
    "picture is built from big, clearly separated shapes with crisp, hard edges between objects and a clear value "
    "structure: every object reads as a strong silhouette against what lies behind it. Materials are painted as "
    "distinct marks a few millimetres in size that stay readable when the picture is reduced to a very small size: "
    "rough granite blocks with dark joints and cracks, weathered planks with visible grain, wet dark rocks with "
    "pale edges, tarred hull planks, slate roof tiles, the iron frame and glass of the lantern. The sky and the "
    "open water are painted with smooth, even colour gradients and long horizontal bands, without noise or fine "
    "speckle. Restrained palette of about a dozen colours, each in an even ramp from light to dark: deep blue and "
    "blue-violet for the sky and the sea, dusky mauve clouds, a single band of warm orange at the horizon, cool "
    "blue-grey stone, warm grey-brown wood, dark green-grey moss and seaweed, a few small warm yellow lights. "
    "Mid-tone values: a clear, luminous dusk in which every object stays readable; deep shadow only in small "
    "areas, no large black areas. Avoid: pixel art, visible pixels, dithering patterns, scan lines, a photograph, "
    "a 3D render, glossy CGI, a modern digital concept painting with soft airbrush haze, a postcard sunset, lens "
    "flare, glow halos, bloom, light rays, bokeh, depth-of-field blur, thick black outlines, a cartoon or anime "
    "look, a frame or border."
)

BG_COMPOSITION = (
    "Composition for a wide picture strip: the picture is later cropped to a band of about 2.2:1, so all "
    "important content lies between 17% and 83% of the image height; the top 17% shows only dusk sky with the "
    "first stars, the bottom 17% only plain, empty stone paving of the quay. Eye-level view from the quay, "
    "straight horizon at 50% of the image height. The harbour-master's stone cottage stands at the far left edge, "
    "partly cut off by the left border; it has a gable roof with a single chimney, and the top of the chimney is "
    "the highest point of the cottage, at about 22% of the image height; one lit window faces the viewer. The iron "
    "lantern on its wooden post stands on the quay just to the right of the cottage, at about 30% of the image "
    "width, its glass at about 45% of the image height. The white lighthouse with one red band stands on a rocky "
    "headland on the right at about 80% of the image width, its lamp at about 26% of the image height. The wooden "
    "jetty with the two moored fishing boats lies in the middle distance between 40% and 70% of the image width. "
    "Open, calm water with long horizontal ripples fills the band between the horizon and the stone edge of the "
    "quay at about 64% of the image height. The two barrels, the stack of crates and the coil of rope stand "
    "together at the right end of the quay, between 82% and 98% of the image width. The quay paving in the "
    "foreground is close to the viewer: a barrel standing on it is about one sixth of the image height tall. The "
    "middle of the quay, between 10% and 75% of the image width and from the stone edge down to the bottom, stays "
    "open and empty: a character will walk there. Lights and smoke are animated separately, so do not paint them "
    "as effects: the lighthouse lamp is only a small bright spot without any beam, rays or halo; the chimney shows "
    "no smoke at all; the lantern glass and the cottage window are lit flat, without glow around them."
)

CU_INTRO = (
    "Second picture for the same illustrated text adventure: a close-up in the same harbour, in which the badger "
    "courier hands the parcel to the viewer. The first attached image is the location picture of this harbour: "
    "paint the new picture in exactly its technique, palette and light, and use its harbour as the background, "
    "seen from a few steps closer (the cottage with the lit window on the left, the lighthouse on its headland on "
    "the right, the horizon and the calm water in between). The second attached image is a character sheet that "
    "only shows the costume and the body proportions of the badger: do not copy its layout, its three views, its "
    "drawing style or its magenta background."
)

CU_STYLE = (
    "Style: a realistic, finely observed book illustration painted by hand in opaque gouache and acrylic on "
    "illustration board, exactly like the first attached image: near-photographic proportions, light and "
    "materials, but clearly painted; big, clearly separated shapes with crisp edges and a clear value structure. "
    "Materials are painted as distinct marks that stay readable when the picture is reduced to a very small size: "
    "coarse fur in small locks, the black and white stripes of the face sharply separated, the knitted stitches of "
    "the red scarf, the seams and the brass button of the cap, the worn leather of the satchel, the creased brown "
    "paper and the string of the parcel. The badger is lit warmly from the left by the lantern and the cottage "
    "window and coolly in blue-violet from the dusk sky on the right. Restrained palette of about a dozen colours, "
    "each in an even ramp from light to dark; mid-tone values, no large black areas. A dignified, friendly, "
    "believable animal character, not a toy. Avoid: pixel art, visible pixels, dithering patterns, a photograph, "
    "a 3D render, glossy CGI, a plush toy, a cute cartoon, chibi or anime proportions, big glossy eyes, soft "
    "airbrush haze, glow halos, light rays, bokeh, depth-of-field blur, thick black outlines, a frame or border."
)

CU_COMPOSITION = (
    "Composition: one single picture with one badger only, no other characters, not a character sheet. The badger "
    "stands on the quay facing the viewer in a three-quarter view turned slightly to the right, shown from the "
    "hips up and placed slightly left of the centre, between 25% and 65% of the image width. The picture is later "
    "cropped to a band of about 2.2:1, so all important content lies between 17% and 83% of the image height: the "
    "top of the cap at about 20%, the eyes at about 33%, the parcel at about 62% of the image height. Instead of "
    "carrying the parcel under the arm, the badger holds it out towards the viewer in both front paws, with a calm, "
    "friendly look, mouth closed, eyes open. The red scarf hangs down in front, the satchel strap crosses the "
    "chest. Behind the badger: the horizon at 50% of the image height, the lighthouse at about 82% of the image "
    "width with its lamp at about 30% of the image height. The lighthouse lamp is only a small bright spot without "
    "any beam, rays or halo, the chimney shows no smoke, and all lights are lit flat without glow (they are "
    "animated separately)."
)

jobs = [
    {
        "out": f"{RAW}/bg.png",
        "size": "1536x1024",
        "prompt": "\n\n".join([BG_STYLE, BG_COMPOSITION, SCENE, BG_ONLY, GUARDS, "Image format: landscape 3:2."]),
        "refs": [],
    },
    {
        "out": f"{RAW}/closeup.png",
        "size": "1536x1024",
        "prompt": "\n\n".join([CU_INTRO, CU_STYLE, CU_COMPOSITION, SCENE, CHAR, GUARDS, "Image format: landscape 3:2."]),
        "refs": [f"{RAW}/bg.png", SHEET],
    },
]

out = ROOT / f"styles/{SLUG}/assets/image_jobs.json"
out.write_text(json.dumps(jobs, ensure_ascii=False, indent=1) + "\n")
for j in jobs:
    (ROOT / f"styles/{SLUG}/prompts" / (pathlib.Path(j["out"]).stem + ".txt")).write_text(j["prompt"] + "\n")
print(out, len(jobs), "Aufträge;", ", ".join(f"{pathlib.Path(j['out']).name}: {len(j['prompt'])} Zeichen" for j in jobs))
