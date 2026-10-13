#!/usr/bin/env python3
"""Prüfbilder und Vergleichszahlen für ki-spritesheet (Fehlerbilder offen zeigen).

    .venv/bin/python styles/ki-spritesheet/scripts/make_checks.py

Schreibt nach assets/check/:
  walk_duplicates.png  Laufblatt am Kopf ausgerichtet: Bilder 1–4 über 5–8, Abweichung der Beinmasken
  walk_feet.png        Bodenläufe der Bilder 1–4 mit den Enden aus der Fußtabelle (Ferse/Zehe)
  idle_flicker.png     ganze Idle-Bilder gegen den gebauten Idle: rot = Pixel, die sich zum Vorbild ändern
  wave_flip.png        beide Winkblätter, Bild 3 und 5 (Seitenwechsel) rot umrahmt
  scale_drift.png      Bild 1 jedes Blatts im Blattmaßstab (oben) und normiert (unten)
  metrics.json         Kopfzittern und Höhen der rohen Fassung gegen die korrigierte
"""
import json, pathlib, sys

import numpy as np
from PIL import Image, ImageDraw, ImageFont

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import kss_sheet as K  # noqa: E402
from build_sprites import place, pm_resize, flicker, TIP  # noqa: E402

E = pathlib.Path(__file__).resolve().parents[1]
RAW = E / "assets" / "raw"
ART = E / "demo" / "art"
OUT = E / "assets" / "check"
BG = (214, 220, 228, 255)
FONT = ImageFont.truetype(str(E / "demo" / "fonts" / "JetBrainsMono-var.ttf"), 14)
SMALL = ImageFont.truetype(str(E / "demo" / "fonts" / "JetBrainsMono-var.ttf"), 12)


