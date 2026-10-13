#!/usr/bin/env python3
"""Vergleich der Ortsserie über alle drei agy-Stile und mit der Codex-Serie (Eintrag hintergrund-serie).

    .venv/bin/python -I styles/ortsserie/scripts/vergleich.py --work <Scratchpad>/ortsserie/vergleich

1. assets/einheitsmass.json: dieselben Maße für alle vier Serien, jeweils Ort gegen den eigenen Hafen-Anker, an der
   Modellausgabe (Rohbild, mittiger 16:9-Schnitt über die volle Breite, bei Gouache innerhalb des gemalten
   Papierrands, auf 1280×720). Die drei Stil-Agenten haben je eigene Maße benutzt; diese Tabelle macht die Serien
   untereinander vergleichbar. Die Maßfunktionen stammen aus den Teilordnern (nicht neu erfunden):
     palette_de    bilderbuch-gouache/scripts/gmetrics.py: k-means (k = 12) in Oklab, nächste Farbe, nach Fläche
                   gewichtet, symmetrisch, Mittel ± Streuung über 8 Seeds (Oklab × 100)
     detail        gmetrics.detail: Gradientenenergie (mittlerer |∇L| × 100) im Verhältnis zum Anker
     struct_corr   painterly-digital/scripts/metrics.py: Bandpass-Korrelation der Helligkeit (gleiche Formen an
                   gleicher Stelle); struct_top dasselbe für die oberen 45 % (Himmel). Maß für Layout-Kopie.
     struct_top_rowfree  wie struct_top, aber vorher je Zeile das Mittel des Bandpasses abgezogen: waagrechte
                   Linien quer durchs Bild (Horizont, durchgehende Wolkenbänder) zählen nicht mit
     mean_L        mittleres Oklab-L × 100 (Helligkeit; Abendstimmung)
   Vergleichswerte: Rauschboden des Palettenmaßes (Anker gegen sich selbst, andere Seeds), struct_corr
   unabhängiger Bildpaare (jeder Codex-Ort gegen jeden agy-Anker: anderes Modell, anderer Stil, andere
   Horizontregel) und derselbe Stilblock ohne Referenz (jede agy-Fassung ohne Referenz gegen den eigenen Anker:
   kann nichts kopiert haben, teilt aber Stilblock und Serienregeln).
2. assets/vergleich_codex_agy.png: Zeilen = Hafen-Anker und die drei Orte, Spalten = Codex-Serie und die drei
   agy-Stile, jeweils das verarbeitete Spielbild ohne Effekte und Text, beschriftet mit den Werten aus 1.
Nur NumPy und Pillow.
"""
import argparse, importlib.util, json, pathlib, sys

import numpy as np
from PIL import Image, ImageDraw, ImageFont

HERE = pathlib.Path(__file__).resolve().parent
E = HERE.parent                      # styles/ortsserie
ROOT = E.parents[1]                  # Projektordner
STYLES = ROOT / "styles"
sys.path.insert(0, str(E / "bilderbuch-gouache" / "scripts"))
import gmetrics as GM                # noqa: E402  (Maße des Gouache-Teils)
import paperframe as PF              # noqa: E402


def _load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


PM = _load_module("ortsserie_pd_metrics", E / "painterly-digital" / "scripts" / "metrics.py")

