#!/usr/bin/env python3
"""Bildaufträge der Ortsserie im Stil bilderbuch-gouache (Format genimg.py --jobs, Pfade relativ zum Projektordner).

    .venv/bin/python -B styles/ortsserie/bilderbuch-gouache/scripts/make_jobs.py [--variant A|B]

Prompt eines Ortes = [nur Variante A: Ankerabsatz] + Stilblock + Bildaufbau mit Serienregeln + Ortsblock
+ Effekte, die Godot animiert + freier Boden + Schutzregeln + Format.

Herkunft der Bausteine
  Stilblock    styles/bilderbuch-gouache/scripts/make_jobs.py STYLE_BG. Satz 1, 2 und 6 wörtlich; in Satz 3–5 sind
               nur die Hafen-Gegenstände (Leuchtturm, Häuschen, Kai) durch allgemeine Wörter ersetzt, sonst wörtlich.
  Bildaufbau   erster Satz wörtlich aus COMPOSITION_BG (16:9-Schnitt), danach die Serienregeln: Abend wie der
               Hafen, Licht, Horizont 46 % wie im Hafen-Prompt, Laufband ab 70 % wie der Kai, ruhige Textfläche
               25–72 % Breite bis 33 % Höhe wie der Himmel im Hafen-Prompt (innen Wand oder Decke).
  Ortsblock    LOCATIONS[ort]["block"], ["anim"] (+ ANIM_TAIL), ["anchor_extra"] und FREE_EN wörtlich aus
               styles/hintergrund-serie/tools/prompts.py (importiert, ohne Bytecode-Cache in fremden Ordnern).
  Ankerabsatz  ANCHOR_EN aus hintergrund-serie; „a watercolour of a harbour“ → „a gouache painting of a harbour“
               und „washes“ → „flat opaque colour shapes“ (Gouache statt Aquarell), sonst wörtlich.
  guards_en    wörtlich aus data/motif.json.

Aufträge
  assets/jobs_ab.json      Experiment am Leuchtturm: raw/leuchtturm_a.png (Referenz: Hafenbild des Stils,
                           styles/bilderbuch-gouache/assets/raw/bg.png) und raw/leuchtturm_b.png (ohne Referenz)
  assets/jobs_serie.json   stube und klippe in der gewählten Variante (--variant, Standard aus VARIANT unten)
  assets/jobs_ab_klippe.json  Nachprüfung des Experiments an einem Außenort: raw/klippe_b.png (ohne Referenz)
Lesbare Prompts: assets/prompts/<name>.txt
"""
import json, pathlib, sys

sys.dont_write_bytecode = True   # nichts in fremde Ordner schreiben (__pycache__)
ROOT = pathlib.Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT / "styles/hintergrund-serie/tools"))
import prompts as HS  # noqa: E402  (hintergrund-serie: LOCATIONS, FREE_EN, ANIM_TAIL, ANCHOR_EN)

S = "styles/ortsserie/bilderbuch-gouache"
RAW = f"{S}/assets/raw"
ANCHOR_REF = "styles/bilderbuch-gouache/assets/raw/bg.png"   # Hafenbild des Stils (agy, 1264x848, mit Papierrand)
M = json.loads((ROOT / "data/motif.json").read_text())

# Nach dem A/B-Experiment am Leuchtturm gewählt (Begründung: measure.json → experiment, NOTES.md)
VARIANT = "A"

STYLE = (
    "Hand-painted illustration from a classic children's picture book, painted with opaque gouache on warm off-white "
    "watercolour paper. Matte, chalky, fully opaque paint laid down in flat colour shapes with visible brush marks; "
    "dry-brush edges where the paper grain shows through; lighter colours painted on top of darker ones; fine flecks "
    "of paper texture everywhere. Simple, rounded, friendly shapes for young children: soft round cloud shapes, "
    "plump, slightly leaning buildings and furniture, soft wobbly walls, round smooth rocks, naive, slightly "
    "flattened perspective. Few large objects and very little small detail: stones, planks and floorboards only "
    "hinted with a few loose rounded dabs, no fine rigging, no fine wood grain, no tiny flowers. Warm limited "
    "palette of mixed gouache colours: apricot, peach and coral glow along the horizon, warm dusty teal and deep "
    "warm blue in the upper sky and the sea, ochre, terracotta, sage green and cream on buildings, walls, wood and "
    "stone; the darkest colour is a warm deep blue-violet, never black. Soft, calm dusk light with gentle contrast. "
    "No black outlines. Not a photograph, not a 3D render, not smooth digital airbrush, not a detailed postcard, not "
    "transparent watercolour, not an oil painting."
)

