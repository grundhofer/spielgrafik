#!/usr/bin/env python3
"""Kopiert die verarbeiteten Assets nach demo/art/ und schreibt demo/art/scene.json (Lagen, Lichtpunkte,
Effekte, Oberfläche und den ganzen Ablauf der Figur bei 30 Bildern/s).

    .venv/bin/python styles/tusche-sumie/tools/stage.py

Liest assets/bg_meta.json (Lichtpunkte, Laufzeile, Wasserband; aus bg_override.json) und
assets/badger_meta.json (Einzelbilder, Ankerpunkte, Vorschub je Laufbild; aus prep_badger.py).
"""
import json, shutil

import numpy as np
from PIL import Image

from inkutil import ROOT, rng

DEMO = ROOT / "demo"
ART = DEMO / "art"
FPS = 30
N = 180


def res(p):
    return "res://art/" + p


def copy(src, dst):
    d = ART / dst
    d.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(ROOT / src, d)
    return res(dst)


def smoke_foot(name, thresh=0.08):
    """Fuß einer Rauchfahne: unterste Zeile mit sichtbarer Dichte (Alpha > thresh) und die Mitte der Dichte in den
    sechs Zeilen darüber, in Texturpixeln. Der Rauch-Sprite setzt diesen Punkt auf den Schornstein."""
    a = np.asarray(Image.open(ROOT / f"assets/fx/{name}.png"))[..., 3] / 255.0
    fy = int(np.where(a.max(axis=1) > thresh)[0].max())
    band = a[fy - 6:fy + 1]
    xs = np.arange(a.shape[1])
    w = band.sum(axis=0)
    return [round(float((xs * w).sum() / w.sum()), 1), fy]


def ripple_slots(meta, texs, count, seed=5):
    """Wellenstriche: feste Plätze im Wasserband, je Platz ein Zyklus aus Ziehen, Halten, Ausblenden."""
    r = rng(seed)
    x0, y0, x1, y1 = meta["water"]
    slots = []
    for i in range(count):
        y = y0 + (y1 - y0) * ((i + r.uniform(0.1, 0.9)) / count) ** 1.2
        depth = (y - y0) / max(1, (y1 - y0))           # vorn größer und dunkler
        s = 0.17 + 0.2 * depth
        slots.append({
            "x": float(r.uniform(x0, x1)), "y": float(y), "sx": s * r.uniform(0.85, 1.15), "sy": s * 0.8,
            "period": float(r.uniform(3.2, 4.6)), "t0": float(r.uniform(0, 4.0)),
            "draw": 0.55, "hold": float(r.uniform(0.5, 1.1)), "fade": 1.0,
            "drift": float(r.uniform(-4, 4)), "flip": bool(r.random() < 0.4),
        })
    # Plätze, die auf Booten, Steg oder Felsen liegen, lässt die Override-Datei aus
    keep = [s for s in slots if not any(a <= s["x"] <= c and b <= s["y"] <= d for a, b, c, d in meta.get("no_ripple", []))]
    return keep


def badger_timeline(bm):
    """Ablauf: hereinlaufen, anhalten (Stehen), zur Kamera drehen, winken, blinzeln. Je Bild [name, x, atmen]."""
    plan = bm["plan"]
    walk = bm["walk"]                    # Namen der Laufbilder in Reihenfolge
    adv = bm["advance"]                  # Vorschub in px beim Wechsel auf das jeweilige Bild
    hold = int(plan["walk_hold"])        # Bildschirmbilder je Laufbild (3 = 10 Bilder/s)
    x = float(plan["x_start"])
    tl = []
    i = 0
    f = 0
    stops = plan.get("stop_frames", [])
    while f < N:
        name = walk[i % len(walk)]
        for _ in range(hold):
            tl.append([name, round(x, 2), 0.0])
            f += 1
        # anhalten erst in einem Durchgangsbild (Füße beieinander), damit das Stehbild ohne Sprung folgt
        if x >= plan["x_stop"] and (not stops or name in stops):
            break
        i += 1
        x += adv[i % len(walk)]
    for name, dur in plan["after"]:
        for _ in range(int(round(dur * FPS))):
            tl.append([name, round(x, 2), 0.0])
    while len(tl) < N:
        tl.append([plan["after"][-1][0], round(x, 2), 0.0])
    tl = tl[:N]
    # Atmen in den Stehbildern: sanft, 0,5 Hz
    for k, e in enumerate(tl):
        if not e[0].startswith("walk"):
            e[2] = round(0.012 * np.sin(k / FPS * 2 * np.pi * 0.5), 4)
    return tl


