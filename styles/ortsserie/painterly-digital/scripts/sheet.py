#!/usr/bin/env python3
"""Vergleichsbogen assets/sheet.png: Hafen-Anker des Stils + drei Orte (verarbeitet, 1280x720 verkleinert),
darunter die nicht verwendeten Fassungen des A/B-Experiments (Rohbilder im selben 16:9-Schnitt). Beschriftet mit
Fassung und Messwerten aus measure.json.

    .venv/bin/python -I styles/ortsserie/painterly-digital/scripts/sheet.py
"""
import json, pathlib

from PIL import Image, ImageDraw, ImageFont

HERE = pathlib.Path(__file__).resolve().parent
E = HERE.parent
ROOT = E.parents[2]
FONT = ROOT / "styles/ortsserie/demo/painterly-digital/fonts/AlegreyaSans-Medium.ttf"
TW, TH = 480, 270
PAD = 14
LAB = 88
BG = (18, 20, 26)
FG = (236, 230, 216)
DIM = (170, 165, 155)
AMBER = (237, 184, 107)
NAMES = {"leuchtturm": "Im Leuchtturm", "stube": "Stube", "klippe": "Klippenpfad"}


def crop169(path, horizon_share=None):
    im = Image.open(path).convert("RGB")
    ch = round(im.width * 9 / 16)
    y0 = (im.height - ch) // 2
    if horizon_share is not None:
        y0 = int(max(0, min(im.height - ch, horizon_share * im.height - 270 * ch / 720)))
    return im.crop((0, y0, im.width, y0 + ch)).resize((TW, TH), Image.LANCZOS)


def main():
    m = json.loads((E / "measure.json").read_text())
    f_title = ImageFont.truetype(str(FONT), 30)
    f_lab = ImageFont.truetype(str(FONT), 21)
    f_small = ImageFont.truetype(str(FONT), 17)
    W = PAD + 4 * (TW + PAD)
    H = 56 + 2 * (TH + LAB + PAD) + 30
    sheet = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(sheet)
    d.text((PAD, 12), "painterly-digital, Ortsserie mit agy (Gemini-Bildmodell): Hafen-Anker und drei neue Orte",
           font=f_title, fill=FG)

    def tile(img, col, row, title, line, color=FG, note=""):
        x = PAD + col * (TW + PAD)
        y = 56 + row * (TH + LAB + PAD)
        sheet.paste(img, (x, y))
        d.text((x, y + TH + 6), title, font=f_lab, fill=color)
        d.text((x, y + TH + 34), line, font=f_small, fill=DIM)
        if note:
            d.text((x, y + TH + 58), note, font=f_small, fill=(230, 140, 120))

    anchor = crop169(ROOT / m["anchor"]["file"], 402 / 848)
    tile(anchor, 0, 0, "Hafen-Anker (painterly-digital, agy)", "Stilreferenz für Fassung A", AMBER)
    for i, ort in enumerate(["leuchtturm", "stube", "klippe"]):
        L = m["locations"][ort]
        img = Image.open(E / "assets" / ort / "still.png").convert("RGB").resize((TW, TH), Image.LANCZOS)
        v = "A, mit Referenz" if L["with_reference"] else "B, ohne Referenz"
        line = (f"Palette ΔE {L['palette_vs_anchor']['palette_matched']:.1f} · Detail "
                f"{L['detail_vs_anchor']['grad_energy_ratio']:.2f}× · Struktur r {L['layout_vs_anchor']['struct_corr']:.2f}")
        tile(img, i + 1, 0, f"{NAMES[ort]} ({v})", line)
    exp = m["experiment_ab"]["places"]
    d.text((PAD, 56 + TH + LAB + 2), "", font=f_small, fill=DIM)
    for i, ort in enumerate(["leuchtturm", "stube", "klippe"]):
        unused = "b" if exp[ort]["used"] == "a" else "a"
        r = exp[ort][unused]
        img = crop169(E / r["file"], m["locations"][ort]["horizon_src_share"])
        v = "A, mit Referenz" if unused == "a" else "B, ohne Referenz"
        note = "übernimmt Wolken, Leuchtturmlage und Kaimauer des Ankers" if ort == "klippe" else ""
        line = (f"Palette ΔE {r['palette_vs_anchor']['palette_matched']:.1f} · Detail "
                f"{r['detail_vs_anchor']['grad_energy_ratio']:.2f}× · Struktur r {r['layout_vs_anchor']['struct_corr']:.2f}")
        tile(img, i + 1, 1, f"{NAMES[ort]} ({v}), nicht verwendet", line, DIM, note)
    x0 = PAD
    y0 = 56 + TH + LAB + PAD
    d.text((x0, y0 + 10), "Unten: Gegenfassungen des A/B-Experiments", font=f_lab, fill=DIM)
    d.text((x0, y0 + 40), "(Rohbild, gleicher 16:9-Schnitt).", font=f_small, fill=DIM)
    d.text((x0, y0 + 66), "Palette ΔE: 8 Farben, Oklab ×100, zum Anker.", font=f_small, fill=DIM)
    d.text((x0, y0 + 90), "Detail: Gradientenenergie ÷ Anker.", font=f_small, fill=DIM)
    d.text((x0, y0 + 114), "Struktur r: Bandpass-Korrelation zum Anker", font=f_small, fill=DIM)
    d.text((x0, y0 + 136), "(unabhängige Bilder |r| ≤ 0,03).", font=f_small, fill=DIM)
    d.text((x0, y0 + 166), "Oben: verarbeitete Hintergründe 1280×720,", font=f_small, fill=DIM)
    d.text((x0, y0 + 188), "Horizont auf Zeile 270, ohne Effekte.", font=f_small, fill=DIM)
    d.text((PAD, H - 26), "Messwerte: styles/ortsserie/painterly-digital/measure.json", font=f_small, fill=DIM)
    sheet.save(E / "assets" / "sheet.png")
    print(E.relative_to(ROOT) / "assets" / "sheet.png", sheet.size)


if __name__ == "__main__":
    main()
