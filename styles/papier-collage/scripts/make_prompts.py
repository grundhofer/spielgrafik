#!/usr/bin/env python3
"""Prompts und Bildaufträge für papier-collage (Format von genimg.py --jobs).

Aufbau je Prompt: Stilblock + Lage-/Teileblock + Motivblock wörtlich aus data/motif.json + Schutzregeln
+ Formatangabe. Alle Aufträge laufen bewusst über agy (gleiches Bildmodell für alle Papierteile, agy hält die
Anordnung der ersten Referenz genau ein). Ergebnis: assets/prompts/*.txt und assets/jobs_<welle>.json.

    .venv/bin/python styles/papier-collage/scripts/make_prompts.py
"""
import json, pathlib

HERE = pathlib.Path(__file__).resolve().parent.parent
ROOT = HERE.parent.parent
REL = "styles/papier-collage/assets"
motif = json.loads((ROOT / "data" / "motif.json").read_text())
SCENE = motif["scene"]["block_en"]
BG_ONLY = motif["scene"]["background_only_en"]
CHAR = motif["character"]["block_en"]
GUARDS = motif["guards_en"]

STYLE = (
    "Handmade cut-paper collage for a 2D side-view adventure game. Every shape is a separate, flat piece of real "
    "paper – matte coloured construction paper, brown kraft paper, rough watercolour paper and thin translucent "
    "tissue paper – cut out with scissors or torn by hand and glued in overlapping layers. Clearly visible paper "
    "grain and fibres on every piece. Scissor-cut edges are crisp and slightly irregular; torn edges show a thin "
    "ragged white fibrous rim where the paper core shows. Details are smaller paper pieces glued on top: window "
    "frames, planks, stones, stripes, punched paper dots for buttons, rivets and stars. Each glued layer casts a "
    "thin soft shadow onto the paper directly beneath it. Bold, simple, slightly naive hand-cut shapes, few "
    "pieces, one flat matte colour per piece: no gradients inside a piece, no painted shading, no outlines, no ink "
    "or pencil lines, no airbrush, no glossy highlights. Dusk colours: deep indigo, violet and dusty rose papers in "
    "the sky, a strip of warm orange paper at the horizon, slate blue and teal papers for the sea, grey and ochre "
    "papers for stone, warm brown kraft paper for wood, dark green and red papers for accents; the lights are "
    "pieces of bright yellow paper. Not a painting, not a vector illustration, not a 3D render, not a photograph "
    "of a real place."
)

MOCK = ("The first reference image is only a rough block mock-up of the layout: keep the position, size and outline "
        "of every object as in it, but take nothing of its flat colours or crude shapes; make every object properly "
        "as described, as cut paper.")

TAIL_LAND = GUARDS + "\nImage format: landscape 3:2."
TAIL_PORT = GUARDS + "\nImage format: portrait 2:3."

P = {}
P["back"] = "\n".join([
    STYLE,
    "This image is the farthest background layer of a game scene: only the sky, the distant sea, far islands and "
    "the rocky headland with the lighthouse. " + MOCK,
    "The sky is made of long horizontal torn strips of tissue paper and construction paper, from deep indigo at the "
    "top through violet and dusty rose to a narrow strip of warm orange paper at the horizon, with three or four "
    "flat cut-paper clouds in violet and rose and a few tiny punched paper stars in the upper sky. The horizon is one "
    "straight, level line across the whole width. Below it the distant sea reaches down to the bottom edge: "
    "horizontal torn strips of slate blue and teal paper, slightly darker towards the bottom, and a few thin strips "
    "of pale orange paper as reflections near the horizon. Far-away low islands of dark violet paper lie on the "
    "horizon at the left. On the right the rocky headland, built from layered torn grey and violet papers with a "
    "little dark green paper on top, and on it the white lighthouse with one red band and a dark lantern room; its "
    "lamp is only a small round piece of yellow paper, without any beam, rays or glow (the light is animated "
    "separately in the game). Nothing else in this layer: no quay, no jetty, no cottage, no boats, no birds, no "
    "characters (they are separate layers glued in front).",
    "The whole scene, of which this image shows only the far layer: " + SCENE,
    BG_ONLY,
    TAIL_LAND,
])

