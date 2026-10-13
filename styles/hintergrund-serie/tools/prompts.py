#!/usr/bin/env python3
"""Baut die Prompts der Hintergrund-Serie aus festen Bausteinen und schreibt die Bildaufträge.

Aufruf aus dem Projektordner:
    .venv/bin/python styles/hintergrund-serie/tools/prompts.py

Schreibt
    styles/hintergrund-serie/assets/image_jobs.json   Aufträge für tools/imagequeue.py (Format genimg.py --jobs),
                                                       in Prioritätsreihenfolge
    styles/hintergrund-serie/assets/prompts/<ort>.txt  dieselben Prompts zum Lesen

Bausteine (alle Hintergründe teilen STYLE_EN, SERIES_EN, guards und Format):
  ANCHOR_EN  nur Folgebilder: das erste Bild (Hafen) ist der Stilanker und geht als einzige Referenz mit
  STYLE_EN   Stilblock: Medium, Technik, Reduktion, Palette, was es nicht sein soll
  SERIES_EN  Serienregeln: Tageszeit, Lichtrichtung, Augenhöhe/Horizont, Bildaufbau für Textbox und Laufstreifen
  Ortsblock  Hafen wörtlich aus data/motif.json, die drei neuen Orte unten nach demselben Muster
  FREE       Hafen: background_only_en wörtlich; sonst dieselbe Regel für Boden und Weg
  ANIM_EN    je Ort: Effekte, die Godot animiert, nicht mitmalen
  guards_en  wörtlich aus data/motif.json
  FORMAT_EN  Formatangabe

Die Ziele liegen in assets/raw/; die Folgeaufträge zeigen mit refs auf das Ziel des ersten Auftrags
(raw/hafen.png). imagequeue.py arbeitet eine Datei der Reihe nach ab, das Ankerbild existiert also, bevor die
Folgebilder erzeugt werden; scheitert es endgültig, enden die Folgeaufträge mit „ref-missing“.
"""
import json, pathlib

ROOT = pathlib.Path(__file__).resolve().parents[3]
SD = ROOT / "styles" / "hintergrund-serie"
P = SD / "assets" / "prompts"
RAW = "styles/hintergrund-serie/assets/raw"
MOTIF = json.loads((ROOT / "data" / "motif.json").read_text())

STYLE_EN = (
    "Style: a traditional hand-painted watercolour illustration, used as a background for a 2D story adventure "
    "game, painted with transparent watercolour and a little opaque gouache on rough cold-press watercolour paper. "
    "Technique: loose transparent washes laid with large soft brushes, wet-in-wet blooms and soft bleeding edges "
    "in the sky and the water, crisp dried edges where washes overlap, pigment granulation in the darker areas, "
    "opaque matte gouache only for a few dark shapes and small light accents, a few dry-brush strokes for stone "
    "and wood texture, a faint loose pencil underdrawing that shows through in places, and the texture of the "
    "white paper visible everywhere through the paint. Reduction: simplified storybook shapes, few objects, large "
    "calm areas of colour, slightly wobbly hand-drawn verticals, no fine clutter, no tiny repeated details, no "
    "thin ropes or rigging lines. Palette: limited and muted: deep indigo and blue-violet for the shadows, muted "
    "slate-teal for water and glass, grey-green for stone and grass, warm cream for walls, paper white for the "
    "highlights, warm ochre and burnt orange only at the light sources and in the band of light at the horizon. "
    "It is not a photograph, not a 3D render, not CGI, not a smooth digital painting, no airbrush gradients, no "
    "glossy highlights, no lens flare, no bloom, no vignette, not a detailed postcard."
)

SERIES_EN = (
    "Series rules, identical for every picture of this series. Time of day: late dusk, about twenty minutes after "
    "sunset; outdoors and in windows the sky is deep blue-violet with a narrow band of warm orange light at the "
    "horizon. Light: the main light comes from the left (outdoors the last warm glow of the sky on the left, "
    "indoors a warm lamp or fire on the left side of the room); shadows fall to the right and are cool "
    "blue-violet; the right side of the picture is slightly cooler and darker. Lamps, windows and fires are "
    "small warm orange pools of light. Camera: straight-on view at standing eye height, no tilt, no fisheye, no "
    "wide-angle distortion, vertical lines stay vertical; the eye level (outdoors the horizon line) lies at 40 "
    "percent of the picture height from the top. Layout for a game screen: the top tenth of the picture is plain "
    "sky, wall or ceiling (it may be cropped); the ground or floor where characters walk is an open, uncluttered "
    "strip between about 58 and 72 percent of the picture height from the top; the bottom quarter of the picture "
    "is a calm, plain, darker foreground without important objects (a text box will cover it)."
)