COMPOSITION = (
    "Composition for a fixed side-view adventure game screen. The picture will be cropped to a wide 16:9 format: "
    "the top 8% and the bottom 8% are cut off, so keep everything important inside the middle band. Series rules, "
    "identical for every picture of this series: Time of day: dusk, shortly after sunset; outdoors and in the "
    "windows the sky is warm dusty teal and deep warm blue with a band of apricot, peach and coral light at the "
    "horizon and the first small stars. Light: soft, calm dusk light with gentle contrast; lamps, windows and fires "
    "are small warm spots of light. Camera: straight-on view at standing eye height, vertical lines stay vertical; "
    "the horizon (indoors: the horizon seen through the windows) at about 46% of the picture height. The floor or "
    "ground where characters walk runs as one continuous, level band across the whole width of the picture, from "
    "about 70% of the picture height down to the bottom edge; this broad strip is free and walkable from left to "
    "right, furniture and objects stand at its back edge or at the far left and right, the middle stays free. The "
    "upper middle of the picture, between 25% and 72% of the width and down to about 33% of the picture height, is "
    "a calm, almost empty area of flat colour (outdoors the sky with only a few small stars, indoors a plain stretch "
    "of wall or ceiling): the story text of the page will be placed there."
)

ANCHOR = (HS.ANCHOR_EN.replace("a watercolour of a harbour", "a gouache painting of a harbour")
          .replace("brush handling, washes, edges", "brush handling, flat opaque colour shapes, edges"))
assert ANCHOR != HS.ANCHOR_EN and "gouache painting of a harbour" in ANCHOR and "flat opaque colour" in ANCHOR

REF_NOTE = "Take only the painting technique, the paper and the palette from it, not its composition or objects."
ORTE = ["leuchtturm", "stube", "klippe"]


def prompt(ort, variant):
    d = HS.LOCATIONS[ort]
    parts = []
    if variant == "A":
        parts.append(ANCHOR.format(extra=d["anchor_extra"]))
    parts += [STYLE, COMPOSITION, d["block"], d["anim"] + HS.ANIM_TAIL, HS.FREE_EN, M["guards_en"],
              "Image format: landscape 3:2."]
    return "\n\n".join(parts)


def job(ort, variant, name=None):
    j = {"out": f"{RAW}/{name or ort}.png", "size": "1536x1024", "prompt": prompt(ort, variant), "refs": []}
    if variant == "A":
        j["refs"] = [ANCHOR_REF]
        j["ref_note"] = REF_NOTE
    return j


def main():
    variant = sys.argv[sys.argv.index("--variant") + 1] if "--variant" in sys.argv else VARIANT
    a = ROOT / S / "assets"
    ab = [job("leuchtturm", "A", "leuchtturm_a"), job("leuchtturm", "B", "leuchtturm_b")]
    serie = [job(o, variant) for o in ORTE[1:]]
    ab2 = [job("klippe", "B", "klippe_b")]
    (a / "jobs_ab.json").write_text(json.dumps(ab, ensure_ascii=False, indent=1) + "\n")
    (a / "jobs_serie.json").write_text(json.dumps(serie, ensure_ascii=False, indent=1) + "\n")
    (a / "jobs_ab_klippe.json").write_text(json.dumps(ab2, ensure_ascii=False, indent=1) + "\n")
    (a / "prompts").mkdir(exist_ok=True)
    for j in ab + serie + ab2:
        (a / "prompts" / (pathlib.Path(j["out"]).stem + ".txt")).write_text(j["prompt"] + "\n")
    for j in ab + serie + ab2:
        print(f"{j['out']}  {len(j['prompt'])} Zeichen  refs={j['refs']}")


if __name__ == "__main__":
    main()