ORTE = [("leuchtturm", "Lampenraum im Leuchtturm"), ("stube", "Stube des Hafenmeisters"), ("klippe", "Klippenpfad")]
# Je Serie: Anker (Rohbild), verwendete Rohbilder je Ort, Gegenproben, Spielbilder für den Bogen
SERIES = {
    "codex": {
        "name": "Codex-Serie (hintergrund-serie)", "model": "gpt-image (Codex)", "paper": False,
        "anchor": "styles/hintergrund-serie/assets/raw/hafen.png",
        "used": {o: f"styles/hintergrund-serie/assets/raw/{o}.png" for o, _ in ORTE},
        "used_note": {o: "mit Anker als Referenz" for o, _ in ORTE},
        "alt": {},
        "show_anchor": "styles/hintergrund-serie/assets/bg_hafen.png",
        "show": {o: f"styles/hintergrund-serie/assets/bg_{o}.png" for o, _ in ORTE},
    },
    "bilderbuch-gouache": {
        "name": "Bilderbuch & Gouache", "model": "agy", "paper": True,
        "anchor": "styles/bilderbuch-gouache/assets/raw/bg.png",
        "used": {"leuchtturm": "styles/ortsserie/bilderbuch-gouache/assets/raw/leuchtturm_a.png",
                 "stube": "styles/ortsserie/bilderbuch-gouache/assets/raw/stube.png",
                 "klippe": "styles/ortsserie/bilderbuch-gouache/assets/raw/klippe.png"},
        "used_note": {o: "mit Referenz" for o, _ in ORTE},
        "alt": {"leuchtturm_b": ("leuchtturm", "ohne Referenz", "styles/ortsserie/bilderbuch-gouache/assets/raw/leuchtturm_b.png"),
                "klippe_b": ("klippe", "ohne Referenz", "styles/ortsserie/bilderbuch-gouache/assets/raw/klippe_b.png")},
        "show_anchor": "styles/bilderbuch-gouache/assets/bg.png",
        "show": {o: f"styles/ortsserie/bilderbuch-gouache/assets/bg_{o}.png" for o, _ in ORTE},
    },
    "painterly-digital": {
        "name": "Digital gemalt (lebendes Standbild)", "model": "agy", "paper": False,
        "anchor": "styles/painterly-digital/assets/raw/master.png",
        "used": {"leuchtturm": "styles/ortsserie/painterly-digital/assets/raw/leuchtturm_a.png",
                 "stube": "styles/ortsserie/painterly-digital/assets/raw/stube.png",
                 "klippe": "styles/ortsserie/painterly-digital/assets/raw/klippe_b.png"},
        "used_note": {"leuchtturm": "mit Referenz", "stube": "mit Referenz", "klippe": "ohne Referenz"},
        "alt": {"leuchtturm_b": ("leuchtturm", "ohne Referenz", "styles/ortsserie/painterly-digital/assets/raw/leuchtturm_b.png"),
                "stube_b": ("stube", "ohne Referenz", "styles/ortsserie/painterly-digital/assets/raw/stube_b.png"),
                "klippe_a": ("klippe", "mit Referenz, verworfen", "styles/ortsserie/painterly-digital/assets/raw/klippe.png")},
        "show_anchor": None,     # aus dem Rohbild geschnitten wie in painterly-digital/scripts/sheet.py
        "show": {o: f"styles/ortsserie/painterly-digital/assets/{o}/still.png" for o, _ in ORTE},
    },
    "pc98-adventure": {
        "name": "Japanischer 16-Bit-PC", "model": "agy", "paper": False,
        "anchor": "styles/pc98-adventure/assets/raw/bg.png",
        "used": {o: f"styles/ortsserie/pc98-adventure/assets/raw/{o}.png" for o, _ in ORTE},
        "used_note": {o: "mit Referenz" for o, _ in ORTE},
        "alt": {"leuchtturm_a": ("leuchtturm", "mit Referenz, gemalter Rahmen", "styles/ortsserie/pc98-adventure/assets/raw/leuchtturm_a.png"),
                "leuchtturm_b": ("leuchtturm", "ohne Referenz, gemalter Rahmen", "styles/ortsserie/pc98-adventure/assets/raw/leuchtturm_b.png"),
                "klippe_b": ("klippe", "ohne Referenz", "styles/ortsserie/pc98-adventure/assets/raw/klippe_b.png")},
        "show_anchor": "styles/ortsserie/pc98-adventure/assets/hafen_bg_serie.png",
        "show": {o: f"styles/ortsserie/pc98-adventure/assets/{o}_bg.png" for o, _ in ORTE},
    },
}


