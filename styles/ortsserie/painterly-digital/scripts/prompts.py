#!/usr/bin/env python3
"""Ortsserie, Stil painterly-digital: baut die Prompts aus festen Bausteinen und schreibt die Bildaufträge.

Aufruf aus dem Projektordner (Python im isolierten Modus):
    .venv/bin/python -I styles/ortsserie/painterly-digital/scripts/prompts.py ab
        -> assets/jobs_1_leuchtturm_ab.json  Experiment am ersten Ort: A mit Stilreferenz, B ohne
    .venv/bin/python -I styles/ortsserie/painterly-digital/scripts/prompts.py series --variant a|b
        -> assets/jobs_2_bilder.json         stube, klippe (gewählte Variante) + Maske leuchtturm
    .venv/bin/python -I styles/ortsserie/painterly-digital/scripts/prompts.py klippe_b
        -> assets/jobs_3_klippe_b.json       Maske stube + klippe ohne Referenz (zweiter A/B-Vergleich, weil
                                             klippe mit Referenz Himmel, Leuchtturmlage und Kaimauer des Ankers
                                             übernahm)
    .venv/bin/python -I styles/ortsserie/painterly-digital/scripts/prompts.py klippe_mask --painting klippe|klippe_b
        -> assets/jobs_4_klippe_mask.json    Maske für die gewählte Klippe + stube ohne Referenz (dritter
                                             A/B-Vergleich, nur Messung, nicht verarbeitet)
    Lesbare Fassungen aller Prompts in assets/prompts/<name>.txt.

Bausteine (alle Gemälde teilen STYLE_EN, SERIES_EN, Ortsblock-Muster, guards und Format):
  ANCHOR_EN  nur Variante A: Hafenbild des Stils (styles/painterly-digital/assets/raw/master.png) als einzige
             Referenz; Text nach ANCHOR_EN aus hintergrund-serie (nur Malweise, nicht Aufbau/Objekte), die
             Aquarell-Wörter durch die Merkmale dieses Stils ersetzt
  STYLE_EN   Stilblock wörtlich aus styles/painterly-digital/prompts/master.txt (erster Absatz); nur der Satz mit
             den Lichthöfen an Hütte/Laterne/Leuchtturm ist ersetzt (hafenbezogen und im Widerspruch zu den
             Effektverboten der Orte, die keine Lichthöfe wollen; die Lichthöfe kommen aus dem Shader)
  SERIES_EN  Serienregeln: Abend wie im Hafen, Licht, Augenhöhe/Horizont 45 % (Wörter aus dem Kompositionsblock
             von master.txt), Freiflächen für die Textleiste unten, klare Flächen für das Kinemagramm
  Ortsblock  LOCATIONS[ort]["block"], ["anim"] (+ ANIM_TAIL), ["anchor_extra"] und FREE_EN wörtlich aus
             styles/hintergrund-serie/tools/prompts.py (importiert, nicht kopiert)
  guards_en  wörtlich aus data/motif.json
Masken: Einleitung wörtlich aus styles/kinemagramm/assets/prompts/mask.txt („as if traced on a clear sheet“),
Farbcodes je Ort (dieselben Codefarben wie dort, damit aimask.py sie einordnen kann).
"""
import argparse, importlib.util, json, pathlib, re, sys

sys.dont_write_bytecode = True      # kein __pycache__ im fremden Ordner styles/hintergrund-serie/tools
HERE = pathlib.Path(__file__).resolve().parent
E = HERE.parent                                   # styles/ortsserie/painterly-digital
ROOT = E.parents[2]
REL = E.relative_to(ROOT).as_posix()
RAW = f"{REL}/assets/raw"
ANCHOR = "styles/painterly-digital/assets/raw/master.png"
P = E / "assets" / "prompts"


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


HS = _load("hs_serie_prompts", ROOT / "styles" / "hintergrund-serie" / "tools" / "prompts.py")
MOTIF = json.loads((ROOT / "data" / "motif.json").read_text())

