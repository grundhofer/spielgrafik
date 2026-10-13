#!/usr/bin/env python3
"""Ortsserie, Stil painterly-digital: Gemälde + KI-Farbcode-Maske -> Daten für den lebenden Hintergrund (Kinemagramm).

    .venv/bin/python -I styles/ortsserie/painterly-digital/scripts/process.py [ort ...] [--work DIR]

Kette wie styles/kinemagramm/tools/process.py, aber für beliebige Orte. Wiederverwendet (nur importiert, nicht
kopiert): styles/kinemagramm/tools/aimask.py (Codes einordnen, Maske an das Gemälde ausrichten, Bereiche zerlegen)
und imgops.py (Guided Filter, Pull-Push, gespiegelte Füllung, kachelbares Rauschen). Die Kinemagramm-Skripte
process.py/auto_scene.py/prep.py selbst sind auf den Hafen verdrahtet (Boote, Schornstein, Laterne, Pfade).

Codes (dieselben Farben wie kinemagramm, je Ort mit eigener Bedeutung, siehe prompts.py MASK_CODES):
  blau Himmel, cyan Wasser, orange "fire" (Linse im Leuchtturm, Glut im Kamin), gelb "small" (Kerze, Fenster
  im Hafen), rot "lamp" (ferne Leuchtturmlampe), grün "grass" (Pflanzen auf der Klippe)
Schritte je Ort:
  1. Maske einordnen (aimask.classify), auf Gemäldegröße bringen, ausrichten (aimask.align), verziehen
  2. 16:9-Ausschnitt: Horizont aus der Himmel/Wasser-Grenze, Ausschnitt so, dass er auf HORIZON_ROW liegt
     (im Rahmen des 3:2-Überstands), dann 1280x720 (Lanczos)
  3. Masken: mask_a R Wasser, G Himmel, B Sterne; mask_b R fire, G small, B lamp (je Leuchtfläche + Lichtschein);
     mask_c R Gras, G Lichtempfänger (warm beleuchtete Flächen außerhalb von Himmel/Wasser), B Strahl sichtbar
  4. Saubere Platte: Himmel und Wasser unter Rahmen, Stäben und Objekten fortgesetzt (Pull-Push + Spiegelung)
  5. scene.json: Horizont, Lichter, Flammen, Linse, Strahl, Nebelbänder, Lichtteilchen, Textleiste
  Korrekturen von Hand nur in scripts/scene.override.json (je Ort ein Block, wird über die Automatik gelegt).
Ausgaben: assets/<ort>/ und Kopie nach styles/ortsserie/demo/painterly-digital/art/<ort>/;
Kontrollbilder (overlay.png, masks.png) im Arbeitsordner.
"""
import argparse, json, pathlib, shutil, sys, tempfile

import numpy as np
from PIL import Image, ImageDraw

HERE = pathlib.Path(__file__).resolve().parent
E = HERE.parent
ROOT = E.parents[2]
sys.path.insert(0, str(ROOT / "styles" / "kinemagramm" / "tools"))
import aimask as A  # noqa: E402
import imgops as K  # noqa: E402

W, H = 1280, 720
RAW = E / "assets" / "raw"
DEMO_ART = ROOT / "styles" / "ortsserie" / "demo" / "painterly-digital" / "art"
# Gemälde und Maske je Ort: leuchtturm und stube mit Stilreferenz (Variante A), klippe ohne (Variante B), weil
# klippe mit Referenz Himmel, Leuchtturmlage und Kaimauer des Ankers übernahm (siehe NOTES.md)
SOURCES = {"leuchtturm": ("leuchtturm_a", "leuchtturm_mask"), "stube": ("stube", "stube_mask"),
           "klippe": ("klippe_b", "klippe_mask")}
ORDER = ["leuchtturm", "stube", "klippe"]
CODE = {"fire": "lantern", "small": "window", "lamp": "lamp", "grass": "chimney"}  # Bedeutung -> aimask-Name
HORIZON_ROW = 270          # gemeinsame Bildschirmzeile des Horizonts (Himmel/Wasser-Grenze)
UI = {"x": 20, "y": 536, "w": 1240, "h": 164}   # Textleiste (textoberflaeche, Form Vollbild, x2)
DEMO_FILES = ["still.png", "plate.png", "mask_a.png", "mask_b.png", "mask_c.png", "scene.json"]

