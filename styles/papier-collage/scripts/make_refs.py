#!/usr/bin/env python3
"""Lagevorlagen (Block-Mock-ups) für die KI-Bilder von papier-collage.

agy übernimmt die Anordnung der ersten Referenz sehr genau. Deshalb wird die Szene zuerst hier in
Bildschirmkoordinaten (1280x720) festgelegt und als grobe Blockskizze auf die Leinwand der Bildaufträge
(1536x1024, 3:2) übertragen: Bildschirm-y = (Leinwand-y - 80) / 1.2, Bildschirm-x = Leinwand-x / 1.2.
So passen Hintergrund, Kai-Ebene und Requisiten ohne Neukomposition zusammen.

    .venv/bin/python styles/papier-collage/scripts/make_refs.py
"""
import json, pathlib
from PIL import Image, ImageDraw

HERE = pathlib.Path(__file__).resolve().parent.parent
ROOT = HERE.parent.parent
REFS = HERE / "assets" / "refs"
S, OY = 1.2, 80  # Bildschirm -> Leinwand
MAG = (255, 0, 255)

# Szene in Bildschirmkoordinaten (1280x720)
LAYOUT = {
    "horizon": 352,
    "lighthouse": {"x0": 1092, "x1": 1148, "top": 92, "base": 262, "lamp": [1120, 118], "band": [180, 205]},
    "headland": [[900, 420], [930, 352], [985, 318], [1040, 286], [1090, 262], [1170, 255], [1230, 236],
                 [1290, 226], [1290, 440]],
    "islands": [[-10, 352], [40, 338], [120, 332], [190, 340], [260, 336], [330, 344], [400, 352]],
    "quay_top": 515,
    "cottage": {"x0": -10, "x1": 330, "base": 560, "eave": 360, "peak": 250,
                "chimney": [248, 292, 212], "door": [60, 150, 398], "window": [200, 282, 420, 492]},
    "lantern": {"post_x": [898, 912], "top": 330, "base": 585, "lamp": [858, 345, 395]},
    "barrels": [[1010, 1080, 503, 588], [1085, 1155, 503, 588]],
    "crates": [1160, 1270, 480, 590],
    "rope": [935, 1000, 566, 592],
    "feet": 592,
}


def c(x, y):
    return (round(x * S), round(y * S + OY))


def back():
    im = Image.new("RGB", (1536, 1024))
    d = ImageDraw.Draw(im)
    bands = [(0, (38, 36, 82)), (110, (66, 52, 110)), (200, (110, 74, 130)), (275, (176, 104, 128)),
             (325, (226, 140, 92)), (LAYOUT["horizon"], (60, 88, 120))]
    ys = [b[0] for b in bands] + [900]
    for (y0, col), y1 in zip(bands, ys[1:]):
        d.rectangle([0, c(0, y0 - 80)[1] if y0 == 0 else c(0, y0)[1], 1536, c(0, y1)[1]], fill=col)
    for k, y in enumerate(range(LAYOUT["horizon"] + 30, 720, 45)):
        d.rectangle([0, c(0, y)[1], 1536, 1024], fill=(54 - k * 4, 84 - k * 5, 116 - k * 5))
    for cx, cy, w, h in [(260, 120, 230, 34), (640, 70, 200, 26), (820, 190, 260, 30), (450, 250, 170, 22)]:
        d.ellipse([c(cx - w / 2, cy - h / 2), c(cx + w / 2, cy + h / 2)], fill=(132, 96, 150))
    d.polygon([c(*p) for p in LAYOUT["islands"]], fill=(84, 58, 100))
    d.polygon([c(*p) for p in LAYOUT["headland"]], fill=(92, 84, 104))
    lh = LAYOUT["lighthouse"]
    d.polygon([c(lh["x0"], lh["base"]), c(lh["x0"] + 6, lh["top"] + 40), c(lh["x1"] - 6, lh["top"] + 40),
               c(lh["x1"], lh["base"])], fill=(236, 232, 222))
    d.rectangle([c(lh["x0"], lh["band"][0]), c(lh["x1"], lh["band"][1])], fill=(190, 52, 50))
    d.rectangle([c(lh["x0"] + 8, lh["top"] + 16), c(lh["x1"] - 8, lh["top"] + 40)], fill=(40, 40, 50))
    d.ellipse([c(lh["lamp"][0] - 9, lh["lamp"][1] - 9), c(lh["lamp"][0] + 9, lh["lamp"][1] + 9)], fill=(255, 214, 90))
    d.polygon([c(lh["x0"] + 2, lh["top"] + 16), c(1120, lh["top"]), c(lh["x1"] - 2, lh["top"] + 16)], fill=(150, 40, 40))
    im.save(REFS / "layout_back.png")


