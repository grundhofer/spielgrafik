#!/usr/bin/env python3
"""Bereitet die KI-Figurenbögen (assets/raw/walk.png aus Auftrag 2, assets/raw/front.png aus Auftrag 3) für die Demo
auf, ohne Handarbeit:

  1. freistellen (genimg.py hat agy-Bilder schon gekeyt; sonst hier Magenta-Key) und Magenta-Saum entfernen
  2. in Einzelbilder zerlegen: Zusammenhangskomponenten, jeweils der Zelle des Layout-Bogens zugeordnet
     (assets/ref/layouts.json), in der ihr Schwerpunkt liegt
  3. alle Bilder eines Bogens mit demselben Faktor auf die Zielgröße bringen (Figurenhöhe aus scene_ai.json)
  4. ausrichten: Laufbilder und Stehen am Kopf (oberes Viertel) und an der Fußzeile; Drehung und Vorderansicht an
     der Mitte der Sohlen; Vorschub je Laufbild aus dem Standfuß (beste Überdeckung des Sohlenstreifens)
  5. Vorderansicht aus Teilen: fester Körper (Bild "front"), nur Winkarm, Augen bzw. Mund aus den anderen Bildern
     (Differenzmaske nach Ausrichtung am Unterkörper). So flimmert der Körper beim Winken und Blinzeln nicht.
  6. Trockenrand: Pigment sammelt sich innen an der Außenkante (wie bei einer getrockneten Lasur)
  Seit Prüfung 1 vor allem anderen: reglaze.py lasiert beide Bögen in Quellauflösung neu (flache Lasuren je
  Kostümteil, hart begrenzte Schattenlasur, Papierweiß, Trockenränder, Granulation; Augen, Nase, Mund und Knöpfe
  aus dem KI-Bild). Blinzeln: Das Modell malte ein Zwinkern; das Bild "blink" entsteht jetzt aus "front" mit zwei
  gemalten Lidstrichen. Die Winkbilder übernehmen das Gesicht nicht (im Bild "wave_in" war ein Auge zu).

Ausgabe: assets/badger_ai_walk.png, assets/badger_ai_stand.png, assets/badger_ai_meta.json,
         assets/check/badger_ai_frames.png, assets/check/badger_ai_feet.png

    .venv/bin/python styles/aquarell/tools/prep_badger_ai.py [--walk assets/raw/walk.png] [--front assets/raw/front.png]
        [--height 150] [--out assets] [--whole]     (--whole: Vorderansicht als ganze Bilder statt aus Teilen)
        [--no-reglaze]                              (KI-Malerei unverändert, Stand vor Prüfung 1)
        [--dx 0,8,0,0,0,0,0,0]                      (Vorschub je Bildwechsel von Hand, 0 = gemessen;
                                                     Standard: "walk_dx" aus assets/badger_ai_override.json)
"""
import argparse, json, pathlib

import numpy as np
from PIL import Image, ImageDraw

import aqutil
import reglaze
import wc

ROOT = pathlib.Path(__file__).resolve().parents[1]
STAND_ORDER = ["stand", "turn", "front", "wave_raise", "wave_out", "wave_in", "blink", "talk"]


def load_sheet(path):
    rgba = np.asarray(Image.open(path).convert("RGBA")).astype(np.float64)
    rgb, a = rgba[..., :3], rgba[..., 3] / 255.0
    keyed = "genimg"
    if a.min() > 0.99:
        rgb, a = aqutil.key_magenta(rgb)
        keyed = "hier (Magenta)"
    rgb = aqutil.despill(rgb, a)
    return rgb, a, keyed