# Effektplanung je Ort (Entwurf der Animation, keine Korrektur der Automatik). Lagen hängen an gemessenen Größen:
# "H" = Horizontzeile, "fire"/"small"/"lamp" = Lage der ersten Lichtfläche dieses Kanals (aus der KI-Maske).
FX = {
    "leuchtturm": {
        "sky_amp": 6.0, "sky_period": 60.0, "water_amp": 1.2, "sparkle_k": 0.3,
        "receiver_k": 0.5,
        "flicker": {"fire": [0.96, 1.05, 3.0], "small": [1.0, 1.0, 1.0], "lamp": [1.0, 1.0, 1.0]},
        "lens": {"period": 8.0, "k": 0.42, "sweep_k": 0.16, "sweep_w": 150.0},
        "fog": [{"dy": 8, "hh": 26, "k": 0.5, "speed": 5.0, "mode": 1, "scale": 260, "lift": 0.25},
                {"y": 470, "hh": 70, "k": 0.16, "speed": 7.0, "mode": 3, "scale": 380, "lift": 0.0}],
        "motes": {"around": "fire", "dx": [-330, 360], "y": [40, 530], "n": 40, "k": 0.55},
        "vignette": 0.26,
    },
    "stube": {
        "sky_amp": 5.0, "sky_period": 60.0, "water_amp": 1.0, "sparkle_k": 0.3,
        "receiver_k": 1.0,
        "flicker": {"fire": [0.82, 1.16, 14.0], "small": [0.86, 1.12, 10.0], "lamp": [1.0, 1.0, 1.0]},
        "beam": {"len": 70.0, "k": 0.55, "period": 10.0},
        "room_glow": [{"at": "fire", "r": 320.0, "k": 0.07}, {"at": "small", "r": 130.0, "k": 0.05}],
        "fog": [{"dy": 6, "hh": 18, "k": 0.45, "speed": 4.0, "mode": 1, "scale": 200, "lift": 0.2},
                {"y": 480, "hh": 60, "k": 0.2, "speed": 6.0, "mode": 3, "scale": 380, "lift": 0.0}],
        "motes": {"around": "fire", "dx": [-80, 260], "y": [150, 500], "n": 22, "k": 0.6},
        "vignette": 0.28,
    },
    "klippe": {
        "sky_amp": 18.0, "sky_period": 80.0, "water_amp": 2.2, "sparkle_k": 0.45,
        "receiver_k": 0.0,
        "flicker": {"fire": [1.0, 1.0, 1.0], "small": [0.88, 1.08, 6.0], "lamp": [1.0, 1.0, 1.0]},
        "beam": {"len": 620.0, "k": 0.5, "period": 10.0},
        "grass_amp": 2.4,
        "gulls": [{"start": [260, 120], "vel": [24, -1.5], "size": 9}, {"start": [760, 70], "vel": [-15, 1.0], "size": 6}],
        "fog": [{"dy": 18, "hh": 34, "k": 0.55, "speed": 6.0, "mode": 1, "scale": 320, "lift": 0.25},
                {"dy": 120, "hh": 60, "k": 0.4, "speed": -4.0, "mode": 2, "scale": 360, "lift": 0.1},
                {"y": 505, "hh": 40, "k": 0.22, "speed": 9.0, "mode": 3, "scale": 300, "lift": 0.0}],
        "motes": {"rect": [300, 300, 1280, 530], "n": 24, "k": 0.4, "light": "small"},
        "vignette": 0.22,
    },
}


def merge(a, b):
    if isinstance(a, dict) and isinstance(b, dict):
        out = dict(a)
        for k, v in b.items():
            if k.startswith("_"):
                continue
            if v is None:
                out.pop(k, None)
            else:
                out[k] = merge(a.get(k), v) if k in a else v
        return out
    return b


def horizon_rows(lab):
    """Erste Wasserzeile in Spalten, in denen direkt darüber Himmel liegt (wie kinemagramm auto_scene)."""
    sky, water = lab == A.IDX["sky"], lab == A.IDX["water"]
    hs = []
    for x in range(0, lab.shape[1], 4):
        col = np.nonzero(water[:, x])[0]
        if len(col):
            y = int(col.min())
            if y >= 3 and sky[max(0, y - 4):y, x].any():
                hs.append(y)
    return hs


def warmth(img):
    return np.clip((img[..., 0] - img[..., 2]) * 2.0, 0, 1)


