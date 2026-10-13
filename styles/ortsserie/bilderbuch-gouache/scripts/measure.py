#!/usr/bin/env python3
"""Messwerte der Ortsserie bilderbuch-gouache → measure.json (im Stilordner der Ortsserie).

    .venv/bin/python -B styles/ortsserie/bilderbuch-gouache/scripts/measure.py

Alle Bildmaße auf 1280x720 (gmetrics.py). Anker = Hafen des Eintrags bilderbuch-gouache, wie er im Spiel steht
(styles/bilderbuch-gouache/assets/bg.png: bemalte Fläche ohne Papierrand).
  orte[*]            Maße am Spielbild assets/bg_<ort>.png; layout_sim_model_output zusätzlich am mittigen Schnitt
                     (die Klippe ist im Spielbild auf den Hafen-Horizont geschnitten, das erhöht die Grau-Korrelation
                     absichtlich; für die Frage „kopiert agy das Layout?“ zählt der mittige Schnitt)
  experiment         A und B beide im mittigen Schnitt der Modellausgabe (paperframe.crop_box, dy = 0)

Vergleichsgrößen für die Layout-Kopie
  same_motif   Anker gegen die Hafenbilder aller anderen Einträge (gleiches Motiv, andere Hand): so ähnlich
               werden zwei Bilder, wenn sie dasselbe zeigen
  independent  Anker gegen Leuchtturm, Stube und Klippe der Codex-Serie (hintergrund-serie): andere Orte
Codex-Serie zum Vergleich: dieselben Maße für hintergrund-serie (Anker dort: bg_hafen.png, Farben vor der LUT).
"""
import json, pathlib, sys

import numpy as np
from PIL import Image

sys.dont_write_bytecode = True
HERE = pathlib.Path(__file__).resolve().parent
SD = HERE.parent
ROOT = HERE.parents[3]
sys.path.insert(0, str(HERE))
import gmetrics as G  # noqa: E402
import paperframe as PF  # noqa: E402

A = SD / "assets"
RAW = A / "raw"
ANCHOR = ROOT / "styles/bilderbuch-gouache/assets/bg.png"
ANCHOR_RAW_JSON = ROOT / "styles/bilderbuch-gouache/assets/raw/bg.json"
HS = ROOT / "styles/hintergrund-serie/assets"
ANCHOR_TEXT_RECT = [300, 14, 980, 132]   # Titel + zwei Satzzeilen im Hafen (main.gd: Titel y 20, Satz ab y 48)

# Aufrufe je Ziel, die das Bildmodell erreicht haben (genimg.py-Ausgaben; .fail.json belegt den Fehlschlag)
TRIES = {"leuchtturm_a": 2, "leuchtturm_b": 1, "stube": 1, "klippe": 1, "klippe_b": 1}
FIRST_OK = {"leuchtturm_a": False, "leuchtturm_b": True, "stube": True, "klippe": True, "klippe_b": True}
FIRST_NOTE = {"leuchtturm_a": "1. Aufruf: agy meldete „image failed to generate: no image generated in response“ "
                              "(kein Bild, zählt als Erzeugung); 2. Aufruf brauchbar"}
CHOSEN = {"leuchtturm": "leuchtturm_a", "stube": "stube", "klippe": "klippe"}
# Handarbeit in Minuten (eigene Schätzung): Raster-Ausschnitte erzeugen und ansehen, Werte ablesen und eintragen,
# einmal im Godot-Bild prüfen. Einmalige Entwicklung (Effekte, Grasmaske, Textplatzierung) ist nicht enthalten.
MINUTES = {"leuchtturm": 10, "stube": 12, "klippe": 12}


def side(name):
    p = RAW / f"{name}.json"
    return json.loads(p.read_text()) if p.exists() else None


def centered(name):
    """Modellausgabe ohne Papierrand im mittigen 16:9-Schnitt (gleiche Regel für alle Varianten des Experiments)."""
    raw = np.asarray(Image.open(RAW / f"{name}.png").convert("RGB"))
    x0, y0, x1, y1, _ = PF.crop_box(raw, 0)
    return np.asarray(Image.fromarray(raw).crop((x0, y0, x1, y1)).resize((1280, 720), Image.LANCZOS))


