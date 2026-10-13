#!/usr/bin/env python3
"""Bereitet die drei KI-Bilder für die Demo auf.

    .venv/bin/python -I styles/prozedurale-animation/scripts/prep_assets.py

- bg.png (agy, 1264x848): Zeilen 24..735 (16:9) auf 1280x720, Wassermaske über die Farbe.
- badger.png (Codex, Alpha): Komponenten -> Gesamtfigur (nur Vorlage), Körper, Bein, Schalende, Tasche;
  Schalwicklung als Deckebene aus dem Körper geschnitten (rot + angrenzende Kontur). Maßstab 0,30.
- boats.png (Codex, Alpha): zwei Boote, Maßstab 0,40.
Schreibt assets/*.png, assets/rig.json, assets/scene.json und kopiert alles nach demo/art/.
"""
import json, pathlib, shutil, sys

import numpy as np
from PIL import Image

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from pa_cc import components  # noqa: E402

SD = HERE.parent
RAW, AS, ART = SD / "assets" / "raw", SD / "assets", SD / "demo" / "art"
ART.mkdir(parents=True, exist_ok=True)

# ---------------------------------------------------------------- Hintergrund
CROP_TOP, CROP_H = 24, 711
bg = Image.open(RAW / "bg.png").convert("RGB")
K = 1280 / bg.width


def to_screen(x, y):
    return [round(x * K, 1), round((y - CROP_TOP) * K, 1)]


bgc = bg.crop((0, CROP_TOP, bg.width, CROP_TOP + CROP_H)).resize((1280, 720), Image.LANCZOS)


def flood(allowed, seeds, limit=4000):
    """Flutfüllung (4er-Nachbarschaft) innerhalb von allowed, ab den Saatpunkten (y, x)."""
    reach = np.zeros_like(allowed)
    for sy, sx in seeds:
        reach[sy, sx] = allowed[sy, sx]
    for _ in range(limit):
        n = reach.copy()
        n[1:] |= reach[:-1]; n[:-1] |= reach[1:]; n[:, 1:] |= reach[:, :-1]; n[:, :-1] |= reach[:, 1:]
        n &= allowed
        if (n == reach).all():
            break
        reach = n
    return reach


# Retusche (Bildschirmmaß): Der helle Wolkenstreifen auf Lampenhöhe las sich neben dem animierten Strahl wie
# ein zweiter, stehender Strahl, der gemalte Lichthof verdoppelte das animierte Aufblitzen.
# 1. Streifen: je Spalte die rosa Zeilen (Blau kaum über Rot) aus den Himmelszeilen darüber/darunter füllen.
# 2. Lichthof: Himmelspixel um die Lampe (Flutfüllung, die dunkle Kontur des Turms hält sie auf) zu einem
#    waagerecht aus dem Ring bei r = 76 px gemittelten Himmel ziehen; der Turm selbst bleibt unberührt.
LAMP = (1111, 151)
px = np.asarray(bgc).astype(np.float32)


def box_blur(arr, rx, ry):
    """Kastenfilter über die letzten zwei Achsen (Zeilen ry, Spalten rx), Ränder gestreckt."""
    out = arr.astype(np.float32)
    if ry:
        p = np.pad(out, ((ry, ry), (0, 0)) + ((0, 0),) * (out.ndim - 2), mode="edge")
        c = np.cumsum(p, axis=0)
        c = np.concatenate([np.zeros_like(c[:1]), c], axis=0)
        out = (c[2 * ry + 1:] - c[:-2 * ry - 1]) / (2 * ry + 1)
    if rx:
        p = np.pad(out, ((0, 0), (rx, rx)) + ((0, 0),) * (out.ndim - 2), mode="edge")
        c = np.cumsum(p, axis=1)
        c = np.concatenate([np.zeros_like(c[:, :1]), c], axis=1)
        out = (c[:, 2 * rx + 1:] - c[:, :-2 * rx - 1]) / (2 * rx + 1)
    return out


