#!/usr/bin/env python3
"""Vergleichsbögen der Ortsserie bilderbuch-gouache (nach measure.py ausführen).

    .venv/bin/python -B styles/ortsserie/bilderbuch-gouache/scripts/make_sheet.py

  assets/sheet.png     Hafen-Anker des Stils + Leuchtturm, Stube, Klippe (verarbeitet, 1280x720 → 800x450),
                       beschriftet mit Versuchen und Messwerten aus measure.json
  assets/ab_sheet.png  Experiment: Variante A (Hafenbild als Stilreferenz) gegen B (nur Stilblock) je Ort
"""
import json, pathlib

from PIL import Image, ImageDraw, ImageFont

HERE = pathlib.Path(__file__).resolve().parent
SD = HERE.parent
ROOT = HERE.parents[3]
A = SD / "assets"
FONT = ROOT / "styles/ortsserie/demo/bilderbuch-gouache/fonts/Fraunces-var.ttf"
BG, INK, SUB = (40, 38, 52), (248, 236, 214), (200, 190, 176)
TW, TH = 800, 450


def font(size):
    return ImageFont.truetype(str(FONT), size)


def fmt(x, nd=2):
    return f"{x:.{nd}f}".replace(".", ",")


def tile(canvas, img, x, y, title, lines):
    canvas.paste(img.convert("RGB").resize((TW, TH), Image.LANCZOS), (x, y))
    d = ImageDraw.Draw(canvas)
    d.text((x, y + TH + 8), title, font=font(22), fill=INK)
    for i, ln in enumerate(lines):
        d.text((x, y + TH + 38 + i * 21), ln, font=font(16), fill=SUB)


def metrics_lines(m):
    g = m["generation"]
    ls = m.get("layout_sim_model_output", m["layout_sim_to_anchor"])   # Modellausgabe, mittiger Schnitt
    dr = m["detail_rel_anchor"]
    out = [f"Versuche {g['tries']}, erster brauchbar: {'ja' if g['first_try_ok'] else 'nein'} · "
           f"{fmt(g['seconds'], 0)} s · geliefert {g['size_delivered']}",
           f"Palettenabstand {fmt(m['palette_dE_to_anchor'])} ± {fmt(m['palette_dE_sd'])} · Detail ×{fmt(dr['grad_energy'])} (Kanten ×{fmt(dr['edge_density'])})"
           f" · Layout r {fmt(ls['edge_r'])} (Kanten) / {fmt(ls['gray_r'])} (Grau)"]
    if "text_area" in m:
        t = m["text_area"]
        out.append(f"Textfläche: L-Streuung {fmt(t['calm']['L_std'])}, Kontrast ≥ {fmt(t['contrast_text']['p05'], 1)}"
                   f" ({'dunkle Schrift auf heller Wand' if t['scheme'] == 'dunkel' else 'helle Schrift im Himmel'})")
    return out


def main():
    m = json.loads((SD / "measure.json").read_text())
    b = m["baseline"]
    W, H = 2 * TW + 3 * 24, 70 + 2 * (TH + 120) + 30
    c = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(c)
    d.text((24, 18), "Ortsserie · Bilderbuch & Gouache · alle Bilder agy (Gemini), Variante A: Hafenbild als "
                     "Stilreferenz", font=font(26), fill=INK)
    anchor = Image.open(ROOT / "styles/bilderbuch-gouache/assets/bg.png")
    ba = b["anchor_text_area"]
    tile(c, anchor, 24, 70, "Hafen von Lornholm (Anker, Eintrag bilderbuch-gouache)",
         [f"1 Versuch · {fmt(b['anchor_generation']['seconds'], 0)} s · geliefert "
          f"{b['anchor_generation']['size_delivered']} · Detail grad {fmt(b['anchor_detail']['grad_energy'])}",
          f"Vergleich Layout r (Kanten): gleiches Motiv anderer Einträge {fmt(b['same_motif']['edge_r_mean'])} ± "
          f"{fmt(b['same_motif']['edge_r_sd'])}",
          f"Textfläche: L-Streuung {fmt(ba['calm']['L_std'])}, Kontrast ≥ {fmt(ba['contrast_cream']['p05'], 1)}"
          f" (helle Schrift im Himmel)"])
    names = {"leuchtturm": "Lampenraum im Leuchtturm", "stube": "Stube des Hafenmeisters", "klippe": "Klippenpfad"}
    pos = {"leuchtturm": (48 + TW, 70), "stube": (24, 70 + TH + 120), "klippe": (48 + TW, 70 + TH + 120)}
    for ort, (x, y) in pos.items():
        tile(c, Image.open(A / f"bg_{ort}.png"), x, y, names[ort], metrics_lines(m["orte"][ort]))
    c.save(A / "sheet.png", optimize=True)

    pairs = m["experiment"]["pairs"]
    W2 = 24 + len(pairs) * 2 * (TW // 2 + 24)
    H2 = 70 + TH // 2 + 110
    c2 = Image.new("RGB", (W2, H2), BG)
    d2 = ImageDraw.Draw(c2)
    d2.text((24, 18), "Experiment: A = Hafenbild als Stilreferenz + Ankerabsatz · B = nur Stilblock, keine Referenz",
            font=font(22), fill=INK)
    x = 24
    for ort, pr in pairs.items():
        for v in ("A", "B"):
            mm = pr[v]
            img = Image.open(SD / mm["raw"])
            c2.paste(img.convert("RGB").resize((TW // 2, int(TW // 2 * img.height / img.width)), Image.LANCZOS),
                     (x, 70))
            yy = 70 + int(TW // 2 * img.height / img.width) + 6
            d2.text((x, yy), f"{names[ort]} · {v}", font=font(17), fill=INK)
            dr, ls = mm["detail_rel_anchor"], mm["layout_sim_to_anchor"]
            d2.text((x, yy + 22), f"Palettenabstand {fmt(mm['palette_dE_to_anchor'])} ± {fmt(mm['palette_dE_sd'])} · Detail ×{fmt(dr['grad_energy'])}"
                                  f" · Kanten ×{fmt(dr['edge_density'])}", font=font(14), fill=SUB)
            d2.text((x, yy + 40), f"Layout r {fmt(ls['edge_r'])} (Kanten) / {fmt(ls['gray_r'])} (Grau)",
                    font=font(14), fill=SUB)
            x += TW // 2 + 24
    c2.save(A / "ab_sheet.png", optimize=True)
    print("ok", (A / "sheet.png").relative_to(ROOT), (A / "ab_sheet.png").relative_to(ROOT))


if __name__ == "__main__":
    main()