P["quay"] = "\n".join([
    STYLE,
    "This image is the front gameplay layer of the same game scene, a set piece that is glued in front of the "
    "background: the stone quay with the harbour-master's cottage and the things on the quay. " + MOCK,
    "The quay runs across the whole width of the image as a broad band at the bottom: its walking surface is made of "
    "irregular cut pieces of grey and ochre stone paper fitted together like paving, its back edge is a straight, "
    "level line. On the left, standing on the quay, the small stone harbour-master's cottage: walls of cut grey "
    "stone-paper pieces, a roof of overlapping strips of slate-blue paper, a wooden door of kraft-paper planks, one "
    "window that is a piece of bright yellow paper behind a dark paper window cross, and a stone chimney without any "
    "smoke (the smoke is animated separately). Right of the centre an iron lantern of dark paper hangs from the arm "
    "of a wooden post; its glass is a piece of bright yellow paper, without glow or rays around it. On the right two "
    "wooden barrels with dark paper hoops, a stack of wooden crates of kraft paper and a coil of rope made of a "
    "twisted paper strip. Everything above and around these objects – sky, sea, boats, the jetty, the headland and "
    "the lighthouse – is left out: all of this layer isolated on a fully transparent background, no shadow cast "
    "outside the pieces.",
    BG_ONLY,
    "The whole scene, of which this image shows only the front layer: " + SCENE,
    TAIL_LAND,
])

P["props"] = "\n".join([
    STYLE,
    "A sheet of separate cut-paper pieces for animating the same game scene, all at one common scale and in exactly "
    "the paper technique and colours of the second reference image. " + MOCK,
    "The pieces, each one complete, none touching another, with clear empty space between all of them: at the top "
    "left a short wooden jetty seen exactly from the side, a long deck of kraft-paper planks on six wooden posts; "
    "below it two small wooden fishing boats seen exactly from the side, the left one smaller, each with a single "
    "mast, a furled sail and a little rigging of thin paper strips, their hulls complete down to the keel (no water); "
    "at the top right two flat cut-paper clouds in violet and rose; on the right a white seagull body seen from the "
    "side without wings, and next to it one separate long wing of white and grey paper; at the bottom right three "
    "soft smoke puffs of torn grey tissue paper of growing size. All pieces isolated on a fully transparent "
    "background, no shadow cast outside the pieces.",
    "The pieces belong to this scene: " + SCENE,
    TAIL_LAND,
])

PUPPET = (
    "The badger courier as a jointed cut-paper puppet for this game, built from a few separate flat paper pieces "
    "that overlap at rounded joints, like a cut-out animation puppet. The pieces are flat paper with visible grain "
    "and crisp cut edges, with ragged torn white edges only where there is fur: the black-and-white striped face is "
    "made of glued paper stripes, the eye is a punched paper dot, the nose a piece of black paper, the cap dark "
    "green paper with a punched brass-yellow paper button, the vest dark green paper with paper pocket flaps and "
    "punched brass-yellow paper buttons, the shirt cream paper, the scarf red paper with cut fringes, satchel and "
    "strap brown paper, the parcel brown kraft paper tied with a real thin string, the paws dark grey paper with "
    "small cut claws."
)

P["badger"] = "\n".join([
    STYLE,
    PUPPET,
    "Seen exactly from the side, facing right, standing upright in a neutral pose, both feet flat on one baseline: "
    "the head with the cap; the body with shirt, vest, the scarf wound around the neck, satchel and strap; the near "
    "arm with the rolled-up sleeve holding the parcel against the side of the body; the far arm behind the body; two "
    "short stout legs with large paws; the loose end of the scarf hanging down the back.",
    "The first reference image shows the pose, size and position of the figure and its costume and proportions; the "
    "second reference image shows the paper technique of the game. Take nothing of the painting style, fur strokes "
    "or outlines of the first image, and nothing of the landscape of the second.",
    CHAR,
    "Isolated on a fully transparent background, no floor, no shadow cast outside the figure.",
    TAIL_PORT,
])

