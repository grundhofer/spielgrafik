#!/usr/bin/env python3
"""Ortsserie, Stil painterly-digital: alle Messwerte -> measure.json (aus Dateien, deterministisch).

    .venv/bin/python -I styles/ortsserie/painterly-digital/scripts/measure.py

Inhalt
  anchor            Hafen-Anker des Stils (styles/painterly-digital/assets/raw/master.png, agy) und seine Maße
  generations       jede Bilderzeugung dieses Eintrags (Reihenfolge, Ziel, Sekunden, gelieferte Größe, verbatim)
  experiment_ab     je Ort Variante A (Anker als Stilreferenz) gegen B (nur Stilblock): Layout-Kopie, Palette,
                    Detail; dazu Bezugswerte (unabhängige Bilder, gleiches Motiv)
  locations         je Ort der verwendeten Fassung: Versuche, erster Versuch brauchbar, Sekunden, Größe,
                    Palettenabstand und Detailmaß zum Anker, Layout-Ähnlichkeit, Ruhe der Textfläche,
                    Ausrichtung der Maske, Handarbeit (Override-Einträge, Zahlenwerte, geschätzte Minuten)
  codex_series      dieselben Maße für die Codex-Serie aus styles/hintergrund-serie (Folgebilder gegen deren Hafen)
Maße siehe metrics.py. Bewertungen „brauchbar“ und Minuten sind eigene Sichtprüfung bzw. Schätzung (manual).
"""
import json, pathlib, sys

import numpy as np
from PIL import Image

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import metrics as M  # noqa: E402

E = HERE.parent
ROOT = E.parents[2]
RAW = E / "assets" / "raw"
ANCHOR = ROOT / "styles/painterly-digital/assets/raw/master.png"
HS = ROOT / "styles/hintergrund-serie/assets"
UI_RECT = (20, 536, 1240, 164)
H_ROW = 270

# Reihenfolge der Erzeugungen (alle mit genimg.py --backend agy), siehe NOTES.md
GENERATIONS = ["leuchtturm_a", "leuchtturm_b", "stube", "klippe", "leuchtturm_mask", "stube_mask", "klippe_b",
               "klippe_mask", "stube_b"]
VARIANTS = {"leuchtturm": {"a": "leuchtturm_a", "b": "leuchtturm_b"},
            "stube": {"a": "stube", "b": "stube_b"},
            "klippe": {"a": "klippe", "b": "klippe_b"}}
USED = {"leuchtturm": "a", "stube": "a", "klippe": "b"}

# Eigene Sichtprüfung und Schätzung (nicht gemessen)
MANUAL = {
    "leuchtturm": {
        "first_try_ok": True,
        "look": ("Malweise, Himmel in den Fenstern und Palette wie im Hafen; heller gekalkte Wände und eine "
                 "fein gezeichnete Wendeltreppe machen das Bild detailreicher als den Anker. Unten ein flacher "
                 "dunkler Streifen (Textleistenzone wörtlich genommen), liegt unter der Textleiste."),
        "minutes": {"override": 5, "effektplanung": 25, "pruefen": 15},
        "handwork_note": ("Linse: Rechteck um die Glasringe (Maske hatte den Messingsockel mit eingefärbt). "
                          "Effektplanung (Linsenblitz, wandernder Lichtfleck, Fensternebel, Lichtteilchen) im "
                          "FX-Block von process.py, Werte nach zwei Probeaufnahmen."),
    },
    "stube": {
        "first_try_ok": True,
        "look": ("Gleiche Pinselführung und Dunst; kühles Petrol mit warmem Kamin und Kerze, im Fenster Hafen "
                 "und Leuchtturm. Kamin mit kleinen gemalten Flammen und einzelnen Funken trotz Verbot. Dunkler "
                 "als der Anker (mehr Fläche im Schatten), flacher Streifen unten."),
        "minutes": {"override": 15, "effektplanung": 25, "pruefen": 20},
        "handwork_note": ("Flammen über Glut und Docht: Basis als Anteil der Maskenhöhe und Größe nach "
                          "Augenmaß an Probeaufnahmen (8 Zahlen). Kerze in der Maske samt Kerzenkörper."),
    },
    "klippe": {
        "first_try_ok": False,
        "look": ("Fassung B (ohne Referenz): Himmel, Nebel über dem Meer, Leuchtturm und Palette wie im Hafen, "
                 "Detail fast gleich (1,03x). Fassung A (mit Referenz) übernahm Wolkenbild, Leuchtturmlage und "
                 "die Kaimauer des Ankers und wurde verworfen. Unten flacher Streifen."),
        "minutes": {"override": 8, "effektplanung": 25, "pruefen": 15},
        "handwork_note": ("Laterne am Wegweiser als zusätzliches Licht (nicht im Farbcode verlangt), Lage per "
                          "Skript als hellster warmer Punkt gemessen. Gras, Strahl, Möwen, Nebel im FX-Block."),
    },
}


