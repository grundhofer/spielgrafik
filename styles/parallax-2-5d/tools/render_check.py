#!/usr/bin/env python3
"""Prüfungen der Demo in der echten Godot-Ausgabe; schreibt assets/render_check.json und assets/compare_fill.png.

    .venv/bin/python -I styles/parallax-2-5d/tools/render_check.py <tempdir>

1. Bildtreue: Gemälde-Kamera (0,0,0), nur Relief (--nofx --nowave --noui) gegen den Bildausschnitt des Gemäldes.
2. Lückenfüllung: Endposition der Fahrt (t = 5,97 s, ohne Oberfläche und Wasserbewegung) mit Zwischenfüllung und
   sauberer Platte (mittlere und hintere Schicht) gegen „Streckung“ (--fill=stretch: nur die vordere Schicht, Dreiecke
   über Tiefensprünge gespannt). Anteil der Pixel, die sich unterscheiden = Fläche, die beim Fahren aufgedeckt wird;
   mit --tint, welcher Anteil aus der mittleren und der hinteren Schicht stammt. Vergleichsbild mit fünf Ausschnitten
   (Laterne, Steg, Fässer, Hausfront, Leuchtturm).
3. Parallaxe: Verschiebung ausgewählter Punkte zwischen erstem und letztem Bild (aus dem Kameramodell, das die
   Demo verwendet; in Godot per Blockvergleich nachgemessen, auch an Turmspitze und Schornstein des Wärterhauses,
   die sich vorher als Inseln mit 22 m Tiefe ablösten, und an einer sichtbaren Kai-Zeile).
4. Reproduzierbarkeit (zwei Läufe bitgleich) und Renderer: Mobile und Compatibility gegen Forward+.
"""
import json, pathlib, sys
import numpy as np
from PIL import Image, ImageDraw, ImageFont

S = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(S / "tools"))
from shot import render  # noqa: E402

TMP = pathlib.Path(sys.argv[1])
CAL = json.loads((S / "demo/scene/calib.json").read_text())
CENTER, FH = (768.0, 506.0), 792.0
CAM_END = np.array([0.3, -0.25, -0.9])


def img(p):
    return np.asarray(Image.open(p).convert("RGB")).astype(np.float32)


def one(name, user, method=None, frames=1):
    pngs, errs = render(TMP / name, frames, user, method)
    return pngs, errs


def proj(P, cam):
    """Weltpunkt -> Bildpixel (1280×720) bei Kameraposition cam (Kamera ohne Drehung, verschobenes Frustum)."""
    f, cx, yh = CAL["f"], CAL["cx"], CAL["yh"]
    d = np.asarray(P) - cam
    u = cx + f * d[0] / -d[2]
    v = yh - f * d[1] / -d[2]
    k = 720.0 / FH
    return ((u - CENTER[0]) * k + 640.0, (v - CENTER[1]) * k + 360.0)


