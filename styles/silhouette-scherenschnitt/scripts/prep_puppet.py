#!/usr/bin/env python3
"""Schneidet die Scherenschnitt-Puppe aus dem KI-Teileblatt (assets/raw/puppet.png).

Das Blatt ist schwarz auf weiß; Alpha = Papier. Die Teile werden über Zusammenhangskomponenten gefunden,
die Gelenkpunkte über die Stiftlöcher, die das Modell selbst in Arm-, Bein- und Hüftteil geschnitten hat.
Zusätzlich geschnitten (im Schwarz unsichtbar):
  - Kopf vom Rumpf entlang der Oberkante der Schalwicklung; der Kopf behält unten eine Verlängerung, die
    hinter der Wicklung liegt, damit beim Nicken keine Fuge aufgeht.
  - Fuß vom Bein am Knöchel; beide Teile behalten eine Scheibe um den Drehpunkt (dreht sich in sich selbst).
  - Die zwei Schalenden aus dem gefalteten Schalstück, gespiegelt (Fransen nach hinten).
Geändert: das große weiße Schulterloch im Rumpf wird gefüllt (liegt sonst neben dem Arm frei), das linke
Bein wird gespiegelt (Fuß nach vorn).

Ausgabe: assets/puppet/*.png (weiß mit Alpha, Bildmaßstab), *_gap.png (um 1,5 px geweitet, für die
Schnittfuge), *_fill.png (Löcher gefüllt, 1 px eingezogen: Seidenpapier-Futter hinter den Schnitten), assets/puppet/rig.json und Kopien in demo/art/puppet/.

    .venv/bin/python styles/silhouette-scherenschnitt/scripts/prep_puppet.py
"""
import json, math, pathlib, shutil
import numpy as np
from PIL import Image, ImageDraw, ImageFilter

SD = pathlib.Path(__file__).resolve().parents[1]
RAW = SD / "assets" / "raw" / "puppet.png"
OUT = SD / "assets" / "puppet"
DEMO = SD / "demo" / "art" / "puppet"
CHECK = SD / "assets" / "check"
for d in (OUT, DEMO, CHECK):
    d.mkdir(parents=True, exist_ok=True)

K = 2            # Arbeitsauflösung 2x
SCALE = 0.285    # Quelle -> Bild (Figur ~206 px hoch)

# Gelenk- und Schnittpunkte im Quellblatt (gemessen: Stiftlöcher per Lochsuche, Rest an Rasterausschnitten)
HIP = (673.3, 536.3)          # Stiftloch Hüfte im Rumpf
SHOULDER_N = (668.0, 262.0)   # Schulter (oben im gefüllten Schulterloch)
SHOULDER_F = (652.0, 262.0)
NECK = (722.0, 214.0)         # Drehpunkt Kopf, in der Schalwicklung
NECK_CUT = ((598.0, 166.0), (862.0, 206.0))  # Oberkante der Schalwicklung (Gerade)
NECK_EXT = 30.0               # Kopfverlängerung unter der Schnittlinie (hinter der Wicklung)
SCARF_ROOT = (628.0, 205.0)   # Ansatz der Schalenden hinten am Hals
EYE = (787.5, 134.0, 13.0)    # Auge: Mitte, Radius (Lid)
ARM_N_PIN = (979.8, 133.9)
ARM_F_PIN = (1155.9, 134.0)
LEG_PIN = {"leg2": (1148.4, 448.4), "leg1": (984.9, 444.8)}
ANKLE_UP = 46.0               # Knöchel über der Sohle


def load():
    L = Image.open(RAW).convert("L")
    W, H = L.size
    L2 = L.resize((W * K, H * K), Image.BICUBIC)
    a = np.asarray(L2) < 128
    return a, (W, H)


def comp_at(mask, x, y):
    img = Image.fromarray((mask * 255).astype(np.uint8)).copy()
    ImageDraw.floodfill(img, (int(x * K), int(y * K)), 77)
    return np.asarray(img) == 77


def holes_of(mask):
    img = Image.fromarray(((~mask) * 255).astype(np.uint8)).copy()
    ImageDraw.floodfill(img, (0, 0), 128)
    return np.asarray(img) == 255