def light_pos(img, ys, xs):
    sub_w = (K.luma(img[ys, xs]) * (0.5 + warmth(img[ys, xs]))) ** 4
    if sub_w.sum() < 1e-9:
        return [float(xs.mean()), float(ys.mean())]
    return [float((xs * sub_w).sum() / sub_w.sum()), float((ys * sub_w).sum() / sub_w.sum())]


def overlay(img, lab, scene, path):
    ov = img * 0.6 + A.PALETTE[lab] * 0.4
    im = Image.fromarray((np.clip(ov, 0, 1) * 255).astype(np.uint8))
    d = ImageDraw.Draw(im)
    for x in range(0, W, 50):
        d.line([(x, 0), (x, H)], fill=(255, 255, 255) if x % 100 == 0 else (110, 110, 110))
        if x % 100 == 0:
            d.text((x + 2, 2), str(x), fill=(255, 255, 0))
    for y in range(0, H, 50):
        d.line([(0, y), (W, y)], fill=(255, 255, 255) if y % 100 == 0 else (110, 110, 110))
        if y % 100 == 0:
            d.text((2, y + 2), str(y), fill=(255, 255, 0))
    if scene.get("horizon_y"):
        d.line([(0, scene["horizon_y"]), (W, scene["horizon_y"])], fill=(0, 255, 255), width=2)
    for li in scene["lights"]:
        x, y = li["pos"]
        r = li["glow"]
        d.ellipse([x - r, y - r, x + r, y + r], outline=(255, 80, 80), width=2)
        d.text((x + 6, y - 6), li["name"], fill=(255, 220, 200))
    for f in scene.get("flames", []):
        x, y = f["pos"]
        d.rectangle([x - f["w"] / 2, y - f["h"], x + f["w"] / 2, y], outline=(255, 160, 0), width=2)
    for fb in scene.get("fog", []):
        d.rectangle([0, fb["y"] - fb["h"] / 2, W, fb["y"] + fb["h"] / 2], outline=(160, 220, 255))
    u = scene["ui"]
    d.rectangle([u["x"], u["y"], u["x"] + u["w"], u["y"] + u["h"]], outline=(255, 210, 120), width=2)
    im.save(path)