PART = ("Edit of the reference image: the same jointed cut-paper puppet of the badger courier, at exactly the same "
        "size and position, but this image shows only {what}, cut out on its own. Everything else of the figure is "
        "left out. Draw the piece complete, also where it was hidden under other pieces in the reference: {fill} "
        "Same paper colours, grain, cut edges and torn white fur edges as in the reference. {extra}Isolated on a "
        "fully transparent background, no shadow cast outside the {pieces}.")

# Teile passend zur erzeugten Gesamtfigur (assets/raw/badger.png): Das Modell hat das Paket der fernen Pfote
# gegeben (vor der Brust sichtbar); der nahe Arm hängt frei, die Pfote liegt auf der Tasche. Die Oberschenkel
# sind dunkles Fell des Rumpfs, darunter kommen graue Unterschenkel mit Füßen.
PARTS = {
    "head": dict(
        what="ONE of its pieces, the head: the green cap with visor, brown band and brass button, the ear, the "
             "black-and-white striped face with the eye, the snout and the black nose",
        fill="below the jaw the neck continues as a rounded tab of dark grey fur paper, reaching down about as far "
             "as the red scarf covered it; the head is not wearing the scarf.",
        extra="", pieces="piece"),
    "torso": dict(
        what="TWO of its pieces: the body and the loose scarf end. The body: the dark green vest with buttons and "
             "pocket flap, the red scarf wound around the neck, the brown satchel strap and the satchel, the white "
             "belly fur, the dark fur hips with their jagged fur edge and the short tail, WITHOUT the head, WITHOUT "
             "the arms, WITHOUT the parcel and WITHOUT the grey lower legs and feet",
        fill="above the scarf the neck is closed with dark grey fur paper; where the near arm with its cream sleeve "
             "and grey paw covered them, the vest, the strap and the satchel continue complete; at the bottom the "
             "dark fur hips end in the same jagged fur edge as in the reference.",
        extra="The second piece, the loose end of the red scarf with its cut fringe, as it flies back in the "
              "reference, lies separately at the left edge of the image with clear empty space between it and the "
              "body. ",
        pieces="pieces"),
    "arms": dict(
        what="TWO of its pieces, the arms. The near arm: the rolled-up cream sleeve, the dark furry forearm and the "
             "grey paw with claws, hanging down",
        fill="the top of the sleeve ends in a rounded shoulder cap where the pin joint will be, and the forearm is "
             "complete where the satchel covered it.",
        extra="The second piece, the far arm, stays at its place in front of the chest: the brown kraft-paper parcel "
              "tied with string, held by a grey paw, with a short piece of the far arm's cream sleeve behind it, "
              "with clear empty space between it and the near arm. ",
        pieces="pieces"),
    "legs": dict(
        what="TWO of its pieces, the legs. The near leg: the grey lower leg with its large hind paw and small cut "
             "claws",
        fill="the top of the leg continues as a rounded tab of grey paper that reaches up under the dark fur of the "
             "hips, where the hip pin joint will be.",
        extra="The second piece, the far leg, is the same leg in slightly darker grey paper; it lies separately at the "
              "left edge of the image with clear empty space between the two legs. ",
        pieces="pieces"),
}
for k, v in PARTS.items():
    P["badger_" + k] = "\n".join([STYLE, PUPPET, PART.format(**v), CHAR, TAIL_PORT])

RN_MOCK = ("The first image is only a rough block mock-up of the layout (positions and sizes); "
           "{second}Do not copy the flat colours of the mock-up.")