Y0, Y1, X0 = 126, 180, 850
reg = px[Y0:Y1, X0:]
st = np.clip((26.0 - (reg[..., 2] - reg[..., 0])) / 10.0, 0.0, 1.0)      # rosa: Blau kaum über Rot
st[:, 1084 - X0:1141 - X0] = 0.0                                           # Turmspalten: Lichthof-Schritt
rows = np.arange(Y0, Y1)[:, None]
has = st > 0.5
top = np.where(has.any(0), np.argmax(has, 0) + Y0, 150).astype(np.float32)
bot = np.where(has.any(0), Y1 - 1 - np.argmax(has[::-1], 0), 150).astype(np.float32)
top = box_blur(top[None], 12, 0)[0] - 4.0
bot = box_blur(bot[None], 12, 0)[0] + 4.0
ti, bi = np.clip(top.round().astype(int), Y0, Y1 - 1), np.clip(bot.round().astype(int), Y0, Y1 - 1)
cols = np.arange(reg.shape[1])
smooth = box_blur(px, 8, 1)
c_top = smooth[ti, cols + X0]
c_bot = smooth[bi, cols + X0]
u = np.clip((rows - top[None]) / np.maximum(bot - top, 1.0)[None], 0.0, 1.0)[..., None]
fill = c_top[None] * (1 - u) + c_bot[None] * u
wgt = np.clip(box_blur(st, 4, 2) * 1.6, 0.0, 1.0)[..., None]
px[Y0:Y1, X0:] = reg * (1 - wgt) + fill * wgt
lum = px @ np.array([0.299, 0.587, 0.114], np.float32)
box = (slice(LAMP[1] - 90, LAMP[1] + 90), slice(LAMP[0] - 90, LAMP[0] + 90))
sky = flood(lum[box] > 95, [(90, 10), (90, 170), (10, 90)])
gy, gx = np.mgrid[box[0], box[1]]
rr = np.hypot(gx - LAMP[0], (gy - LAMP[1]) * 1.15)
w_h = (1.0 - np.clip((rr - 40.0) / 36.0, 0.0, 1.0)) * 0.85 * sky
sub = px[box]
left = px[box[0], LAMP[0] - 76][:, None, :]
right = px[box[0], LAMP[0] + 76][:, None, :]
u = np.clip((gx - (LAMP[0] - 76)) / 152.0, 0.0, 1.0)[..., None]
target = left * (1 - u) + right * u
px[box] = sub * (1 - w_h[..., None]) + target * w_h[..., None]
bgc = Image.fromarray(np.clip(px, 0, 255).round().astype(np.uint8))
bgc.save(AS / "bg.png")

# Wassermaske: Farbe (grün > rot, blau > rot) plus Flutfüllung ab offenen Wasserpunkten, an der dunklen Kontur
# gestoppt. Kaiplatte, Pfosten, Fässer und Kisten fallen so entlang ihrer gemalten Umrisse heraus; die
# Rechteck-Ausschlüsse der ersten Fassung ließen Kammstriche an senkrechten Kanten enden.
a = np.asarray(bg).astype(int)
r, g, b = a[..., 0], a[..., 1], a[..., 2]
H, W = r.shape
yy = np.arange(H)[:, None] + np.zeros((1, W), int)
water = (g - r > 8) & (b > r + 15) & (yy >= 389) & (yy < 600)
dark = (r * 299 + g * 587 + b * 114) // 1000 < 75          # gemalte Kontur
# kleine Lücken je Zeile schließen (helle Spiegelstreifen), nicht über braune oder dunkle Pixel
for y in range(389, 600):
    row = water[y]
    idx = np.nonzero(row)[0]
    if len(idx) < 2:
        continue
    gaps = np.nonzero(np.diff(idx) > 1)[0]
    for gi in gaps:
        x0, x1 = idx[gi], idx[gi + 1]
        if x1 - x0 <= 40:
            seg = a[y, x0:x1]
            if (seg[:, 0] < seg[:, 2] + 30).all() and not dark[y, x0:x1].any():
                row[x0:x1] = True
water = flood(water & ~dark, [(450, 640), (450, 300), (500, 1000)])
mask = np.zeros((H, W, 3), np.uint8)
mask[..., 0] = water * 255
mimg = Image.fromarray(mask).crop((0, CROP_TOP, W, CROP_TOP + CROP_H)).resize((1280, 720), Image.BILINEAR)
m = (np.asarray(mimg)[..., 0] > 127).astype(np.uint8) * 255
out = np.zeros((720, 1280, 3), np.uint8)
out[..., 0] = m
Image.fromarray(out).save(AS / "bg_mask.png")

scene = {
    "_comment": "Bildschirmkoordinaten (1280x720), gemessen am Rohbild (bg.png 1264x848) und umgerechnet",
    "crop_top": CROP_TOP, "scale": round(K, 5),
    "horizon_y": to_screen(0, 388.5)[1],
    "quay_edge_y": to_screen(0, 579)[1],
    "lantern": to_screen(476, 352), "lantern_post_base": to_screen(414, 532),
    "window": to_screen(178, 462), "window_size": [round(45 * K), round(91 * K)],
    "lighthouse_lamp": to_screen(1097, 177),
    "chimney": to_screen(96, 92),
    "chimney_pot": to_screen(110.6, 86.2),          # Oberkante des rechten, höheren Schornsteintopfs (Rauch)
    "jetty_posts": {"left_near": to_screen(678, 542), "left_mid": to_screen(724, 505),
                    "left_far": to_screen(756, 481), "right_far": to_screen(851, 481),
                    "right_mid": to_screen(869, 507), "right_near": to_screen(894, 542)},
    "water_pixels": int((m > 0).sum()),
}

