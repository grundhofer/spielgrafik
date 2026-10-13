#!/usr/bin/env python3
"""Dachs-Kurier als Schnittfigur aus EINEM gemalten Bild (assets/raw/badger.png, Codex mit echtem Alphakanal).

    .venv/bin/python -I styles/parallax-2-5d/tools/build_badger.py

Vorlage: shared/badger/walk_painted.png Bild 3 (Durchgang: nahes Bein senkrecht unter der Hüfte, fernes Bein hinten
angehoben), von gpt-image in der Maltechnik des Hafengemäldes übermalt. Zerlegt in sechs Teile, die in Godot
(main.gd) per Code bewegt werden:
  Rumpf (Kopf, Arme, Paket, Tasche, Schalwicklung, Fellkante unten gezackt),
  Bein (Oberschenkel bis Knöchel) und Fuß getrennt: Der Standfuß liegt flach und fest am Boden, das Bein dreht sich
  um die Hüfte und reicht bis zum Knöchel (umgekehrtes Pendel). Fernes Bein = dasselbe Bein abgedunkelt.
  hinteres Schalende (schwingt an einer gedämpften Feder).

Alle Teile teilen EINE Farbebene (das ganze Bild einmal vormultipliziert verkleinert): an Schnittkanten haben
überlappende Teile dieselbe Farbe, es entsteht keine helle Naht. Nur das Alpha kommt aus der Teilmaske.

Ausgabe (assets/badger/, Kopie nach demo/badger/): body.png, leg.png, foot.png, scarf.png, rig.json, preview.png
"""
import json, pathlib, shutil
import numpy as np
from PIL import Image, ImageDraw, ImageFilter

S = pathlib.Path(__file__).resolve().parent.parent
SRC = S / "assets/raw/badger.png"
OUT = S / "assets/badger"
DEMO = S / "demo/badger"
HEIGHT_PX = 320                      # Figurenhöhe (Mütze bis Sohle) der Teilbilder; im Bild ~150–175 px (Mipmaps)

# Punkte in badger.png (1254×1254), an Lupenbildern mit 10-px-Raster abgelesen
TOP, SOLE = 146, 1170                # oberster Pixel (Mütze), Sohle des nahen Fußes
HIP = (676, 890)                     # Drehpunkt des Beins (im Rumpf verdeckt), senkrecht über dem Knöchel
ANKLE = (676, 1112)                  # Gelenk Bein/Fuß
HEEL = (610, 1170)                   # hinterster Sohlenpunkt
TOE = (836, 1160)                    # vorderster Sohlenpunkt (Krallen)
CUT_Y = 972                          # Rumpf endet hier (gezackte Fellkante)
LEG_POLY = [(586, 872), (764, 872), (760, 930), (758, 980), (752, 1040), (747, 1090), (746, 1128), (602, 1128),
            (600, 1090), (596, 1045), (590, 1000)]
LEG_FADE = (874, 900, 1104, 1126)    # oben weich (unter dem Rumpf), unten weich in den Fuß
FOOT_POLY = [(596, 1078), (748, 1078), (792, 1104), (828, 1130), (845, 1158), (830, 1178), (606, 1178),
             (598, 1160)]
SCARF_POLY = [(512, 468), (470, 486), (420, 510), (360, 560), (332, 600), (348, 628), (388, 668), (424, 690),
              (452, 680), (490, 640), (506, 590), (514, 540)]
SCARF_UNDER = [(512, 468), (548, 470), (548, 560), (530, 640), (488, 640), (506, 590), (514, 540)]
SCARF_PIVOT = (508, 492)
FAR_SHIFT = -16                      # fernes Bein liegt so viele Quellpixel weiter hinten


