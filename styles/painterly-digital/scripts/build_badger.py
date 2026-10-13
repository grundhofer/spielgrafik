#!/usr/bin/env python3
"""Dachs-Kurier als Schnittfigur (Cut-out-Rig) aus EINEM gemalten Bild im Zielstil.

Quelle: assets/raw/badger_side.png – agy hat shared/badger/walk_painted.png, Bild 3 (Durchschwung: nahes Bein
senkrecht unter der Hüfte, fernes Bein hinten angehoben) in derselben Pose im Zielstil übermalt
(Layout-Referenz assets/raw/badger_layout.png, Stilreferenz assets/raw/master.png, Kostüm
shared/badger/master_sheet.png). Die Silhouette stimmt mit der Vorlage überein (IoU 0,997), deshalb gelten die
an walk_painted.png abgelesenen Punkte weiter; sie werden mit W() in das neue Bild umgerechnet.

Die Figur wird in drei Teile zerlegt und in Godot per Code bewegt:
  Rumpf (Kopf, Arme, Paket, Tasche, Schalwicklung), ein Bein (nah und abgedunkelt fern),
  hinteres Schalende (schwingt an einer gedämpften Feder nach).

Gegen die helle Schnittnaht: Alle Teile teilen sich EINE Farbebene (das ganze Bild einmal vormultipliziert
verkleinert und zurückgerechnet). Nur das Alpha kommt aus der jeweiligen Teilmaske. So hat die weiche
Unterkante des Rumpfs exakt die Fellfarbe des Beins darunter; vorher wurde jedes Teil einzeln verkleinert, und
an der Schnittkante entstanden durch Lanczos-Überschwinger aufgehellte Pixel.

Ausgabe (assets/badger/, Kopie nach demo/art/):
  badger_body.png, badger_leg.png, badger_tail.png   Teile in Endgröße
  badger_rig.json     Drehpunkte (Hüfte, Schal), Ferse, Zehe, Sohle relativ zur Hüfte (px)
  badger_preview.png  Rumpf + Beine + Schalende in Ruhe, 3-fach (zur Sichtprüfung)
"""
import json, pathlib, shutil
import numpy as np
from PIL import Image, ImageDraw, ImageFilter

S = pathlib.Path(__file__).resolve().parent.parent
SRC = S / "assets" / "raw" / "badger_side.png"
OUT = S / "assets" / "badger"
ART = S / "demo" / "art"
HEIGHT_PX = 140                      # Figurenhöhe Mütze bis Sohle im Spiel (Haustür ~150 px)

# Abbildung walk_painted.png (Bild 3) -> badger_side.png, aus den Umrissen gemessen:
# Umriss dort (741,111)-(1058,647), hier (270,103)-(761,933)
_S = (933 - 103) / (647 - 111)


def W(x, y):
    return (270 + (x - 741) * _S, 103 + (y - 111) * _S)


TOP, SOLE = W(0, 111)[1], W(0, 645)[1]       # oberster Pixel (Mütze), Fußsohle
HIP = W(939, 500)                    # Drehpunkt des Beins: über der Mitte der Sohle (Ferse/Zehe symmetrisch)
HEEL = W(884, 645)
TOE = W(994, 641)
CUT_Y = W(0, 544)[1]                 # Rumpf endet hier (Fellkante)
CUT_FEATHER = 6 * _S
LEG_POLY = [W(x, y) for x, y in [(868, 488), (942, 488), (960, 540), (966, 590), (996, 614), (1004, 652),
                                  (878, 652), (873, 600), (857, 560), (855, 520)]]
LEG_FEATHER = (W(0, 490)[1], W(0, 516)[1])   # Bein blendet oben weich in das Fell des Rumpfs
# Hinteres Schalende (direkt in badger_side.png abgelesen): Teil außerhalb der Weste. Das Teilbild reicht
# zusätzlich ein ~16 px breites Band (TAIL_UNDER) unter Weste und Schalwicklung, damit beim Ausschwingen keine Lücke aufgeht
# (der Rumpf wird darüber gezeichnet).
TAIL_POLY = [(392, 366), (388, 400), (382, 430), (377, 455), (371, 480), (362, 506), (351, 532), (326, 538),
             (298, 518), (276, 492), (260, 466), (262, 440), (292, 410), (330, 384), (360, 366)]