def process(ort, work, override):
    paint_name, mask_name = SOURCES[ort]
    src = Image.open(RAW / f"{paint_name}.png").convert("RGB")
    sw, sh = src.size
    img_src = np.asarray(src, np.float32) / 255.0
    report = {"src": f"assets/raw/{paint_name}.png", "src_size": [sw, sh]}
    mpath = RAW / f"{mask_name}.png"
    if not mpath.exists():
        sys.exit(f"{ort}: Maske fehlt ({mpath.name})")
    m = Image.open(mpath).convert("RGB")
    report["mask_size"] = list(m.size)
    lab_m = A.classify(np.asarray(m, np.float32) / 255.0)
    report["mask_shares"] = {n: round(float((lab_m == i).mean()), 4) for n, i in A.IDX.items()
                             if (lab_m == i).any()}
    lab0 = A.resize_lab(lab_m, (sw, sh))
    T = A.align(img_src, lab0)
    report["align"] = T
    lab = A.warp_lab(lab0, (T["sx"], T["sy"], T["dx"], T["dy"]), (sw, sh))

    # 2. Ausschnitt 16:9 ------------------------------------------------------------------------------
    ch = round(sw * 9 / 16)
    hs = horizon_rows(lab)
    h_src = float(np.median(hs)) if hs else None
    report["horizon_src"] = h_src
    report["horizon_src_share"] = round(h_src / sh, 3) if h_src else None
    if override.get("crop_y0") is not None:
        y0 = int(override["crop_y0"])
        report["crop_from"] = "scene.override.json"
    elif h_src is not None:
        y0 = int(round(np.clip(h_src - HORIZON_ROW * ch / H, 0, sh - ch)))
        report["crop_from"] = f"Horizont auf Zeile {HORIZON_ROW}"
    else:
        y0 = (sh - ch) // 2
        report["crop_from"] = "Mitte (kein Horizont)"
    box = (0, y0, sw, y0 + ch)
    report["crop_box"] = list(box)
    still_im = src.crop(box).resize((W, H), Image.LANCZOS)
    img = np.asarray(still_im, np.float32) / 255.0
    lab_s = A.resize_lab(lab[box[1]:box[3], box[0]:box[2]], (W, H))
    reg = {n: (lab_s == i).astype(np.float32) for n, i in A.IDX.items()}
    L = K.luma(img)
    warm = warmth(img)
    yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)

    # 3. Masken ----------------------------------------------------------------------------------------
    sky = K.smoothstep(0.25, 0.75, K.guided(img, reg["sky"], 4, 2e-3)) if reg["sky"].any() else reg["sky"]
    water = K.smoothstep(0.25, 0.75, K.guided(img, reg["water"], 4, 2e-3)) if reg["water"].any() else reg["water"]
    water = np.minimum(water, 1 - sky)
    hp = L - K.blur(L, 4)
    sat = img.max(-1) - img.min(-1)
    stars = K.smoothstep(0.08, 0.2, hp) * (sky > 0.95) * (L > 0.42) * (sat < 0.3)
    stars = np.clip(K.blur(stars, 1) * 2.2, 0, 1) * (sky > 0.9)

    scene = {"ort": ort, "ui": dict(UI), "lights": [], "flames": []}
    if h_src is not None:
        scene["horizon_y"] = round((h_src - y0) * H / ch, 1)
    wrows = np.nonzero(reg["water"].any(1))[0]
    if len(wrows):
        scene["water_bottom"] = int(np.percentile(np.nonzero(reg["water"])[0], 98))
    chans = {"fire": np.zeros((H, W), np.float32), "small": np.zeros((H, W), np.float32),
             "lamp": np.zeros((H, W), np.float32)}
    cfg_l = override.get("lights", {})
    for kind in ("fire", "small", "lamp"):
        comps = A.components(reg[CODE[kind]] > 0, min_px=4)[:6]
        for i, (ys, xs) in enumerate(comps):
            name = kind if i == 0 else f"{kind}{i + 1}"
            clip = cfg_l.get(name, {}).get("clip")      # [x0, y0, x1, y1]: Fläche auf ein Rechteck begrenzen
            if clip:
                keep = (xs >= clip[0]) & (xs <= clip[2]) & (ys >= clip[1]) & (ys <= clip[3])
                ys, xs = ys[keep], xs[keep]
                if not len(ys):
                    continue
            pos = light_pos(img, ys, xs)
            ext = max(xs.max() - xs.min(), ys.max() - ys.min()) / 2.0
            comp = np.zeros((H, W), np.float32)
            comp[ys, xs] = 1
            core = np.clip(K.blur(comp, 2) * 1.5, 0, 1) * (0.35 + 0.65 * K.smoothstep(0.15, 0.75, L))
            li = {"name": name, "channel": kind, "pos": [round(pos[0], 1), round(pos[1], 1)],
                  "bbox": [int(xs.min()), int(ys.min()), int(xs.max()), int(ys.max())], "px": int(len(ys)),
                  "glow": round(float(np.clip(ext * 1.2 + 12, 10.0, 220.0)), 1), "glow_k": 0.18 if kind == "fire" else 0.22}
            li = merge(li, {k: v for k, v in cfg_l.get(name, {}).items() if k != "clip"})
            pool_r = li.get("pool_r", {"fire": 260.0, "small": 40.0, "lamp": 0.0}[kind])
            if pool_r:
                d = np.hypot(xx - li["pos"][0], yy - li["pos"][1])
                fall = np.clip(1 - d / pool_r, 0, 1) ** 2
                pool = fall * K.smoothstep(0.05, 0.5, warm * L * 2) * li.get("pool_k", 0.7) * (1 - sky) * (1 - water)
                core = np.maximum(core, pool)
            chans[kind] = np.maximum(chans[kind], core)
            if li.get("skip"):
                continue
            scene["lights"].append({k: li[k] for k in ("name", "channel", "pos", "bbox", "px", "glow", "glow_k")})
    for ex in override.get("extra_lights", []):
        # Licht, das die KI-Maske nicht kennt (von Hand gesetzt): Leuchtfläche = helle Pixel im Kreis r
        d = np.hypot(xx - ex["pos"][0], yy - ex["pos"][1])
        core = (d < ex["r"]).astype(np.float32) * K.smoothstep(0.25, 0.7, L * (0.5 + warm))
        chans[ex["channel"]] = np.maximum(chans[ex["channel"]], np.clip(K.blur(core, 1) * 1.5, 0, 1))
        scene["lights"].append({"name": ex["name"], "channel": ex["channel"], "pos": ex["pos"],
                                "bbox": [int(ex["pos"][0] - ex["r"]), int(ex["pos"][1] - ex["r"]),
                                         int(ex["pos"][0] + ex["r"]), int(ex["pos"][1] + ex["r"])],
                                "px": int((core > 0.5).sum()), "glow": ex.get("glow", 24.0),
                                "glow_k": ex.get("glow_k", 0.22)})
    report["lights"] = [f"{li['name']}@{li['pos']}" for li in scene["lights"]]
    # Gemalte Lichthöfe im Himmel (Leuchtturmlampe) dürfen nicht mit dem Himmel wandern: im Umkreis der
    # Lampen steht der Himmel still (weicher Übergang von 1,0 bis 2,2 Lichthof-Radien)
    sky_full = sky.copy()
    for li in scene["lights"]:
        if li["channel"] == "lamp":
            d = np.hypot(xx - li["pos"][0], yy - li["pos"][1])
            sky = sky * K.smoothstep(1.0 * li["glow"], 2.2 * li["glow"], d)

    grass = reg[CODE["grass"]]
    if grass.any():
        grass = K.smoothstep(0.3, 0.7, K.guided(img, grass, 3, 3e-3)) * (1 - sky) * (1 - water)
    receiver = K.smoothstep(0.08, 0.45, warm * L * 2) * (1 - sky) * (1 - water)
    receiver = np.clip(K.blur(receiver, 3), 0, 1)
    # Kerze, Fenster und Lampen flackern mit ihrem eigenen Kanal, nicht im Takt des Feuers
    receiver *= 1 - np.clip(K.blur(np.maximum(chans["small"], chans["lamp"]), 3) * 2, 0, 1)
    # und nur in der Umgebung des Feuers (sonst flackert auch der gemalte Kerzenschein im Takt des Kamins)
    fire_l = [li for li in scene["lights"] if li["channel"] == "fire"]
    if fire_l:
        d = np.hypot(xx - fire_l[0]["pos"][0], yy - fire_l[0]["pos"][1])
        receiver *= np.clip(1 - d / 520.0, 0, 1) ** 0.5
    else:
        receiver *= 0
    beam_vis = K.blur(sky_full, 2)   # der Strahl beginnt an der Lampe, also auch im stillstehenden Umkreis

    # 4. Saubere Platte ---------------------------------------------------------------------------------
    known = np.clip(np.maximum(sky, water), 0, 1) * (1 - np.clip(K.blur(stars, 2) * 4, 0, 1))
    core_k = (K.box((known > 0.5).astype(np.float32), 3) > 0.999).astype(np.float32)
    known = np.minimum(known, core_k)
    plate_pp = K.pushpull(img, known ** 2)
    plate = K.mirror_fill(img, known > 0.5, plate_pp, reach=40)

    # 5. Szene ------------------------------------------------------------------------------------------
    lamps = [li for li in scene["lights"] if li["channel"] == "lamp"]
    if lamps:
        scene["lamp"] = lamps[0]["pos"]
    # Effekte: Planung aus FX, Lagen aus der Messung, Korrekturen aus dem Override (Schlüssel "fx")
    fx = merge(FX.get(ort, {}), override.get("fx", {}))
    hy = scene.get("horizon_y", 300.0)
    first = {k: next((li for li in scene["lights"] if li["channel"] == k), None) for k in ("fire", "small", "lamp")}
    fog = []
    for b in fx.get("fog", []):
        y = b["y"] if "y" in b else hy + b.get("dy", 0)
        fog.append({"y": round(float(y), 1), "hh": b["hh"], "k": b["k"], "speed": b["speed"], "mode": b["mode"],
                    "scale": b["scale"], "lift": b["lift"]})
    fx["fog"] = fog
    mo = fx.get("motes")
    if mo:
        if "around" in mo and first.get(mo["around"]):
            cx = first[mo["around"]]["pos"][0]
            mo["rect"] = [max(0.0, cx + mo["dx"][0]), mo["y"][0], min(float(W), cx + mo["dx"][1]), mo["y"][1]]
            mo["light"] = first[mo["around"]]["pos"]
        elif isinstance(mo.get("light"), str):
            mo["light"] = first[mo["light"]]["pos"] if first.get(mo["light"]) else [-9999, -9999]
        mo.pop("around", None)
        mo.pop("dx", None)
        mo.pop("y", None)
    if "lens" in fx and first["fire"]:
        x0, y0l, x1, y1l = first["fire"]["bbox"]
        fx["lens"]["rect"] = [x0, y0l, x1, y1l]
        fx["lens"]["center"] = first["fire"]["pos"]
    for rg in fx.pop("room_glow", []):
        # großer, schwacher Lichtschein im Raum, flackert mit dem Kanal seiner Lichtquelle (nur Lichthof)
        src_l = first.get(rg["at"])
        if src_l:
            scene["lights"].append({"name": rg["at"] + "_raum", "channel": src_l["channel"], "pos": src_l["pos"],
                                    "bbox": src_l["bbox"], "px": 0, "glow": rg["r"], "glow_k": rg["k"]})
    if water.max() > 0.5 and "glint_lo" not in fx:
        # Glitzern nur auf den hellsten 10 % des Wassers (90-%-Quantil der Helligkeit, gemessen)
        fx["glint_lo"] = round(float(np.percentile(L[water > 0.5], 90)), 3)
    scene["fx"] = fx
    for name, fa in override.get("flames_auto", {}).items():
        # Flamme über einer Lichtfläche aus der Maske: Basis im Anteil `base` der Höhe (0 oben, 1 unten)
        li = next((x for x in scene["lights"] if x["name"] == name), None)
        if li is None:
            continue
        x0, yt, x1, yb = li["bbox"]
        scene["flames"].append({"pos": [round((x0 + x1) / 2 + fa.get("dx", 0), 1),
                                        round(yt + fa.get("base", 0.5) * (yb - yt), 1)],
                                "w": round(fa.get("w_px", (x1 - x0) * fa.get("w", 1.0)), 1),
                                "h": float(fa.get("h", 60)), "k": float(fa.get("k", 0.8))})

    out = E / "assets" / ort
    out.mkdir(parents=True, exist_ok=True)
    still_im.save(out / "still.png")
    K.save_rgb(plate, out / "plate.png")
    K.save_rgb(np.stack([water, sky, stars], -1), out / "mask_a.png")
    K.save_rgb(np.stack([chans["fire"], chans["small"], chans["lamp"]], -1), out / "mask_b.png")
    K.save_rgb(np.stack([grass, receiver, beam_vis], -1), out / "mask_c.png")
    scene["_report"] = report
    (out / "scene.json").write_text(json.dumps(scene, ensure_ascii=False, indent=1) + "\n")
    stats = {"sky": round(float((sky > 0.5).mean()), 4), "water": round(float((water > 0.5).mean()), 4),
             "stars_px": int((stars > 0.5).sum()), "grass": round(float((grass > 0.5).mean()), 4),
             "fire_px": int((chans["fire"] > 0.5).sum()), "small_px": int((chans["small"] > 0.5).sum()),
             "lamp_px": int((chans["lamp"] > 0.5).sum())}
    report["stats"] = stats
    (out / "scene.json").write_text(json.dumps(scene, ensure_ascii=False, indent=1) + "\n")

    w = work / ort
    w.mkdir(parents=True, exist_ok=True)
    overlay(img, lab_s, scene, w / "overlay.png")
    ov = img * 0.45
    ov[..., 2] += sky * 0.5
    ov[..., 1] += water * 0.45
    ov[..., 0] += (chans["fire"] + chans["small"] + chans["lamp"]) * 0.55
    ov[..., 1] += grass * 0.35
    ov += stars[..., None] * 0.8
    K.save_rgb(np.clip(ov, 0, 1), w / "masks.png")
    K.save_rgb(plate, w / "plate.png")

    art = DEMO_ART / ort
    art.mkdir(parents=True, exist_ok=True)
    for f in DEMO_FILES:
        shutil.copy2(out / f, art / f)
    print(ort, json.dumps(report, ensure_ascii=False))
    return scene


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("orte", nargs="*", default=ORDER)
    ap.add_argument("--work", default=str(pathlib.Path(tempfile.gettempdir()) / "ortsserie-painterly-process"))
    a = ap.parse_args()
    work = pathlib.Path(a.work)
    ov_path = HERE / "scene.override.json"
    overrides = json.loads(ov_path.read_text()) if ov_path.exists() else {}
    # gemeinsames Rauschen (drei kachelbare Kanäle), wie kinemagramm prep.py
    noise_out = DEMO_ART / "noise.png"
    if not noise_out.exists():
        DEMO_ART.mkdir(parents=True, exist_ok=True)
        n = 256
        K.save_rgb(np.stack([K.tile_noise(n, 1.0, 11), K.tile_noise(n, 1.6, 23), K.tile_noise(n, 0.7, 37)], -1),
                   noise_out)
    for ort in a.orte:
        process(ort, work, overrides.get(ort, {}))
    print("ok")


if __name__ == "__main__":
    main()