JOBS = {
    "w1": [dict(out=f"{REL}/raw/back.png", size="1536x1024", prompt=P["back"], backend="agy",
                refs=[f"{REL}/refs/layout_back.png"],
                ref_note=RN_MOCK.format(second=""))],
    "w2": [dict(out=f"{REL}/raw/quay.png", size="1536x1024", prompt=P["quay"], backend="agy",
                refs=[f"{REL}/refs/layout_quay.png", f"{REL}/raw/back.png"],
                ref_note=RN_MOCK.format(second="the second image shows the paper technique and colours of the game, "
                                               "not its content. ")),
           dict(out=f"{REL}/raw/badger.png", size="1024x1536", prompt=P["badger"], backend="agy",
                refs=[f"{REL}/refs/layout_badger.png", f"{REL}/raw/back.png"],
                ref_note="The first image gives pose, size, position and costume; the second only the paper "
                         "technique.")],
    "w3": [dict(out=f"{REL}/raw/props.png", size="1536x1024", prompt=P["props"], backend="agy",
                refs=[f"{REL}/refs/layout_props.png", f"{REL}/raw/back.png"],
                ref_note=RN_MOCK.format(second="the second image shows the paper technique and colours of the game, "
                                               "not its content. "))],
}
JOBS["w4"] = []
for k in PARTS:
    JOBS["w3" if k in ("head", "torso") else "w4"].append(
        dict(out=f"{REL}/raw/badger_{k}.png", size="1024x1536", prompt=P["badger_" + k], backend="agy",
             refs=[f"{REL}/raw/badger.keyed-src.png"],
             ref_note="Keep the size, position, paper colours and technique of the puppet in it."))

# Nachbesserung: Die Teilbilder hielten das Layout der Gesamtfigur so eng ein, dass Arm und Beine (Rumpf) bzw. der
# ganze Körper (Kopf) stehen blieben. Für den Rumpf deshalb eine grob zerlegte Vorlage (scripts/body_layout.py),
# deren flache Flecken das Modell als Weste und Tasche fertigzeichnet.
P["badger_body"] = "\n".join([
    STYLE,
    PUPPET,
    "Edit of the first reference image: it shows two pieces of the jointed cut-paper puppet of the badger courier, "
    "roughly cut apart: the body and, at the left, the loose end of the scarf. Redraw both pieces at exactly the same "
    "size and position as clean, finished cut-paper pieces in the paper technique of the second reference image. "
    "The body: the red scarf wound around the neck (the body piece ends at the top edge of the scarf, nothing above "
    "it), the dark green vest with buttons and pocket flap, the brown satchel strap and the satchel, the white belly "
    "fur, the dark fur hips with their jagged fur edge and the short tail. The flat, plain patches in the first "
    "reference are places where other pieces lay on top: complete them as the dark green vest and as the brown "
    "leather satchel with its flap edge and buckle tab, with the same grain and detail as the rest. No arm, no paw, "
    "no sleeve, no head, no legs and no parcel on these pieces. Isolated on a fully transparent background, no "
    "shadow cast outside the pieces.",
    CHAR,
    TAIL_PORT,
])
JOBS["w5"] = [dict(out=f"{REL}/raw/badger_body.png", size="1024x1536", prompt=P["badger_body"], backend="agy",
                   refs=[f"{REL}/refs/layout_body.png", f"{REL}/raw/badger.keyed-src.png"],
                   ref_note="The first image gives the pieces, their size and position; the second shows the finished "
                            "puppet and its paper technique.")]

if __name__ == "__main__":
    pd = HERE / "assets" / "prompts"
    pd.mkdir(parents=True, exist_ok=True)
    for k, v in P.items():
        (pd / f"{k}.txt").write_text(v + "\n")
    for k, v in JOBS.items():
        (HERE / "assets" / f"jobs_{k}.json").write_text(json.dumps(v, ensure_ascii=False, indent=1))
    print({k: len(v) for k, v in JOBS.items()}, {k: len(v) for k, v in P.items()})