def poly_mask(shape, pts, blur=0.0):
    m = Image.new("L", (shape[1], shape[0]), 0)
    ImageDraw.Draw(m).polygon([tuple(p) for p in pts], fill=255)
    if blur:
        m = m.filter(ImageFilter.GaussianBlur(blur))
    return np.asarray(m).astype(np.float32) / 255


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    a = np.asarray(Image.open(SRC).convert("RGBA")).astype(np.float32)
    h, w, _ = a.shape
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    al = a[..., 3] / 255

    # Masken in Quellauflösung
    rng = np.random.default_rng(11)
    xs = np.arange(w, dtype=np.float32)
    tuft = np.repeat(rng.uniform(-1, 1, w // 9 + 2), 9)[:w]
    edge = CUT_Y + 7.0 * np.abs(np.sin(xs * np.pi / 23.0)) + 5.0 * tuft          # gezackte Fellkante
    body_m = np.clip((edge[None, :] + 5 - yy) / 10.0, 0, 1)
    scarf_out = poly_mask(a.shape, SCARF_POLY, 1.2)
    body_m = body_m * (1 - scarf_out)
    scarf_m = np.maximum(scarf_out, poly_mask(a.shape, SCARF_UNDER, 1.2))
    t0, t1, b0, b1 = LEG_FADE
    leg_m = poly_mask(a.shape, LEG_POLY, 1.2) * np.clip((yy - t0) / (t1 - t0), 0, 1) * np.clip((b1 - yy) / (b1 - b0), 0, 1)
    foot_m = poly_mask(a.shape, FOOT_POLY, 1.0)

    # gemeinsame Farbebene in Endgröße
    k = HEIGHT_PX / (SOLE - TOP)
    size = (round(w * k), round(h * k))
    ke = size[0] / w

    def down(ch):
        return np.asarray(Image.fromarray(ch.astype(np.float32), "F").resize(size, Image.LANCZOS))

    A = np.clip(down(al), 0, 1)
    P = np.dstack([down(a[..., c] * al) for c in range(3)])
    P = np.clip(P, 0, 255 * A[..., None])
    C = np.where(A[..., None] > 0.02, P / np.maximum(A[..., None], 1e-4), 0)
    known = A > 0.02
    for _ in range(8):                                   # Farbe nach außen fortsetzen (Mipmaps, Kanten)
        acc = np.zeros_like(C); cnt = np.zeros(A.shape, np.float32)
        for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            kk = np.roll(known, (dy, dx), (0, 1))
            acc += np.roll(C, (dy, dx), (0, 1)) * kk[..., None]; cnt += kk
        grow = (~known) & (cnt > 0)
        C[grow] = acc[grow] / cnt[grow][:, None]
        known |= grow

    def to_dst(p):
        return ((p[0] + 0.5) * ke - 0.5, (p[1] + 0.5) * ke - 0.5)

    def part(mask, pad=3):
        alp = np.clip(down(al * mask), 0, 1)
        alp[alp < 1.5 / 255] = 0
        ys, xs_ = np.nonzero(alp > 0)
        x0, y0, x1, y1 = xs_.min() - pad, ys.min() - pad, xs_.max() + pad + 1, ys.max() + pad + 1
        rgba = np.dstack([C, alp * 255])[y0:y1, x0:x1]
        return Image.fromarray(np.clip(rgba, 0, 255).round().astype(np.uint8), "RGBA"), (x0, y0)

    parts = {}
    for name, m in (("body", body_m), ("leg", leg_m), ("foot", foot_m), ("scarf", scarf_m)):
        im, org = part(m)
        im.save(OUT / f"{name}.png", optimize=True)
        parts[name] = (im, org)

    def rel(p, name):            # Quellpunkt -> Pixel im Teilbild
        d = to_dst(p)
        o = parts[name][1]
        return [round(d[0] - o[0], 2), round(d[1] - o[1], 2)]

    def from_hip(p):             # Quellpunkt -> relativ zur Hüfte (Endgröße)
        return [round((p[0] - HIP[0]) * ke, 2), round((p[1] - HIP[1]) * ke, 2)]

    rig = {
        "source": "assets/raw/badger.png", "scale": round(ke, 5), "height_px": round((SOLE - TOP) * ke, 1),
        "body_pivot": rel(HIP, "body"), "leg_pivot": rel(HIP, "leg"), "foot_pivot": rel(ANKLE, "foot"),
        "scarf_pivot": rel(SCARF_PIVOT, "scarf"), "scarf_from_hip": from_hip(SCARF_PIVOT),
        "ankle": from_hip(ANKLE), "heel": from_hip(HEEL), "toe": from_hip(TOE), "sole_y": round((SOLE - HIP[1]) * ke, 2),
        "head_top": from_hip((700, TOP)), "far_shift": round(FAR_SHIFT * ke, 2),
        "sizes": {n: list(parts[n][0].size) for n in parts},
    }
    (OUT / "rig.json").write_text(json.dumps(rig, indent=1))
    print(json.dumps(rig))

    # Vorschau in Zeichenreihenfolge: ferner Fuß, fernes Bein, Schalende, naher Fuß, nahes Bein, Rumpf
    bw, bh = parts["body"][0].size
    pv = Image.new("RGBA", (bw + 120, bh + 140), (88, 104, 122, 255))
    hip = (60 + rig["body_pivot"][0], 20 + rig["body_pivot"][1])

    def put(name, pivot, at, dark=1.0):
        im = parts[name][0]
        if dark != 1.0:
            f = np.asarray(im).astype(np.float32); f[..., :3] *= dark
            im = Image.fromarray(f.astype(np.uint8), "RGBA")
        pv.alpha_composite(im, (round(at[0] - pivot[0]), round(at[1] - pivot[1])))

    ank = (hip[0] + rig["ankle"][0], hip[1] + rig["ankle"][1])
    fs = rig["far_shift"]
    put("foot", rig["foot_pivot"], (ank[0] + fs, ank[1]), 0.6)
    put("leg", rig["leg_pivot"], (hip[0] + fs, hip[1]), 0.6)
    put("scarf", rig["scarf_pivot"], (hip[0] + rig["scarf_from_hip"][0], hip[1] + rig["scarf_from_hip"][1]))
    put("foot", rig["foot_pivot"], ank)
    put("leg", rig["leg_pivot"], hip)
    put("body", rig["body_pivot"], hip)
    pv.resize((pv.width * 2, pv.height * 2), Image.LANCZOS).save(OUT / "preview.png")
    DEMO.mkdir(parents=True, exist_ok=True)
    for f in ("body.png", "leg.png", "foot.png", "scarf.png", "rig.json"):
        shutil.copy2(OUT / f, DEMO / f)
        if f.endswith(".png"):
            imp = DEMO / (f + ".import")
            if not imp.exists():
                imp.write_text(IMPORT)


IMPORT = """[remap]

importer="texture"
type="CompressedTexture2D"

[params]

compress/mode=0
compress/high_quality=false
compress/lossy_quality=0.7
compress/hdr_compression=1
compress/normal_map=0
compress/channel_pack=0
mipmaps/generate=true
mipmaps/limit=-1
roughness/mode=0
roughness/src_normal=""
process/fix_alpha_border=true
process/premult_alpha=false
process/normal_map_invert_y=false
process/hdr_as_srgb=false
process/hdr_clamp_exposure=false
process/size_limit=0
detect_3d/compress_to=0
"""

if __name__ == "__main__":
    main()