def quay():
    im = Image.new("RGB", (1536, 1024), MAG)
    d = ImageDraw.Draw(im)
    q = LAYOUT["quay_top"]
    d.rectangle([c(-10, q), c(1300, 760)], fill=(150, 140, 128))
    for y in range(q + 18, 760, 34):
        d.line([c(-10, y), c(1300, y)], fill=(120, 112, 104), width=3)
    co = LAYOUT["cottage"]
    d.rectangle([c(co["x0"], co["eave"]), c(co["x1"] - 20, co["base"])], fill=(128, 124, 120))
    d.polygon([c(co["x0"] - 20, co["eave"] + 6), c((co["x0"] + co["x1"]) / 2 - 10, co["peak"]),
               c(co["x1"] + 6, co["eave"] + 6)], fill=(70, 80, 100))
    ch = co["chimney"]
    d.rectangle([c(ch[0], ch[2]), c(ch[1], co["eave"] - 40)], fill=(118, 110, 104))
    dr = co["door"]
    d.rectangle([c(dr[0], dr[2]), c(dr[1], co["base"])], fill=(110, 76, 48))
    w = co["window"]
    d.rectangle([c(w[0], w[2]), c(w[1], w[3])], fill=(255, 210, 90))
    la = LAYOUT["lantern"]
    d.rectangle([c(la["post_x"][0], la["top"]), c(la["post_x"][1], la["base"])], fill=(110, 78, 50))
    d.rectangle([c(la["lamp"][0] - 4, la["top"] + 4), c(la["post_x"][0], la["top"] + 12)], fill=(60, 56, 56))
    d.rectangle([c(la["lamp"][0] - 18, la["lamp"][1]), c(la["lamp"][0] + 18, la["lamp"][2])], fill=(255, 210, 90))
    for x0, x1, y0, y1 in LAYOUT["barrels"]:
        d.rounded_rectangle([c(x0, y0), c(x1, y1)], radius=14, fill=(132, 90, 54))
    x0, x1, y0, y1 = LAYOUT["crates"]
    d.rectangle([c(x0, (y0 + y1) / 2), c(x1, y1)], fill=(170, 126, 76))
    d.rectangle([c(x0 + 12, y0), c(x1 - 16, (y0 + y1) / 2)], fill=(160, 118, 70))
    x0, x1, y0, y1 = LAYOUT["rope"]
    d.ellipse([c(x0, y0), c(x1, y1)], fill=(176, 150, 104))
    im.save(REFS / "layout_quay.png")


def props():
    im = Image.new("RGB", (1536, 1024), MAG)
    d = ImageDraw.Draw(im)
    # Steg: Plankenband auf Pfählen
    d.rectangle([70, 150, 820, 178], fill=(150, 108, 66))
    for x in range(90, 820, 120):
        d.rectangle([x, 178, x + 18, 290], fill=(110, 78, 50))
    # zwei Boote: Rumpf, Mast
    for x0, w, mh in [(80, 250, 190), (420, 300, 210)]:
        y = 560
        d.polygon([(x0, y - 60), (x0 + w, y - 70), (x0 + w - 40, y), (x0 + 30, y)], fill=(140, 96, 60))
        d.rectangle([x0 + w * 0.45, y - 60 - mh, x0 + w * 0.45 + 8, y - 60], fill=(110, 78, 50))
    # Wolken
    d.ellipse([900, 90, 1230, 170], fill=(150, 110, 160))
    d.ellipse([1270, 110, 1490, 170], fill=(150, 110, 160))
    # Möwe: Körper und Flügel getrennt
    d.ellipse([900, 330, 1010, 370], fill=(240, 240, 236))
    d.polygon([(1100, 360), (1180, 320), (1260, 330), (1180, 350)], fill=(230, 230, 226))
    # Rauchwölkchen
    for x0, r in [(900, 40), (1020, 52), (1170, 66)]:
        d.ellipse([x0, 520 - r, x0 + 2 * r, 520 + r], fill=(176, 170, 178))
    im.save(REFS / "layout_props.png")


def badger():
    sheet = Image.open(ROOT / "shared" / "badger" / "master_sheet.png").convert("RGB")
    fig = sheet.crop((540, 80, 980, 900))
    k = 1180 / (888 - 93)
    fig = fig.resize((round(fig.width * k), round(fig.height * k)), Image.LANCZOS)
    im = Image.new("RGB", (1024, 1536), MAG)
    # Füße auf Zeile 1400, Figur mittig
    top = 1400 - round((888 - 80) * k)
    im.paste(fig, ((1024 - fig.width) // 2, top))
    im.save(REFS / "layout_badger.png")


if __name__ == "__main__":
    REFS.mkdir(parents=True, exist_ok=True)
    back(); quay(); props(); badger()
    (HERE / "assets" / "layout.json").write_text(json.dumps(LAYOUT, indent=1))
    print("ok", sorted(p.name for p in REFS.iterdir()))
