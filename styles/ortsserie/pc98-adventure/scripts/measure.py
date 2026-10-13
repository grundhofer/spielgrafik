#!/usr/bin/env python3
"""Schreibt styles/ortsserie/pc98-adventure/measure.json: Messwerte der agy-Ortsserie im Stil pc98-adventure.

    .venv/bin/python styles/ortsserie/pc98-adventure/scripts/measure.py [--frames <Ordner mit <ort>/f*.png>]

Rohbildmaße (metrics.py) gegen den Hafen-Anker des Stils (styles/pc98-adventure/assets/raw/bg.png):
Layout-Ähnlichkeit (Graustufen- und Kantenkorrelation, Kachelvergleich), Palettenabstand (gematchte k-means-
Farben, Oklab-ΔE), Detailmaß (Gradientenenergie, Kantendichte) relativ zum Anker, Pseudo-Pixelraster, Ruhe der
Porträtzone. Basis: dieselben Maße zwischen unabhängigen Bildern (Anker gegen die Codex-Bilder der
hintergrund-serie, Codex-Bilder untereinander). Verarbeitung: assets/build_stats.json (build_ort.py). Godot:
optional Einzelbilder einer Testaufnahme (16 Farben, 12-Bit-Raster, Bewegungsanteil).
"""
import argparse, itertools, json, pathlib, re, sys

sys.dont_write_bytecode = True
HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import numpy as np  # noqa: E402
from PIL import Image  # noqa: E402

import metrics as M  # noqa: E402
import build_ort  # noqa: E402

SD = HERE.parent
ROOT = SD.parents[2]
REL = lambda p: str(pathlib.Path(p).resolve().relative_to(ROOT))  # noqa: E731
ANCHOR = ROOT / "styles/pc98-adventure/assets/raw/bg.png"
RAW = SD / "assets/raw"
CODEX = {k: ROOT / f"styles/hintergrund-serie/assets/raw/{k}.png" for k in ("hafen", "leuchtturm", "stube", "klippe")}
ORTE = ["leuchtturm", "stube", "klippe"]

# Versuche und Bewertung (eigene Sichtprüfung, siehe NOTES.md); Bildnamen in assets/raw/
VERSUCHE = {
    "leuchtturm": {"bilder": ["leuchtturm_a", "leuchtturm_b", "leuchtturm"], "serie": "leuchtturm",
                   "erster_versuch_brauchbar": True,
                   "anmerkung": "Experiment A (mit Anker) und B (ohne) waren beide brauchbar, hatten aber einen "
                                "gemalten Bildrahmen (Serienregel „framed window“); das Serienbild ist der erste "
                                "Versuch mit korrigierter Serienregel (Variante A)."},
    "stube": {"bilder": ["stube"], "serie": "stube", "erster_versuch_brauchbar": True,
              "anmerkung": "Ein Versuch; zusätzlich ein Fass, das der Ortsblock nicht nennt."},
    "klippe": {"bilder": ["klippe", "klippe_b"], "serie": "klippe", "erster_versuch_brauchbar": True,
               "anmerkung": "Brauchbar, aber Himmel, Wolken und Leuchtturm oben rechts sind aus dem Anker kopiert "
                            "(Kachel r ≈ 1,0). klippe_b ist eine Gegenprobe ohne Referenz, kein Ersatz."},
}
MINUTEN = {"leuchtturm": "10–15", "stube": "15–20", "klippe": "10–15"}
MINUTEN_NOTE = ("geschätzt: Kästen und Mittelpunkte am 4-fach vergrößerten Rasterbild ablesen, Prüfbild mit "
                "eingefärbten Registern ansehen, 1–2 Korrekturen; dazu je Ort 3–5 Minuten für Texte. Ohne die "
                "einmalige Arbeit am Skript (Palettenwege, Tauschverfahren für Feuerschein).")


def raw_json(name):
    d = json.loads((RAW / f"{name}.json").read_text())
    return {"sekunden": d.get("seconds"), "geliefert": d.get("actual_size"), "angefragt": d.get("size"),
            "backend": d.get("backend"), "verbatim": d.get("verbatim"), "refs": d.get("refs", [])}