# ---------------------------------------------------------------- Teile


def cut(img, comp, scale, alpha_fix=True):
    msk, (x0, y0, x1, y1) = comp
    p = np.asarray(img)[y0:y1, x0:x1].astype(np.float32)
    al = np.where(msk[y0:y1, x0:x1], p[..., 3], 0)
    if alpha_fix:
        al = np.where(al >= 250, 255, al)
    al = al / 255.0
    pre = np.dstack([p[..., :3] * al[..., None], al])           # vormultipliziert
    w, h = round((x1 - x0) * scale), round((y1 - y0) * scale)
    chans = [np.asarray(Image.fromarray(pre[..., c].astype(np.float32), "F").resize((w, h), Image.LANCZOS))
             for c in range(4)]
    A = np.clip(chans[3], 0, 1)
    rgb = np.stack(chans[:3], -1) / np.maximum(A[..., None], 1e-4)
    o = np.dstack([np.clip(rgb, 0, 255), A * 255]).round().astype(np.uint8)
    o[A < 0.004] = 0
    return Image.fromarray(o, "RGBA")


S = 0.30
sheet = Image.open(RAW / "badger.png").convert("RGBA")
cs = components(np.asarray(sheet)[..., 3])
assert len(cs) == 5, [c[1] for c in cs]
comp = dict(zip(["assembled", "body", "leg", "scarf", "satchel"], cs))
for name in ["assembled", "body", "leg", "scarf", "satchel"]:
    cut(sheet, comp[name], S).save(AS / f"badger_{name}.png")

# Schalwicklung als Deckebene: roter Strick + dunkle Kontur direkt daneben (aus dem Körper selbst)
body = np.asarray(Image.open(AS / "badger_body.png")).astype(int)
br, bgn, bb, ba = body[..., 0], body[..., 1], body[..., 2], body[..., 3]
red = (br > 95) & (br > bgn * 1.7) & (br > bb * 1.7) & (ba > 0)
red[: int(0.26 * body.shape[0])] = False  # Auge (braune Iris) ausnehmen
red[int(0.48 * body.shape[0]):] = False
grow = red.copy()
dark = (br + bgn + bb < 200) & (ba > 0)
for _ in range(3):
    gg = grow.copy()
    gg[1:] |= grow[:-1]; gg[:-1] |= grow[1:]; gg[:, 1:] |= grow[:, :-1]; gg[:, :-1] |= grow[:, 1:]
    grow = grow | (gg & (dark | red))
# einen weichen Rand von 1 px, damit die Kante nicht hart über Riemen und Schal steht
soft = grow.copy()
soft[1:] |= grow[:-1]; soft[:-1] |= grow[1:]; soft[:, 1:] |= grow[:, :-1]; soft[:, :-1] |= grow[:, 1:]
wa = np.where(grow, ba, np.where(soft, ba * 0.5, 0)).astype(np.uint8)
wrap = body.copy().astype(np.uint8)
wrap[..., 3] = wa
Image.fromarray(wrap, "RGBA").save(AS / "badger_wrap.png")

# Rig in Blatt-Pixeln der zusammengesetzten Vorlage; Ursprung = Hüfte des nahen Beins auf dem Boden
bx0, by0 = comp["body"][1][:2]
lx0, ly0 = comp["leg"][1][:2]
ax0, ay0 = comp["assembled"][1][:2]
BODY_TO_ASM = (-585, -15)       # Kopfabgleich (scripts/pa_align.py)
LEG_TO_ASM = (-932, 14)         # Pfotenabgleich mit dem nahen Bein der Vorlage
body_org = (bx0 + BODY_TO_ASM[0], by0 + BODY_TO_ASM[1])
leg_org = (lx0 + LEG_TO_ASM[0], ly0 + LEG_TO_ASM[1])
LEG = {"hip": (95, 70), "knee": (90, 165), "ankle": (88, 255), "sole": 318, "toe": (226, 300), "heel": (42, 312)}
O = (leg_org[0] + LEG["hip"][0], leg_org[1] + LEG["sole"])   # Ursprung im Blatt


def rig(p_sheet):
    return [round((p_sheet[0] - O[0]) * S, 2), round((p_sheet[1] - O[1]) * S, 2)]


def body_pt(x, y):
    return rig((body_org[0] + x, body_org[1] + y))


def leg_pt(x, y):
    return [round(x * S, 2), round(y * S, 2)]