def disc(shape, cx, cy, r):
    yy, xx = np.mgrid[0:shape[0], 0:shape[1]]
    return (xx - cx * K) ** 2 + (yy - cy * K) ** 2 <= (r * K) ** 2


def save_piece(m, name, pivot, gap=False, pad_src=6, lining=True):
    """m: 2x-Maske (volle Blattgröße). pivot in Quellkoordinaten. Speichert im Bildmaßstab."""
    ys, xs = np.where(m)
    pad = int(pad_src * K)
    x0, x1 = xs.min() - pad, xs.max() + pad
    y0, y1 = ys.min() - pad, ys.max() + pad
    f = SCALE / K
    w, h = int(math.ceil((x1 - x0) * f)), int(math.ceil((y1 - y0) * f))
    crop = Image.fromarray((m * 255).astype(np.uint8)).crop((x0, y0, x0 + int(math.ceil(w / f)) + 1, y0 + int(math.ceil(h / f)) + 1))
    a = crop.resize((w, h), Image.BOX, box=(0, 0, w / f, h / f))
    def write(alpha, nm):
        rgba = np.zeros((h, w, 4), np.uint8)
        rgba[..., :3] = 255
        rgba[..., 3] = np.asarray(alpha)
        Image.fromarray(rgba).save(OUT / f"{nm}.png", optimize=True)
        shutil.copy(OUT / f"{nm}.png", DEMO / f"{nm}.png")
    write(a, name)
    if lining:
        # Futter: Teil mit gefüllten Löchern, 1 px nach innen gezogen (sonst heller Saum am Umriss)
        fm = m | holes_of(m)
        r = int(round(1.0 / SCALE * K))
        fe = Image.fromarray((fm * 255).astype(np.uint8)).filter(ImageFilter.MinFilter(2 * r + 1))
        fa = fe.crop((x0, y0, x0 + int(math.ceil(w / f)) + 1, y0 + int(math.ceil(h / f)) + 1)).resize((w, h), Image.BOX, box=(0, 0, w / f, h / f))
        write(fa, name + "_fill")
    if gap:
        # Schnittfuge: Teil um ~1,5 px geweitet (2x-Maske um 3*K/... in Quellpixeln: 1.5/SCALE)
        r = int(round(1.5 / SCALE * K))
        g = Image.fromarray((m * 255).astype(np.uint8)).filter(ImageFilter.MaxFilter(2 * r + 1))
        ga = g.crop((x0, y0, x0 + int(math.ceil(w / f)) + 1, y0 + int(math.ceil(h / f)) + 1)).resize((w, h), Image.BOX, box=(0, 0, w / f, h / f))
        write(ga, name + "_gap")
    piv = ((pivot[0] * K - x0) * f, (pivot[1] * K - y0) * f)
    return {"file": f"{name}.png", "size": [w, h], "pivot": [round(piv[0], 2), round(piv[1], 2)]}