TAIL_PIVOT = (382, 384)
TAIL_UNDER = [(360, 352), (408, 352), (404, 400), (398, 430), (392, 455), (384, 480), (371, 506), (362, 506),
              (371, 480), (377, 455), (382, 430), (388, 400), (392, 366), (360, 366)]


def despill(a):
    """Magenta-Stich (Schlüsselfarbe) in Pixeln nahe der Transparenz entfernen: Blau über Grün zurücknehmen,
    wo Rot und Blau beide deutlich über Grün liegen."""
    al = a[..., 3] / 255
    near = np.asarray(Image.fromarray(((al < 0.98) * 255).astype(np.uint8)).filter(ImageFilter.MaxFilter(9))) > 0
    r, g, b = a[..., 0], a[..., 1], a[..., 2]
    spill = near & (al > 0) & (r > g + 20) & (b > g + 20) & (b > 0.55 * r)
    out = a.copy()
    out[..., 2] = np.where(spill, g + 0.3 * (b - g) * (0.55 * r / np.maximum(b, 1)), b)
    return out, int(spill.sum())


def poly_mask(shape, pts, blur=0.0):
    m = Image.new("L", (shape[1], shape[0]), 0)
    ImageDraw.Draw(m).polygon([tuple(p) for p in pts], fill=255)
    if blur:
        m = m.filter(ImageFilter.GaussianBlur(blur))
    return np.asarray(m).astype(np.float32) / 255


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    a = np.asarray(Image.open(SRC).convert("RGBA")).astype(np.float32)
    a, n_spill = despill(a)
    h, w, _ = a.shape
    yy, xx = np.mgrid[0:h, 0:w]

    # Masken in Quellauflösung
    xs = np.arange(w, dtype=np.float32)
    rng = np.random.default_rng(7)
    rep = max(1, round(7 * _S))
    tuft = np.repeat(rng.uniform(-1, 1, w // rep + 2), rep)[:w]
    edge = CUT_Y + 5.0 * _S * np.abs(np.sin((xs - W(780, 0)[0]) * np.pi / (9.0 * _S))) + 3.0 * _S * tuft
    body_m = np.clip((edge[None, :] + CUT_FEATHER / 2 - yy) / (CUT_FEATHER / 2), 0, 1)
    tail_out = poly_mask(a.shape, TAIL_POLY, 1.0)
    body_m = body_m * (1 - tail_out)
    tail_m = np.maximum(tail_out, poly_mask(a.shape, TAIL_UNDER, 1.0))
    leg_m = poly_mask(a.shape, LEG_POLY, 1.0) * np.clip((yy - LEG_FEATHER[0]) / (LEG_FEATHER[1] - LEG_FEATHER[0]), 0, 1)

    # Eine gemeinsame Farbebene in Endgröße
    k = HEIGHT_PX / (SOLE - TOP)
    size = (round(w * k), round(h * k))
    ke = size[0] / w                                   # tatsächlicher Faktor (gerundete Größe)

    def down(ch):
        return np.asarray(Image.fromarray(ch.astype(np.float32), "F").resize(size, Image.LANCZOS))

    al_src = a[..., 3] / 255
    A = np.clip(down(al_src), 0, 1)
    P = np.dstack([down(a[..., c] * al_src) for c in range(3)])
    P = np.clip(P, 0, 255 * A[..., None])
    C = np.where(A[..., None] > 0.02, P / np.maximum(A[..., None], 1e-4), 0)
    # Farbe nach außen fortsetzen (für Alpha-Kanten der Teile)
    known = A > 0.02
    for _ in range(6):
        acc = np.zeros_like(C); cnt = np.zeros(A.shape, np.float32)
        for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            kk = np.roll(known, (dy, dx), (0, 1))
            acc += np.roll(C, (dy, dx), (0, 1)) * kk[..., None]; cnt += kk
        grow = (~known) & (cnt > 0)
        C[grow] = acc[grow] / cnt[grow][:, None]
        known |= grow

    def to_dst(p):                                     # Quellkoordinate -> Pixelkoordinate in Endgröße
        return ((p[0] + 0.5) * ke - 0.5, (p[1] + 0.5) * ke - 0.5)

    def part(mask):
        al = np.clip(down(al_src * mask), 0, 1)
        al[al < 1.5 / 255] = 0
        ys, xs_ = np.nonzero(al > 0)
        x0, y0, x1, y1 = xs_.min() - 2, ys.min() - 2, xs_.max() + 3, ys.max() + 3
        rgba = np.dstack([C, al * 255])[y0:y1, x0:x1]
        return Image.fromarray(np.clip(rgba, 0, 255).round().astype(np.uint8), "RGBA"), (x0, y0)

    body, bo = part(body_m)
    leg, lo = part(leg_m)
    tail, to = part(tail_m)
    for name, im in (("badger_body.png", body), ("badger_leg.png", leg), ("badger_tail.png", tail)):
        im.save(OUT / name, optimize=True)

    def rel(p, origin):          # Quellpunkt -> Pixel im Teilbild
        d = to_dst(p)
        return [round(d[0] - origin[0], 2), round(d[1] - origin[1], 2)]

    def from_hip(p):             # Quellpunkt -> relativ zur Hüfte (Endgröße)
        return [round((p[0] - HIP[0]) * ke, 2), round((p[1] - HIP[1]) * ke, 2)]

    rig = {
        "source": "assets/raw/badger_side.png", "scale": round(ke, 5), "height_px": round((SOLE - TOP) * ke, 1),
        "body_pivot": rel(HIP, bo), "leg_pivot": rel(HIP, lo), "tail_pivot": rel(TAIL_PIVOT, to),
        "tail_from_hip": from_hip(TAIL_PIVOT),
        "heel": from_hip(HEEL), "toe": from_hip(TOE), "sole_y": round((SOLE - HIP[1]) * ke, 2),
        "half_foot": round((TOE[0] - HEEL[0]) / 2 * ke, 2),
        "head_top": from_hip(W(965, 111)), "eye": from_hip(W(1004, 206)),
        "body_size": list(body.size), "leg_size": list(leg.size), "tail_size": list(tail.size),
        # oberste Zeile der gezackten Schnittkante im Rumpfbild (für rim_cut im Shader)
        "cut_top_px": round(to_dst((0, CUT_Y - 3.0 * _S))[1] - bo[1], 2),
        "despilled_px": n_spill,
    }
    (OUT / "badger_rig.json").write_text(json.dumps(rig, indent=1))
    print(json.dumps(rig))
    # Vorschau in der Zeichenreihenfolge der Demo: Schalende – fernes Bein (dunkel) – nahes Bein – Rumpf
    pv = Image.new("RGBA", (body.width + 60, body.height + 40), (90, 110, 120, 255))
    hip = (30 + rig["body_pivot"][0], 10 + rig["body_pivot"][1])

    def put(im, pivot, at, dark=1.0):
        if dark != 1.0:
            f = np.asarray(im).astype(np.float32); f[..., :3] *= dark
            im = Image.fromarray(f.astype(np.uint8), "RGBA")
        pv.alpha_composite(im, (round(at[0] - pivot[0]), round(at[1] - pivot[1])))

    tp = (hip[0] + rig["tail_from_hip"][0], hip[1] + rig["tail_from_hip"][1])
    put(tail, rig["tail_pivot"], tp)
    put(leg, rig["leg_pivot"], (hip[0] - 9 * HEIGHT_PX / 168, hip[1]), 0.62)
    put(leg, rig["leg_pivot"], hip)
    pv.alpha_composite(body, (30, 10))
    pv.resize((pv.width * 3, pv.height * 3), Image.LANCZOS).save(OUT / "badger_preview.png")
    ART.mkdir(parents=True, exist_ok=True)
    for f in ("badger_body.png", "badger_leg.png", "badger_tail.png", "badger_rig.json"):
        shutil.copy2(OUT / f, ART / f)


if __name__ == "__main__":
    main()