sat = comp["satchel"][1]
rigd = {
    "_comment": "Einheit: Texturpixel (Blatt x 0,30). Ursprung: Bodenpunkt unter der Hüfte des nahen Beins.",
    "scale": S, "display_scale": 0.6667,
    "body_tex_origin": rig(body_org),
    "body_pivot": rig((leg_org[0] + LEG["hip"][0], leg_org[1] + LEG["hip"][1])),
    "leg_tex_origin": rig(leg_org),
    "leg_local": {k: (leg_pt(*v) if isinstance(v, tuple) else round(v * S, 2)) for k, v in LEG.items()},
    "far_leg_offset": [round(-70 * S, 2), round(-6 * S, 2)],
    "scarf_anchor": body_pt(110, 238),
    "strap_anchor": body_pt(95, 285),
    "back_capsule": {"a": body_pt(232, 380), "b": body_pt(232, 600), "r": round(175 * S, 2)},
    "eye": body_pt(362, 150), "eye_r": round(15 * S, 2),
    "satchel_size": [round((sat[2] - sat[0]) * S, 2), round((sat[3] - sat[1]) * S, 2)],
    "satchel_attach": [round(88 * S, 2), round(10 * S, 2)],
    "satchel_rings": [[round(16 * S, 2), round(16 * S, 2)], [round(160 * S, 2), round(16 * S, 2)]],
    "scarf_size": list(Image.open(AS / "badger_scarf.png").size),
    "sizes": {n: list(Image.open(AS / f"badger_{n}.png").size) for n in ["body", "leg", "scarf", "satchel", "assembled"]},
    "assembled_origin": rig((ax0, ay0)),
}

# Farbe des Lids: Median der dunklen Fellpixel in einem Ring um das Auge (Körpertextur)
bt = np.asarray(Image.open(AS / "badger_body.png")).astype(float)
ex, ey = np.array(rigd["eye"]) - np.array(rigd["body_tex_origin"])
gy, gx = np.mgrid[0:bt.shape[0], 0:bt.shape[1]]
rr = np.hypot(gx - ex, gy - ey)
ring = (rr > 5.5) & (rr < 9) & (bt[..., 3] > 250) & (bt[..., :3].mean(-1) < 110)
rigd["lid_color"] = [round(float(c) / 255, 3) for c in np.median(bt[ring][:, :3], axis=0)]

boats_img = Image.open(RAW / "boats.png").convert("RGBA")
bcs = components(np.asarray(boats_img)[..., 3])
assert len(bcs) == 2, [c[1] for c in bcs]
BS = 0.40
boats = {}
for name, c in zip(["boat_a", "boat_b"], bcs):
    cut(boats_img, c, BS).save(AS / f"{name}.png")
    x0, y0, x1, y1 = c[1]
    boats[name] = {"sheet_bbox": [x0, y0, x1, y1], "tex_size": list(Image.open(AS / f"{name}.png").size)}
# Wasserlinie und Ankerpunkte in Blatt-Pixeln (abgelesen), umgerechnet in Texturpixel relativ zur Textur
boats["boat_a"].update({"waterline_sheet_y": 700, "stern_cleat_sheet": [840, 560], "bow_sheet": [75, 485]})
boats["boat_b"].update({"waterline_sheet_y": 712, "stern_cleat_sheet": [948, 608], "bow_sheet": [1485, 565]})
for name, d in boats.items():
    x0, y0 = d["sheet_bbox"][:2]
    d["waterline_tex_y"] = round((d["waterline_sheet_y"] - y0) * BS, 2)
    d["stern_cleat_tex"] = [round((d["stern_cleat_sheet"][0] - x0) * BS, 2), round((d["stern_cleat_sheet"][1] - y0) * BS, 2)]
    d["bow_tex"] = [round((d["bow_sheet"][0] - x0) * BS, 2), round((d["bow_sheet"][1] - y0) * BS, 2)]
scene["boats"] = boats
scene["boat_tex_scale"] = BS

(AS / "rig.json").write_text(json.dumps(rigd, indent=1, ensure_ascii=False) + "\n")
(AS / "scene.json").write_text(json.dumps(scene, indent=1, ensure_ascii=False) + "\n")
(AS / "ui_text.json").write_text(json.dumps(json.loads((pathlib.Path(__file__).resolve().parents[3] / "data" / "motif.json").read_text())["ui_text"], indent=1, ensure_ascii=False) + "\n")
for f in ["ui_text.json", "bg.png", "bg_mask.png", "badger_body.png", "badger_leg.png", "badger_scarf.png", "badger_satchel.png",
          "badger_wrap.png", "boat_a.png", "boat_b.png", "rig.json", "scene.json"]:
    shutil.copy(AS / f, ART / f)
print(json.dumps({"water_px": scene["water_pixels"], "sizes": rigd["sizes"], "boats": {k: v["tex_size"] for k, v in boats.items()}}))
