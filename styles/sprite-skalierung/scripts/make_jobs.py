#!/usr/bin/env python3
"""Schreibt die Bildaufträge (genimg.py --jobs) für sprite-skalierung.

    .venv/bin/python styles/sprite-skalierung/scripts/make_jobs.py <jobs.json> [name ...]

Aufbau je Prompt: Stilblock + Inhalt (+ Figurenblock aus data/motif.json wörtlich) + guards_en + Format.
Die Prompts landen zusätzlich als Text in styles/sprite-skalierung/prompts/.
"""
import json, pathlib, sys

ROOT = pathlib.Path(__file__).resolve().parents[3]
SD = ROOT / "styles" / "sprite-skalierung"
motif = json.loads((ROOT / "data" / "motif.json").read_text())
CHAR = motif["character"]["block_en"]
GUARDS = motif["guards_en"]


def style(px):
    return (
        "Mid-1980s coin-op arcade pixel art: a sprite for a sprite-scaling pseudo-3D arcade game whose hardware "
        "zooms large pre-drawn sprites smoothly toward the camera. Drawn at low resolution with big, clearly "
        f"visible square pixels on one coarse grid ({px}), hard pixel edges, no anti-aliasing, no gradients, "
        "no blur, no dithering noise. Bold, saturated arcade colours, at most 15 colours per object, 2 to 3 "
        "flat shading tones per material, a dark coloured outline (deep purple-brown, not pure black). Warm low "
        "evening light from the front left with an orange rim light, shadows in cool violet, colours stay "
        "bright and readable. Not a photograph, not a 3D render, not a painting, not a vector illustration."
    )


TRANSP = "Isolated on a fully transparent background."