def split(rgb, a, sheet):
    """Einzelbilder je Layoutzelle: {name: (rgb, alpha)} in Rohbild-Auflösung, beschnitten auf die Figur.
    Kleine Komponenten (Schalende, Krümel) gehen an die Zelle mit dem nächsten Mittelpunkt; berühren sich zwei
    Figuren (Komponente breiter als 1,3 Zellen), wird sie an den Zellgrenzen geteilt."""
    H, W = a.shape
    fx, fy = W / 1536.0, H / 1024.0
    sm = 4
    small = a[::sm, ::sm] > 0.5
    lab, comps = aqutil.components(small)
    cells = sheet["cells"]
    cw = cells[0]["w"] * fx / sm
    cell_area = cells[0]["w"] * cells[0]["h"] * fx * fy / (sm * sm)

    def nearest(x, y):                                            # x, y in Layout-Koordinaten
        return min(range(len(cells)), key=lambda i: (x - (cells[i]["x"] + cells[i]["w"] / 2)) ** 2
                   + (y - (cells[i]["y"] + cells[i]["h"] / 2)) ** 2)

    owner = np.zeros(small.shape, np.int32) - 1                   # Zelle je Pixel (verkleinert)
    split_n = 0
    for c in comps:
        if c["area"] < 0.002 * cell_area:
            continue
        m = lab == c["id"]
        if (c["x1"] - c["x0"] + 1) > 1.3 * cw:
            ys, xs = np.nonzero(m)
            ids = np.array([nearest(x * sm / fx, y * sm / fy) for x, y in zip(xs, ys)])
            owner[ys, xs] = ids
            split_n += 1
        else:
            owner[m] = nearest(c["cx"] * sm / fx, c["cy"] * sm / fy)
    own_up = np.kron(owner, np.ones((sm, sm), np.int32))[:H, :W]
    if own_up.shape != a.shape:
        own_up = np.pad(own_up, ((0, H - own_up.shape[0]), (0, W - own_up.shape[1])), mode="edge")
    frames, missing = {}, []
    for i, cell in enumerate(cells):
        mine = own_up == i
        if not mine.any():
            missing.append(cell["name"])
            continue
        # Randpixel (geringe Deckung) gehören zur nächsten Figur: Maske um die Verkleinerung aufweiten
        m = aqutil.dilate(mine, sm) & (a > 0.01) & ((own_up == i) | (own_up < 0))
        ys, xs = np.nonzero(m)
        y0, y1, x0, x1 = ys.min(), ys.max() + 1, xs.min(), xs.max() + 1
        al = a[y0:y1, x0:x1] * m[y0:y1, x0:x1]
        frames[cell["name"]] = (rgb[y0:y1, x0:x1], al)
    return frames, missing, split_n


def cell_of(sheet, a):
    """Zellgröße des Layouts in Pixeln dieses Bogens (w, h)."""
    H, W = a.shape
    c = sheet["cells"][0]
    return int(round(c["w"] * W / 1536.0)), int(round(c["h"] * H / 1024.0))


def cell_box(sheet, name, a):
    H, W = a.shape
    fx, fy = W / 1536.0, H / 1024.0
    c = next(c for c in sheet["cells"] if c["name"] == name)
    return int(round(c["y"] * fy)), int(round(c["x"] * fx)), int(round(c["h"] * fy)), int(round(c["w"] * fx))


