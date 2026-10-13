#!/usr/bin/env python3
"""Prompts der Ortsserie im Stil pc98-adventure (16-Farben-Adventure eines japanischen 16-Bit-PCs).

Aufruf aus dem Projektordner:
    .venv/bin/python styles/ortsserie/pc98-adventure/scripts/build_prompts.py            Experiment A/B (Leuchtturm)
    .venv/bin/python styles/ortsserie/pc98-adventure/scripts/build_prompts.py --rest A   stube + klippe mit Variante A
                                                                                          (oder B)
Schreibt
    styles/ortsserie/pc98-adventure/assets/jobs_ab.json      Aufträge (Format genimg.py --jobs): leuchtturm_a, leuchtturm_b
    styles/ortsserie/pc98-adventure/assets/jobs_rest.json    Aufträge stube, klippe mit der gewählten Variante
    styles/ortsserie/pc98-adventure/assets/prompts/<name>.txt dieselben Prompts zum Lesen

Bausteine
  ANCHOR_EN  nur Variante A: das Hafenbild des Stils (styles/pc98-adventure/assets/raw/bg.png) als Stilreferenz,
             Text nach dem Muster von ANCHOR_EN aus styles/hintergrund-serie/tools/prompts.py (nur die Machart
             übernehmen, nicht Aufbau und Gegenstände); anchor_extra je Ort wörtlich von dort
  STYLE_EN   Stilblock wörtlich aus styles/pc98-adventure/prompts/bg.txt, ohne die hafenbezogenen Sätze (Kamera
             „onto the harbour“, Bildaufbau, Leuchtfeuer/Rauch); in der Konturzeile ist die Gegenstandsliste des
             Hafens („every building, boat, rock, barrel and post“) durch eine allgemeine ersetzt
  SERIES_EN  Serienregeln, für alle drei Orte gleich: Abenddämmerung wie der Hafen, Licht, Augenhöhe/Horizont,
             Bildaufbau für das Bildfenster des Stils (Rand oben/unten wird beschnitten, Mitte ruhig für ein
             späteres Porträt)
  Ortsblock, FREE_EN, anim + ANIM_TAIL, guards_en, FORMAT_EN  wörtlich aus styles/hintergrund-serie/tools/prompts.py
             (dort per importlib geladen, nichts kopiert, nichts geändert)
"""
import argparse, importlib.util, json, pathlib, sys

sys.dont_write_bytecode = True      # kein __pycache__ im fremden Ordner styles/hintergrund-serie/tools
ROOT = pathlib.Path(__file__).resolve().parents[4]
SD = ROOT / "styles" / "ortsserie" / "pc98-adventure"
REL = "styles/ortsserie/pc98-adventure"
RAW = f"{REL}/assets/raw"
ANCHOR_IMG = "styles/pc98-adventure/assets/raw/bg.png"     # Hafen des Stils (agy, 1264x848)

_spec = importlib.util.spec_from_file_location("hs_prompts", ROOT / "styles/hintergrund-serie/tools/prompts.py")
HS = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(HS)

# --- Stilblock: Sätze aus styles/pc98-adventure/prompts/bg.txt ------------------------------------------------
_BG = (ROOT / "styles/pc98-adventure/prompts/bg.txt").read_text().split("\n\n")[0]
_S_INTRO = ("Scene illustration for a Japanese adventure game on a 16-bit home computer of the late 1980s and early "
            "1990s, shown in the picture window of the game screen: high-resolution 640x400 pixel art with only 16 "
            "colours on screen, chosen from a 4096-colour palette.")
_S_LINE_HARBOUR = ("Crisp, clean anime-style line art: every building, boat, rock, barrel and post has a thin dark "
                   "outline of one pixel, no anti-aliasing, no blur.")
_S_LINE = ("Crisp, clean anime-style line art: every wall, beam, piece of furniture, rock, post and object has a thin "
           "dark outline of one pixel, no anti-aliasing, no blur.")
_S_REST = ("Flat cel shading with one light and one shadow tone per surface. All gradients (sky, sea, glow around the "
           "lit window) are made only from regular ordered dithering patterns between two neighbouring colours: fine "
           "checkerboard raster, 25% and 75% dot grids, horizontal line patterns, never smooth blends and never "
           "noise. Calm, precise, slightly melancholic visual-novel mood. Dusk palette with few colours: deep indigo "
           "and violet sky with dithered bands, a band of orange and pink light at the horizon, dark blue sea with "
           "short horizontal light dashes, cool grey stone, warm brown wood, warm yellow window light.")
_S_AVOID = ("Avoid: painterly digital painting, soft airbrush gradients, photorealism, 3D rendering, a postcard look, "
            "modern pixel art with hundreds of colours, lens flare, bloom.")