def crop_raw(rel, paper):
    """Rohbild → mittiger 16:9-Schnitt über die volle (bemalte) Breite → 1280×720 (uint8-Array)."""
    raw = np.asarray(Image.open(ROOT / rel).convert("RGB"))
    if paper:
        x0, y0, x1, y1, _ = PF.crop_box(raw, 0)
    else:
        h, w = raw.shape[:2]
        ch = round(w * 9 / 16)
        x0, x1 = 0, w
        y0 = (h - ch) // 2
        y1 = y0 + ch
    return np.asarray(Image.fromarray(raw).crop((x0, y0, x1, y1)).resize((1280, 720), Image.LANCZOS))


class Img:
    def __init__(self, key, rel, paper, work):
        self.rel = rel
        self.arr = crop_raw(rel, paper)
        self.path = work / f"{key}.png"
        Image.fromarray(self.arr).save(self.path)
        self.layout = PM.layout_features(self.path)
        self.detail = GM.detail(self.arr)["grad_energy"]
        self.mean_L = GM.mean_lab(self.arr)[0]


def top_rowfree(fa, fb):
    """struct_top ohne waagrechte Anteile: Zeilenmittel des Bandpasses abziehen, dann obere 45 % (48 von 107 Zeilen
    wie in metrics.layout_similarity) korrelieren."""
    a, b = fa["band"], fb["band"]
    return round(PM._pearson((a - a.mean(1, keepdims=True))[:48], (b - b.mean(1, keepdims=True))[:48]), 3)


def compare(img, anchor):
    pal, sd = GM.palette_de(img.arr, anchor.arr)
    lay = PM.layout_similarity(img.layout, anchor.layout)
    return {"palette_de": pal, "palette_sd": sd, "detail_ratio": round(img.detail / anchor.detail, 2),
            "struct_corr": lay["struct_corr"], "struct_top": lay["struct_top"],
            "struct_top_rowfree": top_rowfree(img.layout, anchor.layout),
            "mean_L": img.mean_L, "anchor_mean_L": anchor.mean_L}


def measure(work):
    out = {"method": __doc__.split("2. assets/")[0].split("1. ")[1].strip(), "series": {}, "baseline": {}}
    anchors, places = {}, {}
    for key, s in SERIES.items():
        print(f"  {key}: Anker", flush=True)
        a = Img(f"{key}_anchor", s["anchor"], s["paper"], work)
        anchors[key] = a
        res = {"name": s["name"], "model": s["model"], "anchor": s["anchor"], "places": {}, "alt": {}}
        pal_self, sd_self = GM.palette_de(a.arr, a.arr)
        res["palette_noise_floor"] = {"palette_de": pal_self, "palette_sd": sd_self,
                                      "note": "Anker gegen sich selbst mit anderen Seeds"}
        for o, _ in ORTE:
            print(f"  {key}: {o}", flush=True)
            im = Img(f"{key}_{o}", s["used"][o], s["paper"], work)
            places[(key, o)] = im
            res["places"][o] = dict(file=s["used"][o], variant=s["used_note"][o], **compare(im, a))
        for name, (o, note, rel) in s["alt"].items():
            print(f"  {key}: {name}", flush=True)
            im = Img(f"{key}_{name}", rel, s["paper"], work)
            res["alt"][name] = dict(place=o, file=rel, variant=note, **compare(im, a))
        out["series"][key] = res
    # unabhängige Paare: jeder Codex-Ort gegen jeden agy-Anker (anderes Modell, andere Serie)
    pairs = []
    for o, _ in ORTE:
        for key in ("bilderbuch-gouache", "painterly-digital", "pc98-adventure"):
            lay = PM.layout_similarity(places[("codex", o)].layout, anchors[key].layout)
            pairs.append({"a": f"codex/{o}", "b": f"{key}/anker", "struct_corr": lay["struct_corr"],
                          "struct_top": lay["struct_top"],
                          "struct_top_rowfree": top_rowfree(places[("codex", o)].layout, anchors[key].layout)})
    sc = [p["struct_corr"] for p in pairs]
    out["baseline"]["independent_struct"] = {"pairs": pairs, "min": min(sc), "max": max(sc),
                                             "abs_max": max(abs(x) for x in sc)}
    # derselbe Stilblock ohne Referenz: jede agy-Fassung ohne Referenz gegen den eigenen Anker (keine Kopie möglich)
    same = []
    for key, res in out["series"].items():
        rows = [(o, r) for o, r in res["places"].items()] + [(r["place"], r) for r in res["alt"].values()]
        for o, r in rows:
            if r["variant"].startswith("ohne Referenz"):
                same.append({"a": pathlib.Path(r["file"]).stem, "series": key, "place": o, "variant": r["variant"],
                             **{k: r[k] for k in ("struct_corr", "struct_top", "struct_top_rowfree")}})
    out["baseline"]["same_style_no_ref"] = {
        "note": "agy-Fassungen ohne Referenz gegen den eigenen Anker: gleicher Stilblock und gleiche Serienregeln, "
                "kein Referenzbild, also keine Kopie möglich",
        "pairs": same,
        **{f"{k}_{f.__name__}": f(p[k] for p in same) for k in ("struct_corr", "struct_top") for f in (min, max)}}
    return out


