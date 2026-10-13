#!/usr/bin/env python3
"""Bereitet die Bildpaare für die Godot-Vergleichsansicht vor und baut eine Übersicht aller Paare.

    .venv/bin/python styles/bildmodelle-vergleich/scripts/build_pairs.py

- demo/art/pairs/<id>_codex.png und <id>_agy.png: beide Bilder eines Paars auf dieselbe Leinwand 870×580
  (3:2, „cover“: auf volle Fläche skaliert, Überstand mittig abgeschnitten; agy liefert 1264×848 = 1,4906:1,
  dabei fallen oben und unten je etwa 1 px weg). Transparente Bilder liegen auf einem ruhigen Schachbrett,
  damit Freistellfehler sichtbar bleiben.
- assets/pairs_overview.jpg: alle Paare (Codex links, agy rechts) und die Wiederholungsläufe mit Beschriftung.
"""
import json, pathlib
from PIL import Image, ImageDraw, ImageFont

HERE = pathlib.Path(__file__).resolve().parent
ENTRY = HERE.parent
ROOT = ENTRY.parent.parent
FONT = ENTRY / "demo" / "fonts" / "SourceSans3.ttf"
MONO = ENTRY / "demo" / "fonts" / "IBMPlexMono-Regular.ttf"

DEMO_PAIRS = ["vga_bg", "oel_bg", "vga_badger"]
W, H = 870, 580


def checker(size, cell=16, a=(52, 56, 66), b=(62, 67, 78)):
    im = Image.new("RGB", size, a)
    d = ImageDraw.Draw(im)
    for y in range(0, size[1], cell):
        for x in range(0, size[0], cell):
            if (x // cell + y // cell) % 2:
                d.rectangle([x, y, x + cell - 1, y + cell - 1], fill=b)
    return im


def cover(im, size):
    s = max(size[0] / im.width, size[1] / im.height)
    nw, nh = round(im.width * s), round(im.height * s)
    r = im.resize((nw, nh), Image.LANCZOS)
    x0, y0 = (nw - size[0]) // 2, (nh - size[1]) // 2
    return r.crop((x0, y0, x0 + size[0], y0 + size[1]))


def contain(im, size, bg):
    s = min(size[0] / im.width, size[1] / im.height)
    r = im.resize((round(im.width * s), round(im.height * s)), Image.LANCZOS)
    out = bg.copy()
    out.paste(r, ((size[0] - r.width) // 2, (size[1] - r.height) // 2), r if r.mode == "RGBA" else None)
    return out


def flat(path, size, fit="cover"):
    im = Image.open(ROOT / path)
    if im.mode in ("RGBA", "LA", "P"):
        im = im.convert("RGBA")
        base = checker(size)
        if fit == "cover":
            r = cover(im, size)
            base.paste(r, (0, 0), r)
            return base
        return contain(im, size, base)
    im = im.convert("RGB")
    return cover(im, size) if fit == "cover" else contain(im, size, Image.new("RGB", size, (24, 26, 31)))


def main():
    meas = json.loads((ENTRY / "assets" / "measurements.json").read_text())
    pairs = {p["id"]: p for p in meas["pairs"]}
    out = ENTRY / "demo" / "art" / "pairs"
    out.mkdir(parents=True, exist_ok=True)
    for pid in DEMO_PAIRS:
        for side in ("codex", "agy"):
            flat(pairs[pid][side]["file"], (W, H)).save(out / f"{pid}_{side}.png", optimize=True)
            print("ok", out / f"{pid}_{side}.png")

    # Übersicht
    cw, ch, pad, lab = 640, 427, 14, 56
    f_t = ImageFont.truetype(str(FONT), 26)
    f_s = ImageFont.truetype(str(MONO), 17)
    rows = list(meas["pairs"])
    reps = meas.get("repeats", [])
    n_rows = len(rows) + (1 if reps else 0) * 2
    sheet = Image.new("RGB", (2 * cw + 3 * pad, n_rows * (ch + lab) + pad), (16, 18, 22))
    d = ImageDraw.Draw(sheet)
    y = pad
    for p in rows:
        d.text((pad, y + 6), p["title"], font=f_t, fill=(240, 232, 214))
        for i, side in enumerate(("codex", "agy")):
            m = p[side]
            x = pad + i * (cw + pad)
            name = "Codex · gpt-image" if side == "codex" else "agy · Gemini"
            info = f"{name}   {m['size']}   {m['seconds']:.0f} s"
            d.text((x + cw - d.textlength(info, font=f_s), y + 12), info, font=f_s,
                   fill=(232, 168, 96) if side == "codex" else (120, 184, 228))
            sheet.paste(flat(m["file"], (cw, ch), fit="contain"), (x, y + lab - 8))
        y += ch + lab
    for r in reps:
        d.text((pad, y + 6), f"Wiederholung VGA-Hintergrund, {'Codex' if r['model'] == 'codex' else 'agy'}: "
               f"Lauf 1 | Lauf 2   (ΔE {str(r["delta_e_48x32"]).replace(".", ",")}, Kantenkorrelation {str(r["edge_corr_192x128"]).replace(".", ",")})",
               font=f_t, fill=(240, 232, 214))
        for i, key in enumerate(("a", "b")):
            x = pad + i * (cw + pad)
            sheet.paste(flat(r[key], (cw, ch), fit="contain"), (x, y + lab - 8))
        y += ch + lab
    sheet.save(ENTRY / "assets" / "pairs_overview.jpg", quality=86, optimize=True)
    print("ok", ENTRY / "assets" / "pairs_overview.jpg", sheet.size)


if __name__ == "__main__":
    main()