def find_eyes(rgb, a):
    """Die beiden Augen einer Figur in Vorderansicht: sehr dunkle, kleine Flecken im oberen Drittel, als Paar etwa
    auf gleicher Höhe beiderseits der Kopfmitte (die Nase ist größer und liegt tiefer). Gibt Rahmen (x0, y0, x1, y1)."""
    L = reglaze.rgb2lab(np.clip(rgb / 255.0, 0, 1))[..., 0]
    m = a > 0.5
    rows = np.nonzero(m.any(1))[0]
    if len(rows) < 20:
        return None
    top, bot = rows.min(), rows.max()
    h = bot - top + 1
    zone = np.zeros_like(m)
    zone[top:top + int(0.32 * h)] = True
    hx = np.nonzero(m[top:top + h // 4].any(0))[0]
    cx = (hx.min() + hx.max()) / 2
    _, comps = aqutil.components(m & zone & (L < 22))
    comps = [c for c in comps if 0.00015 * h * h <= c["area"] <= 0.004 * h * h
             and (c["x1"] - c["x0"] + 1) < 2.5 * (c["y1"] - c["y0"] + 1) + 3]
    best = None
    for i, p in enumerate(comps):
        for q in comps[i + 1:]:
            l_, r_ = (p, q) if p["cx"] < q["cx"] else (q, p)
            dx = r_["cx"] - l_["cx"]
            if abs(p["cy"] - q["cy"]) > 0.03 * h or not 0.06 * h <= dx <= 0.3 * h:
                continue
            score = abs((l_["cx"] + r_["cx"]) / 2 - cx) + 2 * abs(p["cy"] - q["cy"]) \
                + 0.5 * abs(p["area"] - q["area"]) ** 0.5
            if best is None or score < best[0]:
                best = (score, l_, r_)
    if best is None:
        return None
    return [(c["x0"], c["y0"], c["x1"], c["y1"]) for c in best[1:]]


def fix_eyes(raw, rgb, a, sheet):
    """Vorderbogen: (1) Blinzeln = Bild "front" mit den geschlossenen Augen aus dem Bild "blink" (am Unterkörper
    ausgerichtet), damit sich nur die Augen ändern und beide geschlossen sind; (2) in den Winkbildern die offenen
    Augen aus "front" einsetzen (im Bild "wave_in" hatte das Modell ein Auge geschlossen). Arbeitet in Quellauflösung
    auf dem ganzen Bogen; die Augen werden im unveränderten KI-Bild gesucht."""
    info = {}
    names = [c["name"] for c in sheet["cells"]]
    if "front" not in names:
        return rgb, a, {"error": "kein Bild 'front'"}
    fy0, fx0, ch, cw = cell_box(sheet, "front", a)
    eyes = find_eyes(raw[fy0:fy0 + ch, fx0:fx0 + cw], a[fy0:fy0 + ch, fx0:fx0 + cw])
    if eyes is None:
        return rgb, a, {"error": "im Bild 'front' nicht gefunden, Blinzeln und Winkbilder unverändert"}
    info["front_eyes_px"] = [list(map(int, e)) for e in eyes]
    em = np.zeros((ch, cw))
    for x0, y0, x1, y1 in eyes:
        w_, h_ = x1 - x0 + 1, y1 - y0 + 1
        em[max(0, y0 - int(0.6 * h_)):y1 + int(0.6 * h_) + 1, max(0, x0 - int(0.45 * w_)):x1 + int(0.45 * w_) + 1] = 1
    em = np.clip(wc.blur(em, 2.0) * 1.4, 0, 1)

    # Gesichtsausschnitt (Augenband bis unter die Nase) aus "front" als Vorlage; in jedem anderen Bild die Lage mit
    # der kleinsten Abweichung suchen (der Kopf sitzt nicht überall gleich auf dem Körper, Körperausrichtung genügt nicht)
    ex0 = min(e[0] for e in eyes); ex1 = max(e[2] for e in eyes)
    ey0 = min(e[1] for e in eyes); ey1 = max(e[3] for e in eyes)
    eh = ey1 - ey0 + 1
    ty0, ty1 = max(0, ey0 - eh), min(ch, ey1 + 4 * eh)
    tx0, tx1 = max(0, ex0 - eh), min(cw, ex1 + eh)
    lum = lambda c: reglaze.rgb2lab(np.clip(c / 255.0, 0, 1))[..., 0]
    f_raw = raw[fy0:fy0 + ch, fx0:fx0 + cw]
    tpl = lum(f_raw[ty0:ty1, tx0:tx1])

    def match(o_raw):
        L = lum(o_raw)
        best = None
        for dy in range(-40, 41, 2):
            for dx in range(-40, 41, 2):
                if ty0 + dy < 0 or tx0 + dx < 0 or ty1 + dy > ch or tx1 + dx > cw:
                    continue
                e = np.mean((L[ty0 + dy:ty1 + dy, tx0 + dx:tx1 + dx] - tpl) ** 2)
                if best is None or e < best[0]:
                    best = (e, dx, dy)
        _, bx, by = best
        for dy in range(by - 1, by + 2):
            for dx in range(bx - 1, bx + 2):
                if ty0 + dy < 0 or tx0 + dx < 0 or ty1 + dy > ch or tx1 + dx > cw:
                    continue
                e = np.mean((L[ty0 + dy:ty1 + dy, tx0 + dx:tx1 + dx] - tpl) ** 2)
                if e < best[0]:
                    best = (e, dx, dy)
        return best[1], best[2], float(np.sqrt(best[0]))

    rgb, a = rgb.copy(), a.copy()
    f_rgb, f_a = rgb[fy0:fy0 + ch, fx0:fx0 + cw].copy(), a[fy0:fy0 + ch, fx0:fx0 + cw].copy()
    for n in ("wave_raise", "wave_out", "wave_in", "blink"):
        if n not in names:
            continue
        y0, x0, h_, w_ = cell_box(sheet, n, a)
        if (h_, w_) != (ch, cw):
            continue
        o_rgb = rgb[y0:y0 + h_, x0:x0 + w_]
        dx, dy, err = match(raw[y0:y0 + h_, x0:x0 + w_])      # o[y + dy, x + dx] entspricht front[y, x]
        if n == "blink":
            # geschlossene Augen aus "blink" (auf die Lage in "front" geschoben) in eine Kopie von "front"
            src = np.roll(np.roll(o_rgb, -dy, 0), -dx, 1)
            rgb[y0:y0 + h_, x0:x0 + w_] = f_rgb * (1 - em[..., None]) + src * em[..., None]
            a[y0:y0 + h_, x0:x0 + w_] = f_a
        else:
            # offene Augen aus "front" an die entsprechende Stelle des Winkbilds
            mw = np.roll(np.roll(em, dy, 0), dx, 1)
            src = np.roll(np.roll(f_rgb, dy, 0), dx, 1)
            rgb[y0:y0 + h_, x0:x0 + w_] = o_rgb * (1 - mw[..., None]) + src * mw[..., None]
        info[n] = f"Augen ersetzt (Gesicht um {dx},{dy} px versetzt, Restabweichung L {err:.1f})"
    return rgb, a, info


def to_image(rgb, a):
    return Image.fromarray(np.dstack([np.clip(rgb, 0, 255), np.clip(a, 0, 1) * 255]).astype(np.uint8), "RGBA")


def scaled(frame, s):
    rgb, a = frame
    im = to_image(rgb, a)
    size = (max(1, round(im.width * s)), max(1, round(im.height * s)))
    out = np.asarray(wc.downscale_rgba(im, size) if s < 1 else im.resize(size, Image.LANCZOS)).astype(np.float64)
    return out[..., :3], out[..., 3] / 255.0


def measure(a):
    m = a > 0.5
    ys = np.nonzero(m.any(1))[0]
    top, bot = int(ys.min()), int(ys.max())
    h = bot - top + 1
    head = m[top:top + max(1, h // 4)]
    hx = np.nonzero(head.any(0))[0]
    sole = m[max(top, bot - max(2, int(0.05 * h))):bot + 1]
    sx = np.nonzero(sole.any(0))[0]
    return {"top": top, "bottom": bot, "h": h, "head_x": float((hx.min() + hx.max()) / 2),
            "sole_x": float((sx.min() + sx.max()) / 2), "sole": (int(sx.min()), int(sx.max()))}


def rim(rgb, a, k):
    """Trockenrand: Dichte innen an der Außenkante erhöhen (Pigmentmodell aus wc.py)."""
    if k <= 0:
        return rgb
    lin = wc.s2l(np.clip(rgb / 255.0, 0, 1))
    D = -np.log(np.clip(lin / wc.s2l(wc.PAPER), 1e-4, 1.0))
    D = D * (1 + k * wc.inner_edge(a, 1.6))[..., None]
    return wc.l2s(wc.s2l(wc.PAPER) * np.exp(-D)) * 255.0


class Canvas:
    """Sammelt Bilder mit ihrer Ankerlage (ax, ay in Bildkoordinaten = Position des Figurenankers)."""

    def __init__(self):
        self.items = []

    def add(self, name, rgb, a, ax, ay):
        self.items.append((name, rgb, a, int(round(ax)), int(round(ay))))

    def build(self, margin=4):
        x0 = min(-ax for _, _, a, ax, ay in self.items)
        x1 = max(a.shape[1] - ax for _, _, a, ax, ay in self.items)
        y0 = min(-ay for _, _, a, ax, ay in self.items)
        y1 = max(a.shape[0] - ay for _, _, a, ax, ay in self.items)
        fw, fh = x1 - x0 + 2 * margin, y1 - y0 + 2 * margin
        AX, AY = -x0 + margin, -y0 + margin
        frames = {}
        for name, rgb, a, ax, ay in self.items:
            buf = np.zeros((fh, fw, 4))
            ox, oy = AX - ax, AY - ay
            buf[oy:oy + a.shape[0], ox:ox + a.shape[1], :3] = rgb
            buf[oy:oy + a.shape[0], ox:ox + a.shape[1], 3] = a
            frames[name] = buf
        return frames, (fw, fh), (AX, AY)


# Erwarteter Vorschub je Laufbild: Das Layout zeigt den Walk des 3D-Modells (0,367 m je Zyklus, 8 Bilder) bei
# 409,6 px/m und rund 411 px Figurenhöhe; hält sich das Bildmodell an die Posen, gilt das auch für den Bogen.
EXPECTED_DX_PER_H = 0.367 * 409.6 / 8 / 411.0


def strip(buf, rows=3):
    """Bodenkontakt: die untersten Zeilen der Figur (gehobene Füße liegen höher und fallen heraus)."""
    m = buf[..., 3] > 0.5
    ys = np.nonzero(m.any(1))[0]
    bot = ys.max()
    out = np.zeros_like(m)
    out[bot - rows + 1:bot + 1] = m[bot - rows + 1:bot + 1]
    return out


def ground_segments(buf, rows=3):
    """Bodenkontakt als Liste (x0, x1) zusammenhängender Stücke (Lücken bis 1 px überbrückt)."""
    xs = np.nonzero(strip(buf, rows).any(0))[0]
    if len(xs) == 0:
        return []
    cuts = np.nonzero(np.diff(xs) > 2)[0]
    return list(zip(np.r_[xs[0], xs[cuts + 1]].tolist(), np.r_[xs[cuts], xs[-1]].tolist()))


def advance(buf_a, buf_b, lo, hi, prior):
    """Vorschub von Bild a nach b: Kandidaten sind die Verschiebungen, bei denen eine Ferse (linkes Ende) oder
    Zehe (rechtes Ende) eines Bodenstücks von b auf die von a fällt; der stehende Fuß rollt über Ferse oder Zehe ab,
    eines von beiden bleibt liegen. Gewählt wird der Kandidat mit den meisten Bestätigungen (±1,5 px), bei
    Gleichstand der nächste am Erwartungswert prior. Ohne Kandidaten im Bereich: prior."""
    sa, sb = ground_segments(buf_a), ground_segments(buf_b)
    cands = [ax - bx for (a0, a1) in sa for (b0, b1) in sb for ax, bx in ((a0, b0), (a1, b1))]
    cands = [c for c in cands if lo <= c <= hi]
    if not cands:
        return int(round(prior)), 0, sa, sb
    score = lambda c: sum(abs(c - d) <= 1.5 for d in cands) - abs(c - prior) / max(1.0, abs(prior) + 1)
    best = max(cands, key=score)
    return int(best), sum(abs(best - d) <= 1.5 for d in cands), sa, sb


def part(base, other, region, thr=0.10, grow_px=3):
    """Überträgt aus other nur den Bereich, der sich gegenüber base ändert (innerhalb region)."""
    ab, ao = base[..., 3], other[..., 3]
    diff = np.abs(base[..., :3] * ab[..., None] - other[..., :3] * ao[..., None]).sum(-1) / (3 * 255.0)
    diff = np.maximum(diff, np.abs(ab - ao))
    ch = (wc.blur(diff, 1.2) > thr) & region
    if ch.sum() < 12:
        return None, 0.0
    # nur zusammenhängende Änderungen, die nicht nur aus Randrauschen bestehen
    lab, comps = aqutil.components(ch)
    keep = [c["id"] for c in comps if c["area"] >= max(12, 0.08 * max(cc["area"] for cc in comps))]
    ch = np.isin(lab, keep)
    m = wc.blur(aqutil.dilate(ch, grow_px).astype(np.float64), 1.2)
    m = np.clip(m * 1.6, 0, 1)
    pb = base[..., :3] * ab[..., None]
    po = other[..., :3] * ao[..., None]
    a_ = ab * (1 - m) + ao * m
    p_ = pb * (1 - m[..., None]) + po * m[..., None]
    rgb = np.where(a_[..., None] > 1e-4, p_ / np.maximum(a_[..., None], 1e-4), 0)
    out = np.dstack([rgb, a_])
    return out, float(ch.sum() / max(1, (ab > 0.5).sum()))


def align_body(base, other, h):
    """Verschiebung von other, bei der Beine und Bauch (untere 55 %) am besten auf base liegen."""
    def low(buf):
        m = buf[..., 3] > 0.5
        ys = np.nonzero(m.any(1))[0]
        out = np.zeros_like(m)
        y0 = ys.max() - int(0.55 * h)
        out[y0:] = m[y0:]
        return out
    dx, dy, iou = aqutil.best_shift(low(base), low(other), range(-12, 13), range(-6, 7))
    return dx, dy, iou


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--walk", default=str(ROOT / "assets/raw/walk.png"))
    ap.add_argument("--front", default=str(ROOT / "assets/raw/front.png"))
    ap.add_argument("--out", default=str(ROOT / "assets"))
    ap.add_argument("--height", type=float, default=0, help="Figurenhöhe in px (Standard: scene_ai.json oder 150)")
    ap.add_argument("--rim", type=float, default=0.3)
    ap.add_argument("--whole", action="store_true")
    ap.add_argument("--no-reglaze", action="store_true")
    ap.add_argument("--dx", default="", help="Vorschub je Bildwechsel walk_i -> walk_i+1, 0 = gemessen")
    a = ap.parse_args()
    out = pathlib.Path(a.out)
    (out / "check").mkdir(parents=True, exist_ok=True)
    lay = json.loads((ROOT / "assets/ref/layouts.json").read_text())
    target = a.height
    if not target:
        sj = out / "scene_ai.json"
        target = json.loads(sj.read_text()).get("badger_height", 150) if sj.exists() else 150
    notes, meta = [], {"target_height": target}

    # --- Laufbogen -------------------------------------------------------------------------------------------
    rgb, al, keyed = load_sheet(a.walk)
    if not a.no_reglaze:
        rgb = reglaze.reglaze(rgb, al, cell_of(lay["walk"], al), seed=3)
    fr, miss, nsplit = split(rgb, al, lay["walk"])
    meta["walk_sheet"] = {"size": list(al.shape[::-1]), "keyed": keyed, "missing": miss, "touching_split": nsplit}
    if nsplit:
        notes.append(f"Laufbogen: {nsplit} sich berührende Figuren an den Zellgrenzen geteilt – Schnitt prüfen")
    walk_names = [f"walk_{i}" for i in range(8)]
    if any(n in miss for n in walk_names):
        raise SystemExit(f"Laufbogen unvollständig, fehlende Bilder: {miss} – Bild ansehen, ggf. neu erzeugen")
    hs = [measure(fr[n][1])["h"] for n in walk_names + (["stand"] if "stand" in fr else [])]
    s_walk = target / float(np.median(hs))
    if max(hs) > 1.08 * min(hs):
        notes.append(f"Laufbogen: Figurenhöhen schwanken stark ({min(hs)}–{max(hs)} px roh) – Maßstab der Bilder prüfen")
    meta["walk_sheet"]["scale"] = round(s_walk, 4)
    meta["walk_sheet"]["heights_raw"] = hs
    sc = {n: scaled(fr[n], s_walk) for n in fr}
    for n in sc:
        sc[n] = (rim(sc[n][0], sc[n][1], a.rim), sc[n][1])
    cv = Canvas()
    ms = {n: measure(sc[n][1]) for n in sc}
    for n in walk_names + [x for x in ("stand",) if x in sc]:
        cv.add(n, sc[n][0], sc[n][1], ms[n]["head_x"], ms[n]["bottom"] + 1)

    # --- Vorderansicht ---------------------------------------------------------------------------------------
    front_ok = pathlib.Path(a.front).exists()
    fsc, fms = {}, {}
    if front_ok:
        rgb2, al2, keyed2 = load_sheet(a.front)
        raw2 = rgb2.copy()
        if not a.no_reglaze:
            rgb2 = reglaze.reglaze(rgb2, al2, cell_of(lay["front"], al2), seed=3)
        rgb2, al2, eye_info = fix_eyes(raw2, rgb2, al2, lay["front"])
        meta["eyes"] = eye_info
        if eye_info.get("error"):
            notes.append("Augen: " + eye_info["error"])
        fr2, miss2, nsplit2 = split(rgb2, al2, lay["front"])
        meta["front_sheet"] = {"size": list(al2.shape[::-1]), "keyed": keyed2, "missing": miss2,
                               "touching_split": nsplit2}
        if nsplit2:
            notes.append(f"Vorderbogen: {nsplit2} sich berührende Figuren geteilt – Schnitt prüfen")
        if "front" not in fr2:
            notes.append("Vorderansicht: Bild 'front' fehlt, Bogen nicht verwendet")
            front_ok = False
        else:
            hs2 = [measure(fr2[n][1])["h"] for n in ("front", "blink", "talk") if n in fr2]
            s_front = target / float(np.median(hs2))
            meta["front_sheet"]["scale"] = round(s_front, 4)
            fsc = {n: scaled(fr2[n], s_front) for n in fr2}
            for n in fsc:
                fsc[n] = (rim(fsc[n][0], fsc[n][1], a.rim), fsc[n][1])
            fms = {n: measure(fsc[n][1]) for n in fsc}
    # Drehung und Vorderansicht stehen dort, wo die Sohlen des Stehbilds stehen
    ref_sole = None
    if "stand" in sc:
        ref_sole = ms["stand"]["sole_x"] - ms["stand"]["head_x"]       # relativ zum Anker (Kopf) des Stehbilds
    if "turn" in sc:
        off = ref_sole if ref_sole is not None else 0.0
        cv.add("turn", sc["turn"][0], sc["turn"][1], ms["turn"]["sole_x"] - off, ms["turn"]["bottom"] + 1)
    if front_ok:
        off = ref_sole if ref_sole is not None else 0.0
        for n in fsc:
            cv.add("f_" + n, fsc[n][0], fsc[n][1], fms[n]["sole_x"] - off, fms[n]["bottom"] + 1)
    frames, (FW, FH), (AX, AY) = cv.build()

    # --- Vorschub aus dem Standfuß ---------------------------------------------------------------------------
    e = EXPECTED_DX_PER_H * target
    dxs, votes, used = [], [], []
    for i in range(8):
        dx, v, _, _ = advance(frames[walk_names[i]], frames[walk_names[(i + 1) % 8]], 0.7 * e, 1.45 * e, e)
        dxs.append(dx)
        votes.append(v)
        used.append(dx)
    if 0 in votes and not (a.dx or (ROOT / "assets/badger_ai_override.json").exists()):
        notes.append(f"Vorschub: bei {votes.count(0)} Bildwechsel(n) kein Fußpaar gefunden, Erwartungswert {e:.1f} genommen")
    if abs(sum(used) - 8 * e) > 0.3 * 8 * e:
        notes.append(f"Vorschub je Zyklus {sum(used)} px weicht stark vom Layout ab ({8 * e:.0f} px) – Posen prüfen")
    meta["walk_dx"] = used
    meta["walk_dx_votes"] = votes
    meta["walk_dx_expected"] = round(e, 2)
    if "stand" in frames:
        dx, v, _, _ = advance(frames["walk_7"], frames["stand"], -e, 2 * e, 0.0)
        meta["stand_dx"] = dx
        meta["stand_votes"] = v
    else:
        meta["stand_dx"] = int(round(e))
    dx_src = a.dx
    ovp = ROOT / "assets/badger_ai_override.json"
    if not dx_src and ovp.exists():
        dx_src = ",".join(str(v) for v in json.loads(ovp.read_text()).get("walk_dx", []))
    if dx_src:
        man = [int(v) for v in dx_src.split(",")]
        for i, v in enumerate(man[:8]):
            if v:
                used[i] = v
        meta["walk_dx"] = used
        meta["walk_dx_manual"] = man
    clamped = used

    # --- Vorderansicht aus Teilen ----------------------------------------------------------------------------
    stand_frames = [n for n in ("stand", "turn") if n in frames]
    parts_info = {}
    if front_ok:
        base = frames["f_front"]
        stand_frames.append("f_front")
        bm = base[..., 3] > 0.5
        ys, xs = np.nonzero(bm)
        top, bot = ys.min(), ys.max()
        fh_ = bot - top + 1
        cx = (xs.min() + xs.max()) / 2
        yy, xx = np.mgrid[0:FH, 0:FW]
        hx = np.nonzero(bm[top:top + fh_ // 4].any(0))[0]
        head_box = (yy >= top) & (yy < top + 0.34 * fh_) & (xx >= hx.min() - 4) & (xx <= hx.max() + 4)
        for n in ("wave_raise", "wave_out", "wave_in", "blink", "talk"):
            key = "f_" + n
            if key not in frames:
                parts_info[n] = "fehlt im Bogen"
                continue
            o = frames[key]
            if n == "blink" and "blink" in meta.get("eyes", {}):
                # schon in Quellauflösung aus "front" gebaut: nur die Augen unterscheiden sich, ganzes Bild nehmen
                parts_info[n] = "ganzes Bild: 'front' mit geschlossenen Augen aus 'blink' (siehe fix_eyes)"
                stand_frames.append(key)
                continue
            dx, dy, iou = align_body(base, o, fh_)
            o = np.roll(np.roll(o, dy, 0), dx, 1)
            if a.whole:
                frames[key] = o
                parts_info[n] = f"ganzes Bild (Versatz {dx},{dy}, IoU Unterkörper {iou:.2f})"
                stand_frames.append(key)
                continue
            if n.startswith("wave"):
                da = np.abs(o[..., 3] - base[..., 3])
                left, right = da[:, :int(cx)].sum(), da[:, int(cx):].sum()
                side = (xx >= cx - 0.08 * fh_) if right >= left else (xx <= cx + 0.08 * fh_)
                region = side & (yy < top + 0.8 * fh_)
                res, share = part(base, o, region, thr=0.10, grow_px=4)
            else:
                res, share = part(base, o, head_box, thr=0.08, grow_px=2)
            if res is None or share < 0.002:
                parts_info[n] = f"keine Änderung gefunden (Anteil {share:.3f}) – nicht verwendet"
                del frames[key]
                continue
            frames[key] = res
            parts_info[n] = f"Teil übertragen: {share:.1%} der Figur (Versatz {dx},{dy}, IoU Unterkörper {iou:.2f})"
            stand_frames.append(key)
    meta["parts"] = parts_info

    # --- Bögen schreiben -------------------------------------------------------------------------------------
    def sheet(names, path):
        im = Image.new("RGBA", (FW * len(names), FH), (0, 0, 0, 0))
        for i, n in enumerate(names):
            im.paste(to_image(frames[n][..., :3], frames[n][..., 3]), (i * FW, 0))
        im.save(path)

    sheet(walk_names, out / "badger_ai_walk.png")
    stand_names = [n for n in ["stand", "turn"] + ["f_" + x for x in STAND_ORDER[2:]] if n in stand_frames]
    sheet(stand_names, out / "badger_ai_stand.png")
    meta.update({"frame": [FW, FH], "anchor": [AX, AY],
                 "clips": {"walk": {"file": "badger_ai_walk.png", "frames": 8, "names": walk_names},
                           "stand": {"file": "badger_ai_stand.png", "frames": len(stand_names),
                                     "names": [n.replace("f_", "") for n in stand_names]}},
                 "notes": notes})
    (out / "badger_ai_meta.json").write_text(json.dumps(meta, indent=1, ensure_ascii=False))

    # --- Prüfbilder ------------------------------------------------------------------------------------------
    allnames = walk_names + stand_names
    chk = Image.new("RGB", (FW * len(allnames), FH * 2 + 16), (244, 239, 228))
    d = ImageDraw.Draw(chk)
    d.rectangle([0, FH + 16, chk.width, chk.height], fill=(40, 40, 48))
    for i, n in enumerate(allnames):
        im = to_image(frames[n][..., :3], frames[n][..., 3])
        for row in (0, 1):
            chk.paste(im, (i * FW, row * (FH + 16)), im)
        d.text((i * FW + 3, FH + 2), n.replace("f_", ""), fill=(60, 60, 60))
    for row in (0, 1):
        y = row * (FH + 16) + AY
        d.line([(0, y), (chk.width, y)], fill=(255, 0, 0))
    for i in range(len(allnames)):
        d.line([(i * FW + AX, 0), (i * FW + AX, chk.height)], fill=(0, 120, 255))
    chk.save(out / "check/badger_ai_frames.png")
    # Füße: Laufbilder nacheinander mit Vorschub, Sohlenstreifen übereinander (Standfuß muss stehen bleiben)
    feet = Image.new("RGB", (FW + sum(clamped) + 40, FH), (255, 255, 255))
    x = 20
    for i, n in enumerate(walk_names + ["walk_0"]):
        im = to_image(frames[n][..., :3], frames[n][..., 3] * 0.35)
        feet.paste(im, (x, 0), im)
        if i < 8:
            x += clamped[i]
    ImageDraw.Draw(feet).line([(0, AY), (feet.width, AY)], fill=(255, 0, 0))
    feet.save(out / "check/badger_ai_feet.png")
    print(f"ok: Bild {FW}x{FH}, Anker {AX},{AY}, Höhe {target:.0f} px, Vorschub {clamped} (Bestätigungen "
          f"{meta['walk_dx_votes']}, erwartet {e:.1f}), "
          f"Stehen +{meta['stand_dx']}")
    for n, t in parts_info.items():
        print(f"   {n:10s} {t}")
    for t in notes:
        print("   HINWEIS:", t)


if __name__ == "__main__":
    main()