# --- Bogen ----------------------------------------------------------------------------------------------------------
TW, TH = 416, 234
PAD = 14
LABW = 150
HEAD = 92
CAP = 46
BG = (17, 16, 22)
FG = (240, 233, 218)
DIM = (172, 166, 156)
AMBER = (237, 184, 107)
RED = (236, 128, 110)
FONT = E / "demo" / "painterly-digital" / "fonts" / "AlegreyaSans-Medium.ttf"
FONT_SC = E / "demo" / "painterly-digital" / "fonts" / "AlegreyaSC-Medium.ttf"


def de(x, nd=1):
    return f"{x:.{nd}f}".replace(".", ",")


def tile_img(key, rel, anchor=False):
    if key == "painterly-digital" and anchor:
        im = Image.open(ROOT / SERIES[key]["anchor"]).convert("RGB")      # wie painterly-digital/scripts/sheet.py
        ch = round(im.width * 9 / 16)
        y0 = int(max(0, min(im.height - ch, 402 / 848 * im.height - 270 * ch / 720)))
        return im.crop((0, y0, im.width, y0 + ch)).resize((TW, TH), Image.LANCZOS)
    im = Image.open(ROOT / rel).convert("RGB")
    if key == "pc98-adventure":
        # Bildfenster 416×256 in Originalpixeln, mittig auf 416×234 beschnitten (nur für den Bogen)
        y0 = (im.height - TH) // 2
        return im.crop((0, y0, TW, y0 + TH))
    return im.resize((TW, TH), Image.LANCZOS)