# Wörtlichkeit gegen die Quelle prüfen (bricht ab, wenn bg.txt sich geändert hat)
for _s in (_S_INTRO, _S_LINE_HARBOUR, _S_REST, _S_AVOID):
    assert _s in _BG, _s[:60]

STYLE_EN = " ".join([_S_INTRO, _S_LINE, _S_REST, _S_AVOID])

_SERIES_HEAD = (
    "Series rules, identical for every picture of this series. Time of day: dusk, the same evening as the harbour "
    "picture of this series; outdoors and in windows the sky is deep indigo and violet with dithered bands, a band "
    "of orange and pink light at the horizon and the first stars. Light: indoors the warm yellow light of the lamp, "
    "the candle or the fire is the main light and the rest of the room lies in cool blue-violet shade; outdoors the "
    "last light comes from the band at the horizon and the shadows are cool blue-violet. Camera: medium-wide view "
    "from standing eye level, straight on, no tilt, no fisheye, vertical lines stay vertical; the eye level "
    "(outdoors the horizon line) lies at about 45% of the image height from the top. "
)
_SERIES_TAIL = (
    "the centre and lower centre stay calm and uncluttered (open floor, path or water), because a character "
    "portrait will be placed there later."
)
# Experiment A/B (leuchtturm_a/_b): diese Fassung ließ agy in beiden Varianten einen Rahmen ins Bild malen.
SERIES_EN_AB = _SERIES_HEAD + (
    "Layout for the picture window of the game screen: the picture is shown inside a framed window that cuts off a "
    "thin strip at the top and at the bottom, so keep important objects away from the top and bottom 6% of the "
    "picture; ") + _SERIES_TAIL
# Serie (leuchtturm, stube, klippe): ohne „framed window“, dafür ausdrücklich randlos.
SERIES_EN = _SERIES_HEAD + (
    "Layout for the picture window of the game screen: the picture fills the whole canvas from edge to edge, with "
    "no painted frame, border or margin; it will be cropped slightly at the top and at the bottom, so keep "
    "important objects away from the top and bottom 6% of the picture; ") + _SERIES_TAIL

ANCHOR_EN = (
    "Reference image: the attached picture is the first picture of this series, a 16-colour pixel-art scene of a "
    "harbour at dusk. Use it only as a sample of the rendering: match its pixel size, one-pixel dark outlines, flat "
    "cel shading, ordered dithering patterns, palette, light and level of detail exactly, as if drawn by the same "
    "artist for the same game on the same day. Do not copy its composition, its layout or its objects: this is a "
    "new picture of a different place, described below.{extra}"
)
REF_NOTE = "Take only the pixel-art rendering and the palette from it, not its composition, layout or objects."

LOCS = ["leuchtturm", "stube", "klippe"]


def prompt(loc, variant, series=None):
    d = HS.LOCATIONS[loc]
    parts = []
    if variant == "A":
        parts.append(ANCHOR_EN.format(extra=d["anchor_extra"]))
    parts += [STYLE_EN, series or SERIES_EN, d["block"], HS.FREE_EN, d["anim"] + HS.ANIM_TAIL,
              HS.MOTIF["guards_en"], HS.FORMAT_EN]
    return "\n\n".join(parts)


def job(loc, variant, name, series=None):
    j = {"out": f"{RAW}/{name}.png", "size": "1536x1024", "prompt": prompt(loc, variant, series)}
    if variant == "A":
        j["refs"] = [ANCHOR_IMG]
        j["ref_note"] = REF_NOTE
    return j


def write(jobs, fname):
    P = SD / "assets" / "prompts"
    P.mkdir(parents=True, exist_ok=True)
    for j in jobs:
        name = pathlib.Path(j["out"]).stem
        (P / f"{name}.txt").write_text(j["prompt"] + "\n")
    (SD / "assets" / fname).write_text(json.dumps(jobs, ensure_ascii=False, indent=1) + "\n")
    for j in jobs:
        print(f"{j['out']}  {len(j['prompt'])} Zeichen  refs={j.get('refs', [])}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--rest", choices=["A", "B"],
                    help="Serienaufträge (leuchtturm neu, stube, klippe) mit dieser Variante")
    ap.add_argument("--extra", nargs=3, metavar=("ORT", "VARIANTE", "NAME"),
                    help="ein Zusatzauftrag mit Serienregeln, z. B. klippe B klippe_b (Gegenprobe ohne Referenz)")
    a = ap.parse_args()
    if a.extra:
        loc, var, name = a.extra
        write([job(loc, var, name)], f"jobs_{name}.json")
    elif a.rest:
        write([job(loc, a.rest, loc) for loc in LOCS], "jobs_rest.json")
    else:
        write([job("leuchtturm", "A", "leuchtturm_a", SERIES_EN_AB),
               job("leuchtturm", "B", "leuchtturm_b", SERIES_EN_AB)], "jobs_ab.json")


if __name__ == "__main__":
    main()