def rel(p):
    return pathlib.Path(p).resolve().relative_to(ROOT).as_posix()


def meta(name):
    p = RAW / f"{name}.json"
    return json.loads(p.read_text()) if p.exists() else {}


def anchor_still():
    """Anker wie die Orte geschnitten (Horizont auf Zeile 270) für den Vergleich der Textfläche."""
    im = Image.open(ANCHOR).convert("RGB")
    ch = round(im.width * 9 / 16)
    h_src = 402  # Horizont des Ankers: Median der stärksten Hell-Dunkel-Kante je Spalte (x 380-900), gemessen
    y0 = int(round(np.clip(h_src - H_ROW * ch / 720, 0, im.height - ch)))
    return im.crop((0, y0, im.width, y0 + ch)).resize((1280, 720), Image.LANCZOS)


def count_leaves(x):
    if isinstance(x, dict):
        return sum(count_leaves(v) for k, v in x.items() if not k.startswith("_"))
    if isinstance(x, list):
        return sum(count_leaves(v) for v in x)
    return 1


def main():
    fa = M.layout_features(ANCHOR)
    pa = M.palette_features(ANCHOR)
    da = M.detail_features(ANCHOR)
    calm_anchor = M.calm(anchor_still(), UI_RECT)
    out = {"anchor": {"file": rel(ANCHOR), "detail": da, "textbar_calm": calm_anchor,
                      "note": "agy-Hauptbild des Eintrags painterly-digital, 1264x848"},
           "metric_notes": {
               "layout": ("gray_corr/edge_corr/struct_corr/struct_top siehe scripts/metrics.py; struct_corr ist "
                          "das Maß für Layout-Kopie (gleiche Formen an gleicher Stelle)"),
               "palette": "Oklab x 100: palette_matched (8 Farben, 1:1 zugeordnet), palette_chamfer (12), mean_dE",
               "detail": "Verhältnis zum Anker bei 1264 px Breite (grad_energy, edge_density, texture_energy)",
               "textbar_calm": ("Rechteck der Textleiste (20, 536, 1240x164) im geschnittenen 1280x720-Bild: "
                                "Streuung und Gradient der Helligkeit (Oklab L x 100); Anker gleich geschnitten"),
           }}

    gens = []
    for n in GENERATIONS:
        m = meta(n)
        gens.append({"name": n, "file": f"assets/raw/{n}.png", "backend": m.get("backend"),
                     "seconds": m.get("seconds"), "actual_size": m.get("actual_size"),
                     "verbatim": m.get("verbatim"), "refs": m.get("refs", [])})
    out["generations"] = gens
    out["image_generations"] = len(gens)
    out["failed_calls"] = sorted(p.name for p in RAW.glob("*.fail.json"))

    ind = {f"hintergrund-serie/{n}": HS / f"raw/{n}.png" for n in ("leuchtturm", "stube", "klippe")}
    base_ind = {k: M.layout_similarity(fa, M.layout_features(v)) for k, v in ind.items()}
    base_same = {"kinemagramm/bg (Codex-Hafen)": M.layout_similarity(
        fa, M.layout_features(ROOT / "styles/kinemagramm/assets/raw/bg.png"))}
    exp = {"baseline_independent": base_ind, "baseline_same_motif": base_same, "places": {}}
    feats = {}
    for ort, vv in VARIANTS.items():
        row = {}
        for v, name in vv.items():
            p = RAW / f"{name}.png"
            f = M.layout_features(p)
            feats[(ort, v)] = f
            d = M.detail_features(p)
            row[v] = {"file": f"assets/raw/{name}.png", "with_reference": v == "a",
                      "layout_vs_anchor": M.layout_similarity(fa, f),
                      "palette_vs_anchor": M.palette_distance(M.palette_features(p), pa),
                      "detail_vs_anchor": M.detail_ratio(d, da)}
        row["a_vs_b_layout"] = M.layout_similarity(feats[(ort, "a")], feats[(ort, "b")])
        row["used"] = USED[ort]
        exp["places"][ort] = row
    exp["decision"] = (
        "Nach leuchtturm: A für die Serie (keine Layout-Kopie messbar, struct_corr 0,02 wie unabhängige Bilder; "
        "Palette nach zwei von drei Maßen näher; Himmel in den Fenstern am nächsten am Anker; Ortsinhalt treuer). "
        "Preis: gut ein Drittel mehr Detail als B (Gradientenenergie 1,85 gegen 1,36 × Anker). Im gemeinsamen "
        "Einheitsmaß der Ortsserie (styles/ortsserie/assets/einheitsmass.json) lag B näher am Anker (Palette 1,97 "
        "gegen 2,41, Detail ×1,41 gegen ×1,83); dort sprechen für A nur die Helligkeit (L 46,5 gegen 43,2, Anker "
        "46,3) und der Inhalt (Wendeltreppe, Himmel in den Fenstern). Das Detail ×1,83 der Serie gehört zu "
        "Fassung A. stube mit A. klippe mit A übernahm Wolkenbild, Leuchtturmlage und "
        "Kaimauer des Ankers (struct_corr 0,215, Himmel 0,428): verworfen, klippe mit B neu erzeugt und verwendet. "
        "stube_b nur zum Vergleich erzeugt (dritter A/B-Punkt), nicht verarbeitet.")
    out["experiment_ab"] = exp

    over = json.loads((HERE / "scene.override.json").read_text())
    locs = {}
    for ort, v in USED.items():
        name = VARIANTS[ort][v]
        p = RAW / f"{name}.png"
        m = meta(name)
        scene = json.loads((E / "assets" / ort / "scene.json").read_text())
        rep = scene.get("_report", {})
        still = Image.open(E / "assets" / ort / "still.png").convert("RGB")
        tries = 2 if ort == "klippe" else 1
        secs = [meta(VARIANTS[ort]["a"]).get("seconds")] + ([m.get("seconds")] if ort == "klippe" else [])
        o = {k: x for k, x in over.get(ort, {}).items() if not k.startswith("_")}
        mm = MANUAL[ort]
        locs[ort] = {
            "painting": f"assets/raw/{name}.png", "variant": v, "with_reference": v == "a",
            "mask": f"assets/raw/{ort}_mask.png",
            "tries_painting": tries, "tries_mask": 1, "first_try_ok": mm["first_try_ok"],
            "seconds_painting": secs, "seconds_mask": meta(f"{ort}_mask").get("seconds"),
            "actual_size": m.get("actual_size"), "mask_size": meta(f"{ort}_mask").get("actual_size"),
            "palette_vs_anchor": M.palette_distance(M.palette_features(p), pa),
            "detail_vs_anchor": M.detail_ratio(M.detail_features(p), da),
            "layout_vs_anchor": M.layout_similarity(fa, M.layout_features(p)),
            "textbar_calm": M.calm(still, UI_RECT),
            "textbar_calm_vs_anchor": {k: round(M.calm(still, UI_RECT)[k] / calm_anchor[k], 2)
                                       for k in ("L_std", "grad_mean")},
            "horizon_src_share": rep.get("horizon_src_share"), "crop_box": rep.get("crop_box"),
            "mask_align": rep.get("align"), "lights": rep.get("lights"),
            "handwork": {"override_entries": len(o), "override_numbers": count_leaves(o),
                         "minutes_estimate": mm["minutes"], "minutes_total": sum(mm["minutes"].values()),
                         "note": mm["handwork_note"]},
            "look_match": mm["look"],
        }
    out["locations"] = locs

    # Codex-Serie (hintergrund-serie) mit denselben Maßen: Folgebilder gegen deren Anker (Codex-Hafen)
    ca = HS / "raw/hafen.png"
    cfa, cpa, cda = M.layout_features(ca), M.palette_features(ca), M.detail_features(ca)
    cs = {}
    for n in ("leuchtturm", "stube", "klippe"):
        p = HS / f"raw/{n}.png"
        cs[n] = {"layout_vs_anchor": M.layout_similarity(cfa, M.layout_features(p)),
                 "palette_vs_anchor": M.palette_distance(M.palette_features(p), cpa),
                 "detail_vs_anchor": M.detail_ratio(M.detail_features(p), cda)}
    out["codex_series"] = {"anchor": rel(ca), "note": "Codex (gpt-image), jedes Folgebild mit dem Hafen als "
                           "einziger Referenz, rohe Bilder vor der LUT", "places": cs}
    (E / "measure.json").write_text(json.dumps(out, ensure_ascii=False, indent=1) + "\n")
    print(json.dumps({k: {kk: vv for kk, vv in v.items() if kk in ("palette_vs_anchor", "detail_vs_anchor",
                                                                     "layout_vs_anchor", "textbar_calm_vs_anchor")}
                      for k, v in locs.items()}, ensure_ascii=False, indent=1))
    print(json.dumps(exp["places"], ensure_ascii=False)[:3000])
    print(json.dumps(cs, ensure_ascii=False))


if __name__ == "__main__":
    main()