def on_bg(arr, bg=BG):
    im = Image.new("RGBA", (arr.shape[1], arr.shape[0]), bg)
    im.alpha_composite(Image.fromarray(arr, "RGBA"))
    return im


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    sheets = json.loads((E / "assets" / "sheets.json").read_text())
    meta = json.loads((ART / "anim.json").read_text())
    G = sheets["scale"]["display_per_walk_px"]
    W = K.split_frames(RAW / "walk.png", 8)
    mw = sheets["walk"]["frames"]
    metrics = {}

    # ---- walk_duplicates.png
    cw, ch = 150, 215
    img = Image.new("RGBA", (cw * 4 + 20, ch * 2 + 70), (40, 42, 50, 255))
    d = ImageDraw.Draw(img)
    ld = sheets["walk"]["leg_diff"]
    for i, f in enumerate(W):
        m = mw[i]
        cell = place(f["img"], G * m["head_scale"], m["head"][0] - f["x0"], m["bottom"] - f["y0"] + 1, 120, 205, cw, ch)
        x, y = 10 + (i % 4) * cw, 30 + (i // 4) * (ch + 20)
        img.alpha_composite(on_bg(cell), (x, y))
        d.text((x + 4, y + 2), f"Bild {i + 1}", font=SMALL, fill=(30, 30, 40))
        if i >= 4:
            d.text((x + 4, y + ch + 2), f"zu Bild {i - 3}: {round(ld[i][i - 4] * 100)} %", font=SMALL,
                   fill=(255, 140, 120))
    other = min(ld[i][j] for i in range(4) for j in range(4) if i != j)
    d.text((10, 6), f"Laufblatt am Kopf: 5–8 wiederholen 1–4 (andere Paare ≥ {round(other * 100)} %)", font=SMALL,
           fill=(230, 232, 240))
    img.convert("RGB").save(OUT / "walk_duplicates.png")

    # ---- walk_feet.png: Unterkante der Bilder 1–4, Bodenläufe und die Enden der Fußtabelle
    from build_sprites import WALK_FEET
    img = Image.new("RGBA", (4 * 230 + 20, 150 + 40), (40, 42, 50, 255))
    d = ImageDraw.Draw(img)
    ends = {}
    for (a, b) in WALK_FEET:
        ends.setdefault(a[0], []).append(a)
        ends.setdefault(b[0], []).append(b)
    for i in range(4):
        f, m = W[i], mw[i]
        crop = f["img"][-110:]
        im = on_bg(crop)
        x = 10 + i * 230
        img.alpha_composite(im, (x, 40))
        dd = ImageDraw.Draw(img)
        h = crop.shape[0]
        base = 40 + h
        dd.line([(x, base), (x + crop.shape[1], base)], fill=(0, 200, 0))
        for (fi, ri, end) in ends.get(i, []):
            r = m["feet"][ri]
            ex = (r[0] if end == "heel" else r[1]) - f["x0"]
            dd.line([(x + ex, base - 30), (x + ex, base + 4)], fill=(255, 200, 60), width=2)
            dd.text((x + ex - 14, base - 46), "Ferse" if end == "heel" else "Zehe", font=SMALL, fill=(255, 200, 60))
        dd.text((x, 22), f"Bild {i + 1}", font=SMALL, fill=(230, 232, 240))
    d.text((10, 4), "Fußtabelle: Ende des Standfußes, das beim Bildwechsel liegen bleibt", font=SMALL,
           fill=(230, 232, 240))
    img.convert("RGB").save(OUT / "walk_feet.png")

    # ---- idle_flicker.png
    I = K.split_frames(RAW / "idle.png", 6)
    mi = sheets["idle"]["frames"]
    ki = sheets["scale"]["display_per_sheet_px"]["idle"]
    whole = [place(I[i]["img"], ki, (mi[i]["feet"][0][0] + mi[i]["feet"][0][1]) / 2 - I[i]["x0"],
                   mi[i]["bottom"] - I[i]["y0"] + 1, 70, 200, 140, 206) for i in range(6)]
    strip = Image.open(ART / "badger_idle.png").convert("RGBA")
    a = meta["anims"]["idle"]
    cwi, chi = a["size"]
    built = []
    for c in (0, 1, 2, 1, 0, 3):
        cell = np.asarray(strip.crop((c * cwi, 0, (c + 1) * cwi, chi)))
        canvas = np.zeros((206, 140, 4), np.uint8)
        ox, oy = int(70 - a["anchor"][0]), int(200 - a["anchor"][1])
        canvas[oy:oy + chi, ox:ox + cwi] = cell
        built.append(canvas)

    def changes(seq):
        out = []
        for j, cur in enumerate(seq):
            prev = seq[j - 1]
            dd_ = np.abs(cur.astype(int) - prev.astype(int))
            ch_ = ((dd_[..., :3].max(-1) > 40) | (dd_[..., 3] > 128)) & ((cur[..., 3] > 128) | (prev[..., 3] > 128))
            im = on_bg(cur).convert("RGB")
            arr = np.asarray(im).copy()
            arr[ch_] = (arr[ch_] * 0.3 + np.array([255, 30, 30]) * 0.7).astype(np.uint8)
            out.append(Image.fromarray(arr))
        return out
    rows = [changes(whole), changes(built)]
    img = Image.new("RGB", (6 * 140 + 20, 2 * 206 + 80), (40, 42, 50))
    d = ImageDraw.Draw(img)
    for r, row in enumerate(rows):
        for j, im in enumerate(row):
            img.paste(im, (10 + j * 140, 30 + r * (206 + 22)))
    fw = sheets["idle"]["flicker_whole_frames"]
    fb = sheets["idle"]["flicker_built"]
    d.text((10, 6), f"Idle aus ganzen KI-Bildern: {round(min(fw) * 100)}–{round(max(fw) * 100)} % der Figurpixel "
           "ändern sich je Bild (rot)", font=SMALL, fill=(230, 232, 240))
    d.text((10, 30 + 206 + 2), f"gebaut (Körper + Lid + Atmen): rund {round(max(fb) * 100)} %, nur Oberkörper um "
           "1 px versetzt bzw. Lid", font=SMALL, fill=(230, 232, 240))
    img.save(OUT / "idle_flicker.png")

    # ---- wave_flip.png
    rows = []
    for sheet in ("wave", "wave2"):
        fr = K.split_frames(RAW / f"{sheet}.png", 6)
        ims = []
        for f in fr:
            h, w = f["mask"].shape
            ims.append(on_bg(pm_resize(f["img"], (round(w * 0.42), round(h * 0.42)), (0, 0, w, h))))
        rows.append(ims)
    img = Image.new("RGB", (6 * 120 + 20, 2 * 220 + 60), (40, 42, 50))
    d = ImageDraw.Draw(img)
    for r, ims in enumerate(rows):
        for j, im in enumerate(ims):
            x, y = 10 + j * 120, 40 + r * 230 + (200 - im.height)
            img.paste(im.convert("RGB"), (x, y))
            if j in (2, 4):
                d.rectangle([x - 2, y - 2, x + im.width + 1, y + im.height + 1], outline=(255, 70, 60), width=3)
        d.text((10, 22 + r * 230), ["Winkblatt 1 (Prompt mit „one arm“)",
                                     "Winkblatt 2 (Seiten ausdrücklich benannt, Wechsel verboten)"][r],
               font=SMALL, fill=(230, 232, 240))
    d.text((10, 4), "Bild 3 und 5: Paket und Winkarm wechseln die Seite – in beiden Blättern", font=SMALL,
           fill=(255, 140, 120))
    img.save(OUT / "wave_flip.png")

    # ---- scale_drift.png
    firsts = [("walk", K.split_frames(RAW / "walk.png", 8)[0]), ("idle", I[0]),
              ("jump", K.split_frames(RAW / "jump.png", 6)[5]), ("wave2", K.split_frames(RAW / "wave2.png", 6)[0])]
    ks = sheets["scale"]["display_per_sheet_px"]
    keymap = {"walk": "walk", "idle": "idle", "jump": "jump", "wave2": "wave"}
    img = Image.new("RGB", (4 * 170 + 20, 2 * 240 + 70), (40, 42, 50))
    d = ImageDraw.Draw(img)
    for j, (name, f) in enumerate(firsts):
        h, w = f["mask"].shape
        a1 = pm_resize(f["img"], (round(w * 0.5), round(h * 0.5)), (0, 0, w, h))
        k = ks[keymap[name]]
        a2 = pm_resize(f["img"], (round(w * k), round(h * k)), (0, 0, w, h))
        for r, arr in enumerate((a1, a2)):
            im = on_bg(arr).convert("RGB")
            x = 10 + j * 170
            y = 30 + r * 250 + (235 - im.height)
            img.paste(im, (x, y))
            d.line([(x - 4, 30 + r * 250 + 235), (x + 160, 30 + r * 250 + 235)], fill=(0, 200, 0))
        d.text((10 + j * 170, 30 + 250 + 236), f"{name}: ×{sheets['scale']['sheet_vs_walk'][keymap[name]]:.3f}",
               font=SMALL, fill=(230, 232, 240))
    d.text((10, 6), "oben: Blattmaßstab (alle ×0,5) – unten: auf Kopfgröße bzw. Standhöhe normiert", font=SMALL,
           fill=(230, 232, 240))
    img.save(OUT / "scale_drift.png")

    # ---- Zahlen: rohe Fassung (sprites.py slice, Schwerpunkt, Boden) gegen korrigiert
    raw = meta["raw"]["walk"]
    rs = np.asarray(Image.open(ART / "raw_walk.png").convert("RGBA"))
    # Bildmaßstab der rohen Laufbilder so, dass ihre mittlere Höhe der korrigierten entspricht
    corr = meta["anims"]["walk"]
    cs = np.asarray(Image.open(ART / "badger_walk.png").convert("RGBA"))
    cw_, ch_ = corr["size"]
    corr_h = []
    for c in range(4):
        al = cs[:, c * cw_:(c + 1) * cw_, 3] > 128
        ys = np.flatnonzero(al.any(1))
        corr_h.append(ys[-1] - ys[0] + 1)
    k = float(np.mean(corr_h)) / float(np.mean(raw["heights"][:4]))
    tips = np.array([t[0] for t in raw["snout"]], float) * k
    metrics["raw_walk_head_x_spread_px"] = round(float(tips.max() - tips.min()), 1)
    metrics["raw_walk_head_x_step_px"] = [round(float(v), 1) for v in np.diff(np.r_[tips, tips[:1]])]
    metrics["raw_walk_heights_px"] = [round(h * k) for h in raw["heights"]]
    metrics["corrected_walk_heights_px"] = [int(h) for h in corr_h]
    metrics["raw_note"] = ("rohe Laufbilder (sprites.py slice, Schwerpunkt waagerecht, Unterkante senkrecht) auf die "
                           "mittlere Höhe der korrigierten skaliert; Kopf = Schnauzenspitze im oberen Drittel")
    # Größensprung beim Zustandswechsel in der rohen Fassung (sprites.py slice --height je Blatt)
    rel = {}
    for name in ("walk", "idle", "jump", "wave"):
        rel[name] = meta["raw"][name]["heights"]
    metrics["raw_heights_by_state_px_at_slice120"] = rel
    (OUT / "metrics.json").write_text(json.dumps(metrics, ensure_ascii=False, indent=1))
    print(json.dumps(metrics, ensure_ascii=False))


if __name__ == "__main__":
    main()