def main():
    res = {}
    # 1. Bildtreue
    p, e = one("fid", ["--nofx", "--nowave", "--noui", "--cam=0,0,0"])
    r = img(p[0])
    W, H = CAL["image"]
    w_src = FH * 1280 / 720
    box = (round(CENTER[0] - w_src / 2), round(CENTER[1] - FH / 2), round(CENTER[0] + w_src / 2), round(CENTER[1] + FH / 2))
    c = np.asarray(Image.open(S / "demo/scene/color.png").crop(box).resize((1280, 720), Image.LANCZOS)).astype(np.float32)
    d = np.abs(r - c).mean(2)
    res["fidelity"] = {"mean_abs_255": round(float(d.mean()), 2), "share_over_24": round(float((d > 24).mean()), 4),
                       "note": "Abweichungen fast nur an Kanten (Mipmap-Filter gegen Lanczos, 2-px-Gitter)"}

    # 2. Lückenfüllung
    pe, _ = one("end_plate", ["--t0=5.97", "--noui", "--nowave"])
    ps, _ = one("end_stretch", ["--t0=5.97", "--noui", "--nowave", "--fill=stretch"])
    pt, _ = one("end_tint", ["--t0=5.97", "--noui", "--nowave", "--tint"])
    a, b, tt = img(pe[0]), img(ps[0]), img(pt[0])
    diff = np.abs(a - b).max(2) > 24
    # eingefärbt: vordere Schicht × (1; 0,45; 0,45), mittlere × (0,45; 1; 0,45), hintere × (0,45; 0,6; 1).
    # Welche Vorhersage passt am besten?
    err = np.stack([np.abs(tt - a * np.array(k)).sum(2) for k in ((1.0, 0.45, 0.45), (0.45, 1.0, 0.45),
                                                                     (0.45, 0.6, 1.0))])
    best = err.argmin(0)
    clear = np.sort(err, 0)[1] - np.sort(err, 0)[0] > 6
    res["fill"] = {"share_plate_vs_stretch_differs": round(float(diff.mean()), 4),
                   "share_mid_layer_visible_at_end": round(float(((best == 1) & clear).mean()), 4),
                   "share_back_layer_visible_at_end": round(float(((best == 2) & clear).mean()), 4)}
    # Vergleichsbild: fünf Ausschnitte, je Streckung | Zwischenfüllung + Platte | eingefärbt
    crops = [(150, 20, 470, 330), (280, 250, 600, 560), (930, 380, 1250, 690), (0, 220, 320, 530),
             (960, 20, 1280, 330)]
    sheet = Image.new("RGB", (3 * 330, len(crops) * 315 + 24), (16, 16, 22))
    dr = ImageDraw.Draw(sheet)
    font = ImageFont.truetype(str(S / "demo/fonts/EBGaramond-wght.ttf"), 16)
    for j, lab in enumerate(("Streckung", "Zwischenfüllung + saubere Platte",
                             "eingefärbt: vorn rot, Mitte grün, hinten blau")):
        dr.text((10 + j * 330, 3), lab, fill=(230, 230, 230), font=font)
    for i, bx in enumerate(crops):
        for j, src in enumerate((ps[0], pe[0], pt[0])):
            sheet.paste(Image.open(src).convert("RGB").crop(bx), (j * 330, 24 + i * 315))
    sheet.save(S / "assets/compare_fill.png")

    # 3. Parallaxe (Kameramodell)
    pts = {k: v for k, v in CAL["points"].items()}
    f, cx, yh = CAL["f"], CAL["cx"], CAL["yh"]

    def ground(x_src, y_src, h):
        z = h * f / (y_src - yh)
        return [(x_src - cx) * z / f, -h, -z]
    fd = np.asarray(Image.open(S / "demo/scene/front_depth.png")).astype(np.float64)
    sdisp = (fd[..., 0] * 256 + fd[..., 1]) / 65535

    def src_point(x, y):
        z = CAL["z_min"] / float(np.median(sdisp[y - 2:y + 3, x - 2:x + 3]))
        return [(x - cx) * z / f, -(y - yh) * z / f, -z]
    extra = {"Kai sichtbar (Zeile 740)": ground(700, 740, CAL["hq"]), "Kai Mitte (Zeile 700)": ground(700, 700, CAL["hq"]),
             "Turmspitze": src_point(1350, 218), "Schornstein Wärterhaus": src_point(1385, 310),
             "Fass rechts": src_point(1210, 720), "Kiste vorn": src_point(1420, 800),
             "Boot rechts (Rumpf)": src_point(900, 590), "Himmel/Inseln": [0, 30, -4000]}
    par = {}
    for k, P in list(pts.items()) + list(extra.items()):
        p0 = proj(P, np.zeros(3)); p1 = proj(P, CAM_END)
        par[k] = {"z_m": round(-float(P[2]), 1), "dx_px": round(p1[0] - p0[0], 1), "dy_px": round(p1[1] - p0[1], 1)}
    res["parallax_first_to_last_frame"] = par
    # Nachmessen in Godot: Ausschnitt um den Punkt im ersten Bild, im letzten Bild per Blockvergleich gesucht
    # (Summe der quadrierten Abweichungen, ganzzahlige Verschiebung im Umkreis von 90 px). Der Maßstab ändert sich
    # durch das Vorfahren um wenige Prozent, der Ausschnitt ist klein genug.
    pn, _ = one("end_nofx", ["--nofx", "--nowave", "--noui", "--cam=%g,%g,%g" % tuple(CAM_END)])
    i0, i1 = img(p[0]).mean(2), img(pn[0]).mean(2)
    meas = {}
    for k, P in (("lantern", pts["lantern"]), ("lighthouse", pts["lighthouse"]), ("Fass rechts", extra["Fass rechts"]),
                 ("Boot rechts (Rumpf)", extra["Boot rechts (Rumpf)"]), ("Turmspitze", extra["Turmspitze"]),
                 ("Schornstein Wärterhaus", extra["Schornstein Wärterhaus"]),
                 ("Kai sichtbar (Zeile 740)", extra["Kai sichtbar (Zeile 740)"])):
        x, y = (int(round(q)) for q in proj(P, np.zeros(3)))
        r_ = 12
        tpl = i0[y - r_:y + r_ + 1, x - r_:x + r_ + 1]
        if tpl.shape != (2 * r_ + 1, 2 * r_ + 1):
            meas[k] = {"error": "Punkt am Bildrand"}
            continue
        best = (np.inf, 0, 0)
        for dy in range(-90, 91):
            for dx in range(-130, 131):
                yy0, xx0 = y + dy - r_, x + dx - r_
                if yy0 < 0 or xx0 < 0 or yy0 + 2 * r_ + 1 > 720 or xx0 + 2 * r_ + 1 > 1280:
                    continue
                e = ((i1[yy0:yy0 + 2 * r_ + 1, xx0:xx0 + 2 * r_ + 1] - tpl) ** 2).mean()
                if e < best[0]:
                    best = (e, dx, dy)
        meas[k] = {"godot_dx_px": best[1], "godot_dy_px": best[2],
                   "model_dx_px": par[k]["dx_px"], "model_dy_px": par[k]["dy_px"]}
    res["parallax_measured_in_godot"] = meas

    # 4. Reproduzierbarkeit und Renderer
    r1, _ = one("rep1", ["--t0=3.0"], frames=3)
    r2, _ = one("rep2", ["--t0=3.0"], frames=3)
    res["bit_identical_runs"] = all((img(x) == img(y)).all() for x, y in zip(r1, r2))
    out = {}
    for m in ("mobile", "gl_compatibility"):
        pm, em = one("m_" + m, ["--t0=3.0"], method=m, frames=3)
        if not pm:
            out[m] = {"error": em[:3]}
            continue
        dd = np.abs(img(pm[-1]) - img(r1[-1]))
        out[m] = {"mean_abs_255": round(float(dd.mean()), 2), "share_over_24": round(float((dd.max(2) > 24).mean()), 4),
                  "errors": em[:3]}
    res["renderers_vs_forward_plus"] = out
    (S / "assets/render_check.json").write_text(json.dumps(res, indent=1, ensure_ascii=False))
    print(json.dumps(res, indent=1, ensure_ascii=False))


if __name__ == "__main__":
    main()