def main():
    if ART.exists():
        shutil.rmtree(ART)
    ART.mkdir(parents=True)
    bgm = json.loads((ROOT / "assets/bg_meta.json").read_text())
    bm = json.loads((ROOT / "assets/badger_meta.json").read_text())
    sc = {
        "paper": copy("assets/paper.png", "paper.png"),
        "bg": copy("assets/bg_ink.png", "bg_ink.png"),
        "bg_noise": copy("assets/fx/bg_noise.png", "fx/bg_noise.png"),
        "bg_anim": bgm["bg_anim"],
        "glow": copy("assets/fx/glow.png", "fx/glow.png"),
        "lights": bgm["lights"],
    }
    mists = []
    for m in bgm["mist"]:
        m = dict(m)
        m["tex"] = copy(f"assets/fx/{m['tex']}.png", f"fx/{m['tex']}.png")
        mists.append(m)
    sc["mist"] = mists
    rt = [copy(f"assets/fx/{n}.png", f"fx/{n}.png") for n in bgm["ripple_textures"]]
    slots = ripple_slots(bgm, rt, bgm["ripple_count"])
    sc["ripples"] = {"textures": rt, "count": len(slots), "slots": slots, "amount": bgm["ripple_amount"]}
    sm = dict(bgm["smoke"])
    sm["feet"] = [smoke_foot(n) for n in sm["textures"]]
    sm["textures"] = [copy(f"assets/fx/{n}.png", f"fx/{n}.png") for n in sm["textures"]]
    sc["smoke"] = sm
    gl = dict(bgm["gulls"])
    gl["frames"] = [copy(f"assets/fx/{n}.png", f"fx/{n}.png") for n in gl["frames"]]
    sc["gulls"] = gl

    frames = {}
    for name, f in bm["frames"].items():
        frames[name] = {"tex": copy(f"assets/badger/{name}.png", f"badger/{name}.png"), "ax": f["ax"], "ay": f["ay"]}
    sc["badger"] = {"frames": frames, "timeline": badger_timeline(bm), "foot_y": bgm["foot_y"]}
    if "shadow" in bgm:
        sh = dict(bgm["shadow"])
        sh["tex"] = copy(f"assets/fx/{sh['tex']}.png", f"fx/{sh['tex']}.png")
        sc["badger"]["shadow"] = sh

    ui = dict(bgm["ui"])
    ui["font"] = "res://fonts/ShipporiMincho-Regular-latin.ttf"
    ui["font_bold"] = "res://fonts/ShipporiMincho-SemiBold-latin.ttf"
    ui["seal"]["tex"] = copy("assets/ui/seal.png", "ui/seal.png")
    ui["highlight"]["tex"] = copy(f"assets/fx/{ui['highlight']['tex']}.png", f"fx/{ui['highlight']['tex']}.png")
    for c in ui["choices"]:
        c["dot"] = copy(f"assets/fx/{c['dot']}.png", f"fx/{c['dot']}.png")
    sc["ui"] = ui
    (ART / "scene.json").write_text(json.dumps(sc, indent=1, ensure_ascii=False))
    print("ok scene.json:", len(sc["badger"]["timeline"]), "Figurenbilder,", len(slots), "Wellenstriche")


if __name__ == "__main__":
    main()