ANCHOR_EN = (
    "Reference image: the attached picture is the first picture of this series, a watercolour of a harbour. Use "
    "it only as a sample of the painting: match its paper texture, brush handling, washes, edges, palette, light "
    "and level of detail exactly, as if painted by the same hand on the same day. Do not copy its composition, "
    "its layout or its objects: this is a new picture of a different place, described below.{extra}"
)

FORMAT_EN = "Image format: landscape 3:2."

FREE_EN = ("Leave the floor and the path free of people and animals: it is a game background, characters are added "
           "later as separate sprites.")

ANIM_TAIL = " These effects are animated separately in the game."

LOCATIONS = {
    "hafen": {
        "de": "Hafen von Lornholm (Motivblock aus data/motif.json, wörtlich)",
        "block": MOTIF["scene"]["block_en"],
        "anim": ("Do not paint effects that the game animates: the lighthouse lamp, the lantern and the cottage "
                 "window are only small soft glowing spots without any light beams, rays, glare or halo; no smoke "
                 "at all from the chimney; no birds in the sky."),
        "anchor_extra": "",
    },
    "leuchtturm": {
        "de": ("Lampenraum oben im Leuchtturm, von innen: runder Raum, weiß gekalkte Wände, niedrige Holzdecke; "
               "links der Mitte die große Messinglampe in der Linse aus Glasringen (leuchtet warm); ganz links "
               "Pult mit Logbuch, Ölkanne, Fernrohr; rechts Wendeltreppe nach unten; zwei hohe Fenster mit Meer, "
               "Wolken, Horizontband und ersten Sternen; Tau und Kiste an der Wand; abgetretene Dielen."),
        "block": (
            "Location: the lamp room at the top of the white lighthouse of Lornholm, a fictional island in a "
            "northern sea, at dusk, seen from inside. A small round room with whitewashed, slightly curved walls "
            "and a low wooden ceiling. Left of the centre, set back from the open floor, stands the big brass "
            "lighthouse lamp inside a tall lens of stacked glass rings, glowing softly and warmly. On the far left "
            "a small wooden desk with an open logbook, an oil can and a brass telescope. On the right an iron "
            "spiral staircase leads down through a round opening in the floor. Two tall windows in the back wall "
            "show the darkening calm sea, low clouds, a band of orange light at the horizon and the first stars. A "
            "coil of rope and a wooden crate stand against the wall. Worn wooden floorboards."
        ),
        "anim": ("Do not paint effects that the game animates: the big lamp glows softly inside its lens, but "
                 "without any light beams, rays, glare, sparkles or halo around it; no birds outside the windows; "
                 "no dust in the air."),
        "anchor_extra": " There is no harbour, no quay and no boat in this picture.",
    },
    "stube": {
        "de": ("Stube im Häuschen des Hafenmeisters, von innen: niedriger Raum, weiß gekalkte Steinwände, dunkle "
               "Deckenbalken; links Kamin mit Kessel über Glut; in der Mitte an der Rückwand Tisch mit zwei "
               "Stühlen, Teekanne, Kerze, Seekarte; rechts tiefes Fenster mit Blick auf Hafen und fernen "
               "Leuchtturm, daneben Regal mit Büchern, Barometer, Schiffsmodell, Ölzeug am Haken neben der Tür; "
               "Flickenteppich auf Steinplatten."),
        "block": (
            "Location: the parlour of the harbour-master's small stone cottage in Lornholm, a fictional island in "
            "a northern sea, at dusk, seen from inside. A low room with whitewashed stone walls and dark wooden "
            "ceiling beams. On the left a stone fireplace with a black kettle hanging over the glowing embers. In "
            "the middle, against the back wall, a sturdy wooden table with two chairs, a teapot, a candle in a "
            "brass holder and a folded sea chart. On the right a small deep-set window shows the dusky harbour "
            "and, in the distance, the white lighthouse with its lamp lit; beside it a shelf with a few books, a "
            "brass barometer and a model sailing boat, and an oilskin coat on a hook by the door. A braided rag "
            "rug on the stone-flag floor."
        ),
        "anim": ("Do not paint effects that the game animates: the fire in the fireplace only as low glowing "
                 "embers with a soft warm glow, no tall flames, no sparks and no smoke; the candle only as a small "
                 "soft glowing spot; the distant lighthouse lamp only as a tiny glowing dot without a beam."),
        "anchor_extra": " The harbour appears only small, seen through the window.",
    },
    "klippe": {
        "de": ("Klippenpfad über dem Hafen: schmaler Erdpfad mit flachen Steinen quer über die grasige Klippe; "
               "dahinter Zaun aus Holzpfosten mit einer Latte an der Kante; tief unten links der Hafen mit "
               "erleuchteten Fenstern und zwei kleinen Booten, rechts auf der Felsnase der Leuchtturm; Gras, "
               "Heide, Findlinge, Wegweiser mit leeren Brettern, Holzbank; ruhige See, Horizontband, Sterne."),
        "block": (
            "Location: the cliff path above the harbour of Lornholm, a fictional island in a northern sea, at "
            "dusk. A narrow trodden earth path with a few flat stones runs across the grassy clifftop from the "
            "left to the right. Behind the path, along the cliff edge, stands a weathered fence of wooden posts "
            "with one rail. Beyond the edge, far below on the left, lies the small harbour with a few lit windows "
            "and two tiny boats; on a rocky headland on the right stands the white lighthouse with one red band, "
            "its lamp lit. Tufts of wind-bent grass, heather and a few grey boulders; a wooden signpost with blank "
            "boards and a simple wooden bench beside the path. Calm sea, low clouds, a band of orange light at "
            "the horizon, the first stars."
        ),
        "anim": ("Do not paint effects that the game animates: the lighthouse lamp and the harbour windows are "
                 "only small soft glowing spots without any light beams, rays or glare; no smoke; no birds in "
                 "the sky."),
        "anchor_extra": (" The harbour and the lighthouse appear only far away and small, as described; the "
                         "picture is dominated by the clifftop and the path."),
    },
}
ORDER = ["hafen", "leuchtturm", "stube", "klippe"]