def main():
    a, (W, H) = load()
    body = comp_at(a, 760, 400)
    arm_n = comp_at(a, 940, 160)
    arm_f = comp_at(a, 1165, 300)
    leg2 = comp_at(a, 1160, 600)
    leg1 = comp_at(a, 970, 600)
    scarf = comp_at(a, 700, 670)

    # Schulterloch füllen
    hb = holes_of(body)
    fill = comp_at(hb, 666, 281)
    body = body | fill

    # Kopf / Rumpf trennen
    yy, xx = np.mgrid[0:H * K, 0:W * K]
    (ax, ay), (bx, by) = NECK_CUT
    line_y = (ay + (xx / K - ax) * (by - ay) / (bx - ax)) * K
    head = body & (yy < line_y + NECK_EXT * K)
    torso = body & (yy >= line_y)

    # linkes Bein spiegeln (Fuß nach rechts)
    ys, xs = np.where(leg1)
    x0, x1 = xs.min(), xs.max()
    leg1m = np.zeros_like(leg1)
    leg1m[:, x0:x1 + 1] = leg1[:, x0:x1 + 1][:, ::-1]
    pin1 = LEG_PIN["leg1"]
    pin1m = ((x0 + x1) / K - pin1[0], pin1[1])

    rig = {"scale": SCALE, "source": "assets/raw/puppet.png", "pieces": {}}

    def leg_split(m, pin, name):
        ys, xs = np.where(m)
        sole = ys.max() / K
        ay_ = sole - ANKLE_UP
        row = m[int(ay_ * K)]
        cols = np.where(row)[0] / K
        ax_ = (cols.min() + cols.max()) / 2
        r = (cols.max() - cols.min()) / 2 - 3
        d = disc(m.shape, ax_, ay_, r)
        upper = m & ((yy < ay_ * K) | d)
        foot = m & ((yy >= ay_ * K) | d)
        rig["pieces"][name] = save_piece(upper, name, pin, gap=(name == "leg_n"))
        rig["pieces"][name]["ankle_rel"] = [round((ax_ - pin[0]) * SCALE, 2), round((ay_ - pin[1]) * SCALE, 2)]
        fn = name.replace("leg", "foot")
        rig["pieces"][fn] = save_piece(foot, fn, (ax_, ay_), gap=(fn == "foot_n"))
        rig["pieces"][fn]["sole_rel"] = round((sole - ay_) * SCALE, 2)
        rig["pieces"][fn]["toe_rel"] = round((xs.max() / K - ax_) * SCALE, 2)
        rig["pieces"][fn]["heel_rel"] = round((xs.min() / K - ax_) * SCALE, 2)
        return ax_, ay_, r, sole

    an = leg_split(leg2, LEG_PIN["leg2"], "leg_n")
    af = leg_split(leg1m, pin1m, "leg_f")

    rig["pieces"]["torso"] = save_piece(torso, "torso", HIP)
    rig["pieces"]["head"] = save_piece(head, "head", NECK)
    rig["pieces"]["arm_n"] = save_piece(arm_n, "arm_n", ARM_N_PIN, gap=True)
    rig["pieces"]["arm_f"] = save_piece(arm_f, "arm_f", ARM_F_PIN)

    # Schalenden: oberer und unterer Streifen des gefalteten Stücks, links (Falz) bei x 590 abgeschnitten
    for nm, cond in (("scarf_a", yy < 712 * K), ("scarf_b", yy >= 712 * K)):
        s = scarf & cond & (xx > 592 * K)
        ys, xs = np.where(s)
        x0, x1 = xs.min(), xs.max()
        sm = np.zeros_like(s)
        sm[:, x0:x1 + 1] = s[:, x0:x1 + 1][:, ::-1]
        # Ansatz = rechtes Ende nach dem Spiegeln (vorher linkes Ende), mittlere Zeile dort
        endcol = sm[:, x1 - 4 * K]
        rows = np.where(endcol)[0]
        root = (x1 / K - 6, (rows.min() + rows.max()) / 2 / K)
        rig["pieces"][nm] = save_piece(sm, nm, root, pad_src=40, lining=False)  # Rand für die Wellen im Shader
        rig["pieces"][nm]["length"] = round((x1 - x0) / K * SCALE, 1)

    # Gelenkpositionen relativ zur Hüfte (Bildpixel)
    rel = lambda p: [round((p[0] - HIP[0]) * SCALE, 2), round((p[1] - HIP[1]) * SCALE, 2)]
    rig["joints"] = {
        "neck": rel(NECK), "shoulder_n": rel(SHOULDER_N), "shoulder_f": rel(SHOULDER_F),
        "scarf_root": rel(SCARF_ROOT), "eye": rel(EYE[:2]), "eye_r": round(EYE[2] * SCALE, 2),
    }
    hip_to_sole = (an[3] - LEG_PIN["leg2"][1]) * SCALE
    rig["hip_to_ankle"] = round((an[1] - LEG_PIN["leg2"][1]) * SCALE, 2)
    rig["hip_to_sole"] = round(hip_to_sole, 2)
    ys, _ = np.where(body)
    rig["height"] = round((HIP[1] - ys.min() / K) * SCALE + hip_to_sole, 1)
    rig["eye_rel_head"] = [round((EYE[0] - NECK[0]) * SCALE, 2), round((EYE[1] - NECK[1]) * SCALE, 2)]
    (OUT / "rig.json").write_text(json.dumps(rig, indent=1))
    shutil.copy(OUT / "rig.json", DEMO / "rig.json")
    print(json.dumps({k: rig[k] for k in ("hip_to_ankle", "hip_to_sole", "height", "joints")}, indent=1))
    for k, v in rig["pieces"].items():
        print(k, v["size"], v["pivot"])


if __name__ == "__main__":
    main()