def raw_metrics(path, pal_anchor, det_anchor):
    det = M.detail(path)
    return {
        "layout_zum_anker": M.layout_similarity(ANCHOR, path),
        "kacheln_zum_anker": M.tile_copy(ANCHOR, path),
        "palette_zum_anker": M.palette_distance(pal_anchor, M.palette_of(path)),
        "detail": det,
        "detail_rel_anker": {"grad_energy": round(det["grad_energy"] / det_anchor["grad_energy"], 2),
                             "edge_density": round(det["edge_density"] / det_anchor["edge_density"], 2)},
        "pixelraster": M.pixel_style(path),
        "ruhe_portraetzone": M.calm_zone(path),
    }


def numbers_in(obj):
    if isinstance(obj, (int, float)) and not isinstance(obj, bool):
        return 1
    if isinstance(obj, (list, tuple)):
        return sum(numbers_in(x) for x in obj)
    if isinstance(obj, dict):
        return sum(numbers_in(v) for v in obj.values())
    return 0


def godot_checks(fdir):
    out = {}
    for o in ORTE:
        files = sorted((fdir / o).glob("f*.png"))
        if not files:
            continue
        fr = [np.asarray(Image.open(f).convert("RGB")) for f in files[:180]]
        cols = [len(np.unique(f.reshape(-1, 3), axis=0)) for f in fr]
        off12 = sum(int((f % 17 != 0).any()) for f in fr)
        win = lambda f: f[24:536, 24:856]  # noqa: E731  Bildfenster (12..428, 12..268 im 640er Raster) ×2
        ch = [float((win(fr[i]) != win(fr[i + 1])).any(-1).mean()) for i in range(len(fr) - 1)]
        anyc = np.zeros(win(fr[0]).shape[:2], bool)
        for i in range(len(fr) - 1):
            anyc |= (win(fr[i]) != win(fr[i + 1])).any(-1)
        txt = fr[150][2 * 280 + 2:2 * 348 - 2, 2 * 12 + 2:2 * 628 - 2]
        out[o] = {"bilder": len(fr), "farben_je_bild_min_max": [min(cols), max(cols)],
                  "bilder_ausserhalb_12bit": off12,
                  "bildfenster_aenderung_je_bild_mittel": round(float(np.mean(ch)), 4),
                  "bildfenster_aenderung_je_bild_max": round(float(max(ch)), 4),
                  "bildfenster_anteil_je_bewegt_6s": round(float(anyc.mean()), 4),
                  "textfenster_farben": int(len(np.unique(txt.reshape(-1, 3), axis=0))),
                  "ganzzahlig_x2": bool(all((f[0::2, 0::2] == f[1::2, 1::2]).all() for f in fr[::30]))}
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--frames", help="Ordner mit <ort>/f*.png aus der Godot-Testaufnahme")
    a = ap.parse_args()
    pal_anchor = M.palette_of(ANCHOR)
    det_anchor = M.detail(ANCHOR)
    stats = json.loads((SD / "assets/build_stats.json").read_text())

    basis = {"anker_vs_codex": {k: M.layout_similarity(ANCHOR, CODEX[k]) for k in ("leuchtturm", "stube", "klippe")},
             "codex_paare": {f"{x}-{y}": M.layout_similarity(CODEX[x], CODEX[y])
                             for x, y in itertools.combinations(CODEX, 2)},
             "codex_kacheln_hafen_klippe": M.tile_copy(CODEX["hafen"], CODEX["klippe"])["closest_tile"],
             "hinweis": ("Codex-Paare teilen dieselben Serienregeln (dunkles unteres Viertel, Horizont 40 %) und "
                         "korrelieren deshalb schon ohne Kopie mit 0,4–0,7 (grau). Ein reiner Dämmerungshimmel "
                         "ergibt auch zwischen unabhängigen Bildern eine Kachel an der Schwelle (Codex hafen/klippe, "
                         "mitte-oben: r = 0,91, |ΔL| = 0,03). Eine Kachel gilt deshalb erst zusammen mit der "
                         "Sichtprüfung als kopiert; bei klippe ist mitte-oben praktisch identisch (r = 1,00, "
                         "|ΔL| = 0,01) und rechts-oben mit Leuchtturm und Felsnase r = 0,93, |ΔL| = 0,02.")}
    raw = {}
    for n in ["leuchtturm_a", "leuchtturm_b", "leuchtturm", "stube", "klippe", "klippe_b"]:
        raw[n] = {"datei": REL(RAW / f"{n}.png"), **raw_json(n), **raw_metrics(RAW / f"{n}.png", pal_anchor, det_anchor)}

    gp = stats.get("gegenproben", {})
    experiment = {
        "ort": "leuchtturm",
        "A": {"beschreibung": "Hafenbild des Stils als Stilreferenz (Ankerabsatz: nur Machart, nicht Aufbau)",
              **raw["leuchtturm_a"], "verarbeitet_serienpalette_dE": gp.get("leuchtturm_a", {}).get("serie", {}).get("loss_static", {}).get("dE_mean")},
        "B": {"beschreibung": "ohne Referenz, nur Stilblock", **raw["leuchtturm_b"],
              "verarbeitet_serienpalette_dE": gp.get("leuchtturm_b", {}).get("serie", {}).get("loss_static", {}).get("dE_mean")},
        "A_vs_B_layout": M.layout_similarity(RAW / "leuchtturm_a.png", RAW / "leuchtturm_b.png"),
        "gemalter_rahmen_px": {"A": 22, "B": 34},
        "wahl": "A",
        "begruendung": ("A liegt in der Palette näher am Anker (ΔE 5,07 gegen 5,57), sein Pseudo-Pixelraster ist "
                        "dem des Ankers ähnlicher (Periode 2,88 gegen 3,11 px; B 8,65 px, also kein klares "
                        "Pixelraster) und der Himmel im Fenster hat dieselben Rasterbänder wie der Hafen (Sichtprüfung). "
                        "Layout-Kopie ist bei A nicht messbar: Kanten-Korrelation 0,25 wie B (0,26) und im Bereich "
                        "unabhängiger Bilder (0,15–0,32), keine Kachel kopiert. Die ruhigere Porträtzone (0,83 gegen "
                        "1,02) spricht ebenfalls für A."),
        "gegenprobe_klippe": {
            "A (Serienbild)": {k: raw["klippe"][k] for k in ("layout_zum_anker", "palette_zum_anker", "pixelraster")},
            "B (klippe_b, ohne Referenz)": {k: raw["klippe_b"][k] for k in ("layout_zum_anker", "palette_zum_anker",
                                                                             "pixelraster")},
            "befund": ("Mit Referenz übernahm agy beim Außenort die obere Bildhälfte des Ankers fast pixelgleich "
                       "(Himmel, Wolken, Leuchtturm auf der Felsnase an derselben Stelle; Pixelraster 3,11 px wie "
                       "der Anker, Deutlichkeit 203). Ohne Referenz entsteht ein eigener Aufbau, das Meer kommt aber "
                       "graulila statt dunkelblau (Palettenabstand 4,19 statt 2,52). Die Serienpalette rastert das "
                       "graulila Meer auch graulila (Verlust nur ΔE 2,73); sie vereinheitlicht die Farbwerte, nicht "
                       "den Farbton eines anders gemalten Bildes (Sichtprüfung assets/sheet.png). Bei A verliert der "
                       "kopierte, gesättigte Hafenhimmel in der Serienpalette mehr (ΔE 3,59)."),
        },
    }

    orte = {}
    for o in ORTE:
        s = stats[o]
        dm = s.get("demo_palette", "serie")
        cfg = build_ort.CONFIG[o]
        hand = dict(s[dm]["handwork"])
        hand["zahlen_von_hand"] = numbers_in({k: cfg[k] for k in ("crop_top", "glow", "lamp", "sea")})
        hand["minuten_geschaetzt"] = MINUTEN[o]
        hand["minuten_hinweis"] = MINUTEN_NOTE
        serie = VERSUCHE[o]["serie"]
        orte[o] = {
            "versuche": len(VERSUCHE[o]["bilder"]), "bilder": VERSUCHE[o]["bilder"],
            "erster_versuch_brauchbar": VERSUCHE[o]["erster_versuch_brauchbar"],
            "anmerkung": VERSUCHE[o]["anmerkung"],
            "sekunden_je_erzeugung": {n: raw[n]["sekunden"] for n in VERSUCHE[o]["bilder"]},
            "geliefert": raw[serie]["geliefert"],
            "palettenabstand_zum_anker_dE": raw[serie]["palette_zum_anker"]["dE_matched"],
            "detail_rel_anker": raw[serie]["detail_rel_anker"],
            "layout_aehnlichkeit_zum_anker": raw[serie]["layout_zum_anker"],
            "kopierte_kacheln": raw[serie]["kacheln_zum_anker"]["copied_tiles"],
            "kacheln_zum_anker": raw[serie]["kacheln_zum_anker"]["tiles"],
            "pixelraster": raw[serie]["pixelraster"],
            "ruhe_textflaeche": {
                "textfenster": "eigenes schwarzes Textfenster unter dem Bildfenster, überdeckt das Bild nicht",
                "portraetzone_gradient_rel_bild": raw[serie]["ruhe_portraetzone"],
                "anker_portraetzone_gradient_rel_bild": M.calm_zone(ANCHOR)},
            "verarbeitung": {
                "demo_palette": dm,
                "verlust_dE": {m: s[m]["loss_static"]["dE_mean"] for m in ("fixed", "serie", "own")},
                "verlust_dE_p90": {m: s[m]["loss_static"]["dE_p90"] for m in ("fixed", "serie", "own")},
                "groesste_verluste_hafenpalette": s["fixed"]["loss_static"]["groups"][:3],
                "groesste_verluste_serienpalette": s["serie"]["loss_static"]["groups"][:3],
                "farben_im_bild": s[dm]["colors_used"],
                "licht_register14_px": s[dm]["glow_px"], "blitz_register15_px": s[dm]["lamp_core_px"] + s[dm]["lamp_extra_px"],
                "blitz_aus_farbe": s[dm]["lamp_off"],
                "wasser_glanzstriche": s[dm]["water_dashes"], "wasser_geaenderte_px": s[dm]["water_changed_px"]},
            "handarbeit": hand,
        }

    # Dieselben Maße für die Codex-Serie (hintergrund-serie), Anker dort: Codex-Hafen
    cpal = M.palette_of(CODEX["hafen"])
    cdet = M.detail(CODEX["hafen"])
    codex = {}
    for o in ORTE:
        d = M.detail(CODEX[o])
        codex[o] = {"palette_zum_codex_hafen": M.palette_distance(cpal, M.palette_of(CODEX[o]))["dE_matched"],
                    "detail_rel_codex_hafen": round(d["grad_energy"] / cdet["grad_energy"], 2),
                    "layout_zum_codex_hafen": M.layout_similarity(CODEX["hafen"], CODEX[o]),
                    "kopierte_kacheln": M.tile_copy(CODEX["hafen"], CODEX[o])["copied_tiles"]}

    hafen = stats.get("hafen", {})

    # Gegenprobe Akzentfarben: Serienpalette mit einer zusätzlich fest vorgegebenen Farbe (Holz bzw. Abendviolett)
    from pc98lib import pattern_dither, tohex
    srcs = {"hafen": build_ort.load_hafen_src(), **{o: build_ort.load_bg(o, build_ort.CONFIG[o]) for o in ORTE}}
    base_fixed = dict(build_ort.FIXED)
    akzent = {}
    for name, extra in (("ohne", {}), ("holz_aa7755", {"wood": "aa7755"}), ("holz_996655", {"wood": "996655"}),
                        ("violett_775599", {"violet": "775599"})):
        build_ort.FIXED = dict(base_fixed, **extra)
        build_ort._SERIE.clear()
        pal, _ = build_ort.palette_serie()
        res = {}
        for k, src in srcs.items():
            idx = pattern_dither(src, pal, allowed=list(range(14)), levels=4, ox=12, oy=12)
            res[k] = build_ort.palette_loss(src, idx, pal)["dE_mean"]
        akzent[name] = {"verlust_dE": res, "mittel": round(sum(res.values()) / len(res), 2),
                        "palette": [tohex(c) for c in pal[:14]]}
    build_ort.FIXED = base_fixed
    build_ort._SERIE.clear()
    out = {
        "stil": "pc98-adventure",
        "anker": {"roh": REL(ANCHOR), "verarbeitet": "styles/pc98-adventure/assets/bg_preview.png",
                  "detail": det_anchor, "pixelraster": M.pixel_style(ANCHOR)},
        "masse": {
            "layout": "Korrelation der Oklab-Helligkeit (96x64) und der Gradientenbilder (192x128 → 48x32)",
            "kacheln": "3x2 Kacheln, je Korrelation r und mittlerer |ΔL|; kopiert = r ≥ 0,9 und |ΔL| ≤ 0,03",
            "palette": "k-means (12) in Oklab auf 632 px Breite, gematchter Abstand beider Richtungen, ΔE = Oklab × 100",
            "detail": "mittlere Gradientenenergie von L ×100 und Anteil Gradient > 0,04, auf 632 px Breite",
            "pixelraster": "stärkste Periode 2–10 px der Spaltenunterschiede (1264 px Breite), Deutlichkeit = Spitze/Median",
            "verlust": "ΔE zwischen Quelle (416x256) und gerastertem Bild, beide 4x4 in linearem Licht gemittelt",
        },
        "basis_unabhaengige_bilder": basis,
        "experiment_ab": experiment,
        "orte": orte,
        "palette": {
            "hafen_palette": stats["leuchtturm"]["fixed"]["palette"],
            "serien_palette": stats["leuchtturm"]["serie"]["palette"],
            "hafen_verlust_dE": {m: hafen[m]["loss_static"]["dE_mean"] for m in hafen},
            "hafen_groesste_verluste_serienpalette": hafen.get("serie", {}).get("loss_static", {}).get("groups", [])[:3],
            "mittel_4_bilder_dE": {
                "hafenpalette": round((hafen["fixed"]["loss_static"]["dE_mean"]
                                       + sum(stats[o]["fixed"]["loss_static"]["dE_mean"] for o in ORTE)) / 4, 2),
                "serienpalette": round((hafen["serie"]["loss_static"]["dE_mean"]
                                        + sum(stats[o]["serie"]["loss_static"]["dE_mean"] for o in ORTE)) / 4, 2),
                "eigene_je_bild_nur_orte": round(sum(stats[o]["own"]["loss_static"]["dE_mean"] for o in ORTE) / 3, 2)},
            "serienpalette_mit_zusatzakzent": akzent,
        },
        "vergleich_codex_serie": {"hinweis": "gleiche Maße, Bezug jeweils der eigene Hafen-Anker der Serie",
                                  "codex": codex,
                                  "agy_pc98": {o: {"palette_zum_anker": orte[o]["palettenabstand_zum_anker_dE"],
                                                   "detail_rel_anker": orte[o]["detail_rel_anker"]["grad_energy"],
                                                   "layout_zum_anker": orte[o]["layout_aehnlichkeit_zum_anker"],
                                                   "kopierte_kacheln": orte[o]["kopierte_kacheln"]} for o in ORTE}},
        "erzeugungen": {"gesamt": 6, "budget": 10, "workers_max": 2,
                        "liste": ["leuchtturm_a", "leuchtturm_b", "leuchtturm", "stube", "klippe", "klippe_b"],
                        "sperren": ["Beim Auftrag klippe meldete ein agy-Konto sein Kontingent erschöpft; genimg.py "
                                    "wich auf das nächste agy-Konto aus (Erzeugung dauerte deshalb 185,7 s). "
                                    "Sperren zählen laut PIPELINE.md nicht als Erzeugung."]},
    }
    if a.frames:
        out["godot_testaufnahme"] = godot_checks(pathlib.Path(a.frames))
    (SD / "measure.json").write_text(json.dumps(out, ensure_ascii=False, indent=1) + "\n")
    print(json.dumps({o: {k: orte[o][k] for k in ("palettenabstand_zum_anker_dE", "detail_rel_anker",
                                                 "layout_aehnlichkeit_zum_anker", "kopierte_kacheln")} for o in ORTE},
                     ensure_ascii=False, indent=1))
    print("codex", json.dumps(codex, ensure_ascii=False))


if __name__ == "__main__":
    main()