def sheet(m, path):
    f_t = ImageFont.truetype(str(FONT), 30)
    f_h = ImageFont.truetype(str(FONT_SC), 21)
    f_l = ImageFont.truetype(str(FONT), 20)
    f_s = ImageFont.truetype(str(FONT), 16)
    keys = list(SERIES)
    W = LABW + len(keys) * (TW + PAD) + PAD
    H = HEAD + (1 + len(ORTE)) * (TH + CAP + PAD) + 72
    c = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(c)
    d.text((PAD, 12), "Ortsserie: Codex-Serie gegen drei agy-Stile, je Ort das Spielbild ohne Effekte und Text",
           font=f_t, fill=FG)
    heads = {"codex": ("Codex-Serie", "gpt-image, Aquarell-Stilblock, vor der LUT"),
             "bilderbuch-gouache": ("Bilderbuch & Gouache", "agy"),
             "painterly-digital": ("Digital gemalt", "agy, lebendes Standbild"),
             "pc98-adventure": ("Japanischer 16-Bit-PC", "agy, Bildfenster mittig beschnitten")}
    for j, k in enumerate(keys):
        x = LABW + j * (TW + PAD)
        d.text((x, 52), heads[k][0], font=f_h, fill=AMBER)
        d.text((x + d.textlength(heads[k][0], font=f_h) + 10, 56), heads[k][1], font=f_s, fill=DIM)
    rows = [("anker", "Hafen", "Anker der Serie"), ("leuchtturm", "Lampenraum", "im Leuchtturm"),
            ("stube", "Stube des", "Hafenmeisters"), ("klippe", "Klippenpfad", "")]
    for i, (o, l1, l2) in enumerate(rows):
        y = HEAD + i * (TH + CAP + PAD)
        d.text((PAD, y + TH // 2 - 24), l1, font=f_l, fill=FG)
        d.text((PAD, y + TH // 2 + 2), l2, font=f_s, fill=DIM)
        for j, k in enumerate(keys):
            x = LABW + j * (TW + PAD)
            s = SERIES[k]
            if o == "anker":
                c.paste(tile_img(k, s["show_anchor"], anchor=True), (x, y))
                nf = m["series"][k]["palette_noise_floor"]["palette_de"]
                d.text((x, y + TH + 4), f"Stilanker · Rauschboden Palette {de(nf)}", font=f_s, fill=DIM)
                continue
            c.paste(tile_img(k, s["show"][o]), (x, y))
            r = m["series"][k]["places"][o]
            d.text((x, y + TH + 4), f"Palette {de(r['palette_de'])} · Detail ×{de(r['detail_ratio'], 2)} · "
                   f"Struktur r {de(r['struct_corr'], 2)} · L {de(r['mean_L'], 0)}/{de(r['anchor_mean_L'], 0)}",
                   font=f_s, fill=FG)
            note = r["variant"]
            col = DIM
            if k == "pc98-adventure" and o == "klippe":
                note += "; Himmel und Leuchtturm aus dem Anker kopiert"
                col = RED
            d.text((x, y + TH + 24), note, font=f_s, fill=col)
    d.text((PAD, H - 60), "Maße an der Modellausgabe gegen den eigenen Anker (assets/einheitsmass.json): Palette = "
           "Oklab-Abstand × 100 (k-means 12, 8 Seeds), Detail = Gradientenenergie ÷ Anker, Struktur r = "
           "Bandpass-Korrelation (Layout-Kopie), L = mittlere Helligkeit Ort/Anker.", font=f_s, fill=DIM)
    b = m["baseline"]["independent_struct"]
    d.text((PAD, H - 40), f"Unabhängige Bildpaare: Struktur r {de(b['min'], 2)} bis {de(b['max'], 2)}. "
           "Die Codex-Bilder zeigt der Bogen vor ihrer Farb-LUT, damit alle vier Spalten ohne Farbabgleich stehen.",
           font=f_s, fill=DIM)
    s0 = m["baseline"]["same_style_no_ref"]
    d.text((PAD, H - 20), f"Gleicher Stilblock ohne Referenz (keine Kopie möglich): Struktur r "
           f"{de(s0['struct_corr_min'], 2)} bis {de(s0['struct_corr_max'], 2)}, in den oberen 45 % "
           f"{de(s0['struct_top_min'], 2)} bis {de(s0['struct_top_max'], 2)}. Kopien mit Referenz lagen höher "
           "(siehe style.json).", font=f_s, fill=DIM)
    c.save(path, optimize=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--work", required=True, help="Ordner für Zwischenbilder (Scratchpad)")
    ap.add_argument("--sheet-only", action="store_true", help="Messwerte aus assets/einheitsmass.json lesen")
    a = ap.parse_args()
    work = pathlib.Path(a.work)
    work.mkdir(parents=True, exist_ok=True)
    target = E / "assets" / "einheitsmass.json"
    if a.sheet_only:
        m = json.loads(target.read_text(encoding="utf-8"))
    else:
        m = measure(work)
        target.parent.mkdir(exist_ok=True)
        target.write_text(json.dumps(m, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    sheet(m, E / "assets" / "vergleich_codex_agy.png")
    print("ok")


if __name__ == "__main__":
    main()