MASTER = (ROOT / "styles" / "painterly-digital" / "prompts" / "master.txt").read_text().splitlines()[0]
HALO_OLD = ("The light sources glow with soft halos: the lit cottage window, the iron lantern and the lighthouse "
            "lamp. ")
HALO_NEW = "The light sources glow warmly. "
assert HALO_OLD in MASTER, "master.txt hat sich geändert"
STYLE_EN = MASTER.replace(HALO_OLD, HALO_NEW)

SERIES_EN = (
    "Series rules, identical for every picture of this series. Time of day: dusk, as in the harbour picture of "
    "this series: outdoors and in the windows the sky is deep teal and slate blue with low clouds, a band of "
    "warm orange light at the horizon and the first stars. Light: cool, soft dusk light everywhere; warm amber "
    "and orange light comes only from the horizon band and from the lamps, fires and lit windows named below, "
    "each with a small warm pool of light on the nearby surfaces; the shadows are deep teal and dusty violet. "
    "Composition for a side-scrolling game level: strict side view at eye level, flat horizon at 45 % of the "
    "image height (indoors: the horizon seen through the windows), no tilt, no fisheye, no wide-angle "
    "distortion, vertical lines stay vertical. Layout for a game screen: the picture will be cropped to a wide "
    "16:9 screen, so the top tenth and the bottom tenth hold nothing important; the floor or the ground where "
    "characters walk is an open, uncluttered strip between about 60 and 75 % of the image height; the bottom "
    "quarter of the picture is a calm, plain, darker foreground without important objects (a semi-transparent "
    "text bar will cover it). The picture is one single still image that will be brought to life with subtle "
    "animated layers (drifting mist, moving clouds and water, flickering lights): keep the sky, the water and "
    "every light source as clearly separated, readable areas with clean edges."
)

ANCHOR_EN = (
    "Reference image: the attached picture is the first picture of this series, a digital painting of a "
    "harbour at dusk. Use it only as a sample of the painting: match its brush handling, brush texture, soft "
    "edges, haze, palette, light and level of detail exactly, as if painted by the same hand on the same day. "
    "Do not copy its composition, its layout or its objects: this is a new picture of a different place, "
    "described below.{extra}"
)
REF_NOTE_STYLE = "Take only the painting technique and the palette from it, not its composition or its objects."

MASK_INTRO = (ROOT / "styles" / "kinemagramm" / "assets" / "prompts" / "mask.txt").read_text().split(
    "Colour codes:")[0].strip()
MASK_CODES = {
    "leuchtturm": (
        "Colour codes: the sky seen through the windows, including all clouds and stars, down to the horizon: "
        "pure blue #0000FF. The sea seen through the windows, from the horizon down to the window sill: pure "
        "cyan #00FFFF. The glowing glass lens of the big lighthouse lamp, with the brass lamp inside it: pure "
        "orange #FF8000. Everything else (the walls, the ceiling, the window frames and bars, the floor, the "
        "desk with everything on it, the iron staircase, the rope and the crate): pure black #000000. Use no "
        "other colours, and do not add, remove or move any object."),
    "stube": (
        "Colour codes: the sky seen through the window, including all clouds and stars, down to the horizon: "
        "pure blue #0000FF. The water of the harbour seen through the window: pure cyan #00FFFF. The glowing "
        "embers in the fireplace: pure orange #FF8000. The small flame of the candle: pure yellow #FFFF00. The "
        "tiny lit lamp of the distant lighthouse seen through the window: pure red #FF0000. Everything else (the "
        "walls, the ceiling beams, the fireplace stones, the kettle, the table, the chairs, the teapot, the "
        "candle holder, the sea chart, the shelf with its objects, the coat, the door, the window frame, the "
        "land and the lighthouse tower seen through the window, the rug and the floor): pure black #000000. Use "
        "no other colours, and do not add, remove or move any object."),
    "klippe": (
        "Colour codes: the whole sky including all clouds and stars, down to the horizon: pure blue #0000FF. "
        "All open water of the sea and the harbour, including every reflection on the water: pure cyan "
        "#00FFFF. The lit windows of the harbour houses: pure yellow #FFFF00. The glowing lamp at the top of "
        "the lighthouse: pure red #FF0000. The grass, the heather and the low plants on the clifftop, only the "
        "plants themselves: pure green #00FF00. Everything else (the earth path and its stones, the boulders, "
        "the fence, the signpost, the bench, the cliffs and rocks, the harbour houses and boats, the headland "
        "and the lighthouse tower): pure black #000000. Use no other colours, and do not add, remove or move "
        "any object."),
}
FORBIDDEN = re.compile(r"in the style of|\bstudio\b|ghibli|disney|pixar|lucasarts|sierra|\bori\b|hollow knight|"
                       r"child of light|rayman|\bgris\b", re.I)