def background_prompt(loc):
    d = LOCATIONS[loc]
    parts = []
    if loc != "hafen":
        parts.append(ANCHOR_EN.format(extra=d["anchor_extra"]))
    free = MOTIF["scene"]["background_only_en"] if loc == "hafen" else FREE_EN
    parts += [STYLE_EN, SERIES_EN, d["block"], free, d["anim"] + ANIM_TAIL, MOTIF["guards_en"], FORMAT_EN]
    return "\n\n".join(parts)


WALK_EN = (
    "Sprite sheet for a 2D side-view adventure game: the badger courier walking to the right, painted in "
    "watercolour to match the backgrounds of the game. One row of 6 animation frames of a walk cycle, evenly "
    "spaced, same scale, feet on the same baseline, each frame a distinct leg and arm position (contact, down, "
    "passing, up, contact, down). Three reference images are attached: the one with six walking badgers on a "
    "magenta background gives the layout, the size and the poses, keep them exactly; the watercolour painting of "
    "a harbour at dusk gives the painting technique and the colours; the character sheet with three views gives "
    "only the costume and the proportions, do not copy its clean drawing style. Painting technique: traditional "
    "transparent watercolour with a little opaque gouache, soft painted edges inside the figure, a few visible "
    "brush strokes, a faint pencil underdrawing, no black outlines. Each figure is painted solid and opaque, with "
    "a crisp, closed silhouette edge and no splashes, drips or washes outside the figure. Not a 3D render, not a "
    "smooth digital painting, not a plush toy. Light: soft warm light from the upper left and slightly from the "
    "front, cool blue-violet shading on the right side of the body, mid-light values so that the dark green cap "
    "and vest, the cream shirt and the red scarf stay clearly readable; no rim light, no backlight, no cast "
    "shadow, no ground."
)


def walk_prompt():
    return "\n\n".join([WALK_EN, MOTIF["character"]["block_en"], "Isolated on a fully transparent background.",
                        MOTIF["guards_en"], FORMAT_EN])


def jobs():
    anchor = f"{RAW}/hafen.png"
    out = []
    for loc in ORDER:
        j = {"out": f"{RAW}/{loc}.png", "size": "1536x1024", "prompt": background_prompt(loc)}
        if loc != "hafen":
            j["refs"] = [anchor]
        out.append(j)
    # Laufzyklus: Layout (eigenes Blatt auf Magenta, prep.py layout), Stil (Anker), Kostüm (Referenzblatt)
    out.append({"out": f"{RAW}/walk.png", "size": "1536x1024", "prompt": walk_prompt(),
                "refs": [f"{RAW}/walk_layout_ref.png", anchor, MOTIF["character"]["reference_sheet"]],
                "key_color": "ff00ff"})
    return out


def main():
    P.mkdir(parents=True, exist_ok=True)
    for loc in ORDER:
        (P / f"{loc}.txt").write_text(background_prompt(loc) + "\n")
    (P / "walk.txt").write_text(walk_prompt() + "\n")
    js = jobs()
    (SD / "assets" / "image_jobs.json").write_text(json.dumps(js, ensure_ascii=False, indent=1) + "\n")
    for j in js:
        print(f"{j['out']}  {len(j['prompt'])} Zeichen  refs={j.get('refs', [])}")


if __name__ == "__main__":
    main()