JOBS = {
    "badger_run": dict(
        size="1536x1024",
        refs=["shared/badger/master_sheet.png"],
        prompt=style("each figure about 64 art pixels tall") + " "
        "Content: a sprite sheet of the player character seen directly from behind, running straight away from "
        "the viewer into the depth of the screen, like the hero of a third-person arcade game who always runs "
        "into the picture. One row of exactly 3 animation frames, evenly spaced with wide gaps, identical scale "
        "and size, the planted foot of every frame on the same baseline, all centred on the same vertical axis: "
        "frame 1 - left foot planted, right leg kicked back and up so the right sole is visible, arms swinging; "
        "frame 2 - passing pose, both legs together under the body, body upright and slightly higher; "
        "frame 3 - right foot planted, left leg kicked back and up so the left sole is visible, arms swinging. "
        "In all three frames we see the back: the back of the dark green peaked cap, the back of the head with "
        "dark grey fur and white ear tips, the red knitted scarf with both ends hanging down over the back, the "
        "back of the dark green vest, the brown satchel strap diagonally across the back and the satchel on the "
        "hip, the short white tail, the dark grey legs and paws; the parcel under one arm peeks out at the side. "
        "Character (costume only): " + CHAR + " "
        "Use the reference sheet (its back view on the right) only for the costume and the stout, short-legged "
        "proportions; drawing style, pixel size and palette follow the style block above. "
        + GUARDS + " " + TRANSP + " Image format: landscape 3:2.",
    ),
    "props": dict(
        size="1536x1024",
        refs=[],
        prompt=style("one metre of the object is about 32 art pixels") + " "
        "Content: a sheet of six separate harbour props for the roadside of the game, arranged in two rows of "
        "three with wide gaps, all at the same scale, each standing upright on its own flat base line, seen from "
        "the front at eye level with a slight view from above: 1) an upright wooden barrel with iron hoops; "
        "2) a stack of three wooden crates; 3) a short black iron mooring bollard; 4) a tall wooden post, about "
        "three times the height of the barrel, with an iron lantern hanging from a short arm at the top, the "
        "lantern glass only a small flat warm-yellow window without any rays, halo or glow around it (the glow "
        "is animated separately); 5) a coil of thick hemp rope lying flat; 6) a brown paper parcel tied with "
        "string. Harbour of a small northern island at dusk. No ground, no cast shadows, nothing else. "
        + GUARDS + " " + TRANSP + " Image format: landscape 3:2.",
    ),
    "boats": dict(
        size="1536x1024",
        refs=[],
        prompt=style("one metre is about 24 art pixels") + " "
        "Content: two small wooden fishing boats of a northern island harbour, side by side with a wide gap, "
        "both at the same scale, each seen from behind at a three-quarter angle so that the stern and the whole "
        "side facing the viewer are visible, the bow pointing away into the depth: boat 1 with a red hull, white "
        "upper planks, a small white wheelhouse and a short mast; boat 2 with a dark blue hull, white upper "
        "planks, an open deck, a short mast with a furled brown sail. Only the parts above the waterline: each "
        "hull is cut off by a straight horizontal waterline at the bottom. No water, no reflections, no ropes, "
        "lamps unlit. " + GUARDS + " " + TRANSP + " Image format: landscape 3:2.",
    ),
    "cottage": dict(
        size="1024x1024",
        refs=[],
        prompt=style("one metre is about 24 art pixels") + " "
        "Content: a small stone harbour-master's cottage of a northern island harbour as one roadside sprite, "
        "seen from the front-left three-quarter view at eye level: the gable end with a wooden door faces the "
        "viewer, the long side with one lit window faces right (the window glass a flat warm-yellow area, no "
        "glow around it), a dark slate roof, a stone chimney on the ridge without any smoke (the smoke is "
        "animated separately), rough grey-beige stone walls, a small step in front of the door. Standing on a "
        "flat base line, no ground around it, no cast shadow. " + GUARDS + " " + TRANSP
        + " Image format: square 1:1.",
    ),
    "horizon": dict(
        size="1536x1024",
        refs=[],
        prompt=style("the lighthouse about 40 art pixels tall") + " "
        "Content: a very wide horizontal strip of the distant coast at dusk, used as the far horizon layer "
        "behind the playfield of a pseudo-3D arcade game; it scrolls sideways in curves. Everything stands on "
        "one perfectly straight horizontal baseline (the sea horizon) at about two thirds of the image height. "
        "From left to right: low flat rocky islets, a long low island with a few dark fir trees, an open gap, "
        "then in the right half a rocky headland rising to a cliff with a white lighthouse with one red band "
        "on top, its lamp only a small bright yellow spot without any beam (the beam is animated separately), "
        "a tiny keeper's house beside it, then the headland slopes down again, then two small rocks. "
        "Silhouettes in deep violet and dark blue with flat warm orange highlights on the upper edges that "
        "face the sunset; the lighthouse stays clearly white and red. The whole sky above and everything below "
        "the baseline are transparent: no sky colour, no clouds, no sun, no sea, no reflections. "
        + GUARDS + " " + TRANSP + " Image format: landscape 3:2.",
    ),
    "clouds": dict(
        size="1536x1024",
        refs=[],
        prompt=style("each cloud bank 12 to 30 art pixels tall") + " "
        "Content: a very wide strip of low evening clouds for the sky layer of a pseudo-3D arcade game: six "
        "long, flat, layered cloud banks with flat bottoms spread across the full width, lit from below by a "
        "sunset behind them (bright orange and pink undersides, violet and dusky blue tops), each drawn as a flat "
        "pixel-art shape with 3 to 4 tones, separated by wide transparent gaps. Everything else is transparent: "
        "no sky colour, no sun, no sea, no land, no stars. " + GUARDS + " " + TRANSP
        + " Image format: landscape 3:2.",
    ),
}

ORDER = ["badger_run", "props", "horizon", "boats", "cottage", "clouds"]


def main():
    out = pathlib.Path(sys.argv[1])
    names = sys.argv[2:] or ORDER
    jobs = []
    (SD / "prompts").mkdir(exist_ok=True)
    for n in names:
        j = JOBS[n]
        (SD / "prompts" / f"{n}.txt").write_text(j["prompt"] + "\n")
        jobs.append({"out": f"styles/sprite-skalierung/assets/raw/{n}.png", "size": j["size"],
                     "prompt": j["prompt"], "refs": j["refs"]})
    out.write_text(json.dumps(jobs, indent=1, ensure_ascii=False))
    print(f"{len(jobs)} Aufträge -> {out}")


if __name__ == "__main__":
    main()