def painting_prompt(loc, variant):
    d = HS.LOCATIONS[loc]
    parts = []
    if variant == "a":
        parts.append(ANCHOR_EN.format(extra=d["anchor_extra"]))
    parts += [STYLE_EN, SERIES_EN, d["block"], HS.FREE_EN, d["anim"] + HS.ANIM_TAIL, MOTIF["guards_en"],
              HS.FORMAT_EN]
    return "\n\n".join(parts)


def mask_prompt(loc):
    return "\n\n".join([MASK_INTRO, MASK_CODES[loc], MOTIF["guards_en"], HS.FORMAT_EN])


def painting_job(loc, variant, out_name):
    j = {"out": f"{RAW}/{out_name}.png", "size": "1536x1024", "prompt": painting_prompt(loc, variant)}
    if variant == "a":
        j["refs"] = [ANCHOR]
        j["ref_note"] = REF_NOTE_STYLE
    return j


def mask_job(loc, painting):
    return {"out": f"{RAW}/{loc}_mask.png", "size": "1536x1024", "prompt": mask_prompt(loc),
            "refs": [f"{RAW}/{painting}.png"], "ref_note": ""}


def check(jobs):
    for j in jobs:
        m = FORBIDDEN.search(j["prompt"])
        if m:
            sys.exit(f"{j['out']}: verbotene Formulierung {m.group(0)!r}")
        for r in j.get("refs", []):
            if not r.startswith(RAW) and not (ROOT / r).exists():
                sys.exit(f"{j['out']}: Referenz fehlt: {r}")


def write(name, jobs):
    check(jobs)
    P.mkdir(parents=True, exist_ok=True)
    (E / "assets" / name).write_text(json.dumps(jobs, ensure_ascii=False, indent=1) + "\n")
    for j in jobs:
        (P / (pathlib.Path(j["out"]).stem + ".txt")).write_text(j["prompt"] + "\n")
        print(f"{name}: {j['out']}  {len(j['prompt'])} Zeichen  refs={j.get('refs', [])}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("stage", choices=["ab", "series", "klippe_b", "klippe_mask"])
    ap.add_argument("--variant", choices=["a", "b"])
    ap.add_argument("--painting", choices=["klippe", "klippe_b"])
    a = ap.parse_args()
    if a.stage == "klippe_b":
        write("jobs_3_klippe_b.json", [mask_job("stube", "stube"), painting_job("klippe", "b", "klippe_b")])
        return 0
    if a.stage == "klippe_mask":
        if not a.painting:
            ap.error("klippe_mask braucht --painting klippe|klippe_b")
        write("jobs_4_klippe_mask.json", [mask_job("klippe", a.painting), painting_job("stube", "b", "stube_b")])
        return 0
    if a.stage == "ab":
        write("jobs_1_leuchtturm_ab.json", [painting_job("leuchtturm", "a", "leuchtturm_a"),
                                            painting_job("leuchtturm", "b", "leuchtturm_b")])
        return 0
    if not a.variant:
        ap.error("series braucht --variant a|b (Ergebnis des Experiments)")
    write("jobs_2_bilder.json", [painting_job("stube", a.variant, "stube"),
                                 painting_job("klippe", a.variant, "klippe"),
                                 mask_job("leuchtturm", f"leuchtturm_{a.variant}")])
    return 0


if __name__ == "__main__":
    sys.exit(main())