def image_metrics(img, anchor, d_anchor):
    d = G.detail(img)
    return {"layout_sim_to_anchor": G.layout_sim(anchor, img),
            "palette_dE_to_anchor": G.palette_de(anchor, img)[0],
            "palette_dE_sd": G.palette_de(anchor, img)[1],
            "mean_oklab_L_a_b_C": G.mean_lab(img),
            "detail": d,
            "detail_rel_anchor": {k: round(d[k] / d_anchor[k], 2) for k in d}}


def gen_info(name):
    s = side(name)
    if not s:
        return None
    return {"seconds": s.get("seconds"), "size_requested": s.get("size"), "size_delivered": s.get("actual_size"),
            "backend": s.get("backend"), "verbatim": s.get("verbatim"), "refs": s.get("refs", []),
            "tries": TRIES.get(name), "first_try_ok": FIRST_OK.get(name), "note": FIRST_NOTE.get(name, "")}


def prompt_check(name):
    """Prompt in der Begleitdatei = Prompt in assets/prompts/<name>.txt (keine stille Änderung nach dem Erzeugen)."""
    s = side(name)
    p = A / "prompts" / f"{name}.txt"
    return bool(s and p.exists() and s["prompt"].strip() == p.read_text().strip())


def main():
    anchor = G.load(ANCHOR)
    dA = G.detail(anchor)
    # Vergleichsgrößen
    same = []
    for p in sorted(ROOT.glob("styles/*/assets/bg.png")):
        if "bilderbuch-gouache" in str(p):
            continue
        s = G.layout_sim(anchor, G.load(p))
        same.append([p.parts[-3], s["gray_r"], s["edge_r"]])
    sm = np.array([[x[1], x[2]] for x in same])
    indep = {o: G.layout_sim(anchor, G.load(HS / f"bg_{o}.png")) for o in ("leuchtturm", "stube", "klippe")}
    baseline = {
        "same_motif": {"n": len(same), "gray_r_mean": round(float(sm[:, 0].mean()), 3),
                       "gray_r_sd": round(float(sm[:, 0].std()), 3), "edge_r_mean": round(float(sm[:, 1].mean()), 3),
                       "edge_r_sd": round(float(sm[:, 1].std()), 3), "edge_r_max": round(float(sm[:, 1].max()), 3),
                       "gray_r_max": round(float(sm[:, 0].max()), 3)},
        "independent_codex_places": indep,
        "anchor_detail": dA,
        "palette_dE_noise_floor": {"anchor_vs_itself": G.palette_de(anchor, anchor)[0],
                                   "note": "derselbe Anker gegen sich selbst mit verschiedenen Seeds; Werte in "
                                           "dieser Größe bedeuten keinen Unterschied"},
        "anchor_text_area": {"rect": ANCHOR_TEXT_RECT, "calm": G.calm(anchor, ANCHOR_TEXT_RECT),
                             "contrast_cream": G.contrast((248, 236, 214), anchor, ANCHOR_TEXT_RECT)},
        "anchor_generation": {"seconds": json.loads(ANCHOR_RAW_JSON.read_text()).get("seconds"),
                              "size_delivered": json.loads(ANCHOR_RAW_JSON.read_text()).get("actual_size")},
    }
    build = json.loads((A / "build.json").read_text())
    # Orte
    orte = {}
    for ort, name in CHOSEN.items():
        img = G.load(A / f"bg_{ort}.png")              # Spielbild (Außenorte auf den Hafen-Horizont geschnitten)
        b = build[ort]
        hw = dict(b["handwork"])
        hw["minutes_estimate"] = MINUTES[ort]
        orte[ort] = {
            "raw": f"assets/raw/{name}.png", "variant": "A (Hafenbild des Stils als Stilreferenz)",
            "generation": gen_info(name), "prompt_matches_file": prompt_check(name),
            **image_metrics(img, anchor, dA),
            "layout_sim_model_output": G.layout_sim(anchor, centered(name)),
            "text_area": {"rect": b["text"]["rect"], "lines": b["text"]["lines"], "scheme": b["text"]["scheme"],
                          "calm": b["text"]["calm"], "contrast_text": b["text"]["contrast"],
                          "band_needed": bool(b["text"]["band"])},
            "crop": b["crop"], "horizon_row": b["horizon_row"], "auto_found": b["auto"], "handwork": hw,
        }
    # Experiment
    exp = {"question": "Kopiert agy das Layout des Hafenbilds, wenn es als Stilreferenz mitgeht, und hält die "
                       "Referenz den Strich besser als der Stilblock allein?",
           "A": "Ankerabsatz (nur Malweise übernehmen) + Hafenbild des Stils als einzige Referenz",
           "B": "derselbe Prompt ohne Ankerabsatz und ohne Referenz",
           "pairs": {}}
    for ort, (a, bname) in {"leuchtturm": ("leuchtturm_a", "leuchtturm_b"), "klippe": ("klippe", "klippe_b")}.items():
        if not (RAW / f"{bname}.png").exists():
            continue
        exp["pairs"][ort] = {v: {"raw": f"assets/raw/{n}.png", "generation": gen_info(n),
                                 "prompt_matches_file": prompt_check(n), **image_metrics(centered(n), anchor, dA)}
                             for v, n in (("A", a), ("B", bname))}
    exp["decision"] = "A"
    exp["reason"] = ("A kopiert das Hafen-Layout nicht (Kanten-r 0,15 und 0,13, unter dem Wert für gleiches Motiv "
                     "0,19 ± 0,05 und unter B mit 0,22 und 0,20) und hält den Detailgrad des Ankers (Gradient ×1,38 "
                     "und ×1,03 gegen B ×2,50 und ×1,38); B malt dünne dunkle Konturen und Motiv-Klischees (Häuser "
                     "und Wolken im Lampenraum, Häuschen auf der Klippe). Palettenabstand gemischt: Leuchtturm B "
                     "näher (3,23 gegen 3,82), Klippe A näher (2,49 gegen 3,20); Streuung des Maßes ±0,3–0,4.")
    # Codex-Serie mit denselben Maßen
    hs_anchor = G.load(HS / "bg_hafen.png")
    dH = G.detail(hs_anchor)
    codex = {o: {"layout_sim_to_anchor": G.layout_sim(hs_anchor, G.load(HS / f"bg_{o}.png")),
                 "palette_dE_to_anchor": G.palette_de(hs_anchor, G.load(HS / f"bg_{o}.png"))[0],
                 "detail_rel_anchor": {k: round(v / dH[k], 2) for k, v in G.detail(G.load(HS / f"bg_{o}.png")).items()}}
             for o in ("leuchtturm", "stube", "klippe")}
    out = {
        "style": "bilderbuch-gouache",
        "backend": "agy (fest gewählt, genimg.py --backend agy)",
        "generations": {"total": sum(TRIES.values()), "budget": 10, "by_target": TRIES},
        "methods": {
            "layout_sim": "Pearson-r der Graustufen (64x36) und der weichgezeichneten Sobel-Kantenbilder (80x45), "
                          "beide Bilder 1280x720 ohne Papierrand",
            "palette_dE": "k-means (k=12) in Oklab je Bild, jede Farbe zur nächsten des anderen Bildes, nach "
                          "Flächenanteil gewichtet, symmetrisch gemittelt; ΔE = Oklab-Abstand × 100; Mittel über 8 "
                          "Seeds (palette_dE_sd = Streuung), Rauschboden in baseline.palette_dE_noise_floor",
            "detail": "grad_energy = mittlerer |∇L| (Oklab) × 100; edge_density = Anteil |∇L| > 0,03; "
                      "texture_energy = mittlere Abweichung der 8-bit-Helligkeit vom 3-px-Weichzeichner "
                      "(wie hintergrund-serie/drift.json)",
            "text_area": "Rechteck des Textblocks (Titel + Satz); L_std und grad_energy wie oben; "
                         "Kontrast = WCAG-Kontrast der Satzfarbe gegen jedes Hintergrundpixel (Median, 5-%-Quantil)",
        },
        "baseline": baseline,
        "orte": orte,
        "experiment": exp,
        "codex_series_same_metrics": {"anchor": "styles/hintergrund-serie/assets/bg_hafen.png (vor der LUT)",
                                      "orte": codex},
    }
    (SD / "measure.json").write_text(json.dumps(out, ensure_ascii=False, indent=1) + "\n")
    for o, v in orte.items():
        print(o, v["layout_sim_to_anchor"], v["palette_dE_to_anchor"], v["detail_rel_anchor"],
              v["text_area"]["calm"]["L_std"], v["generation"]["seconds"])
    for o, p in exp["pairs"].items():
        for k, v in p.items():
            print("exp", o, k, v["layout_sim_to_anchor"], v["palette_dE_to_anchor"], v["detail_rel_anchor"])
    for o, v in codex.items():
        print("codex", o, v)
    print("baseline", baseline["same_motif"], indep)


if __name__ == "__main__":
    main()
