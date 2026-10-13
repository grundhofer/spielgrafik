#!/usr/bin/env python3
"""Zerlegt das KI-Porträt in Rig-Ebenen und schreibt die Godot-Szene demo/portrait.tscn.

    .venv/bin/python styles/lebendes-portraet/tools/prep.py
    .venv/bin/python styles/lebendes-portraet/tools/prep.py --portrait X.png --faces Y.png   (z. B. Platzhalter)

Eingang (Quellraster, 1024×1024):
  assets/raw/portrait.png  Porträt, Augen offen, Mund zu (echter Alphakanal)
  assets/raw/faces.png     KI-Bearbeitung desselben Bildes: Augen zu, Mund offen
Ausgang:
  assets/layer_*.png       Ebenen in Anzeigegröße (Körper, Kopf, Kopf-Bearbeitung, Schal)
  demo/art/*.png           dieselben Ebenen für Godot
  demo/portrait.tscn       Skeleton2D mit Knochen, drei Polygon2D mit Gitter und Gewichten, Kopf-Shader-Daten
  assets/rig.json          Messwerte (Rechtecke, Kurven, Knochen) für Prüfskripte
  assets/rig_debug.png     Prüfbild: Ebenen, Gitter, Knochen, Augen- und Mundbereiche

Alle Korrekturen gehören in tools/prep_config.json, nie in erzeugte Dateien.
"""
import argparse, json, math, pathlib, sys

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import imgops as ops  # noqa: E402

HERE = pathlib.Path(__file__).resolve().parent.parent
DEMO = HERE / "demo"
ART = DEMO / "art"
CFG = json.loads((HERE / "tools" / "prep_config.json").read_text())


def log(*a):
    print(*a, flush=True)


# ---------------------------------------------------------------- Laden und Ausrichten
def load_rgba(p, size=1024):
    im = Image.open(p).convert("RGBA")
    if im.size != (size, size):
        # Codex liefert z. B. 1254×1254 statt 1024×1024: auf das Quellraster bringen (Konfiguration in 1024er-Pixeln)
        im = im.resize((size, size), Image.LANCZOS)
    a = np.asarray(im, np.float32) / 255.0
    al = a[..., 3]
    al[al >= 250 / 255] = 1.0
    al[al <= 2 / 255] = 0.0
    return a


def gray(a):
    return a[..., 0] * 0.299 + a[..., 1] * 0.587 + a[..., 2] * 0.114


def warp(img_arr, s, tx, ty, size):
    """Ausgabe(p) = Eingabe(p / s - t/s): Maßstab s um den Ursprung, dann verschieben um t."""
    im = Image.fromarray(np.clip(img_arr * 255 + 0.5, 0, 255).astype(np.uint8), "RGBA")
    data = (1 / s, 0, -tx / s, 0, 1 / s, -ty / s)
    out = im.transform(size, Image.AFFINE, data, resample=Image.BICUBIC)
    return np.asarray(out, np.float32) / 255.0


def align(A, B, exclude):
    """Richtet B auf A aus (Maßstab + Verschiebung), gemessen außerhalb der Gesichtsänderungen."""
    h, w = A.shape[:2]
    if B.shape[:2] != (h, w):
        B = np.asarray(Image.fromarray((B * 255).astype(np.uint8), "RGBA").resize((w, h), Image.LANCZOS),
                       np.float32) / 255.0
    aA, aB = A[..., 3] > 0.5, B[..., 3] > 0.5
    ys, xs = np.nonzero(aA)
    cA = np.array([xs.mean(), ys.mean()])
    ys, xs = np.nonzero(aB)
    cB = np.array([xs.mean(), ys.mean()])
    s0 = math.sqrt(aA.sum() / max(1, aB.sum()))
    t0 = cA - cB * s0
    gA = gray(A) * A[..., 3]
    valid = (A[..., 3] > 0.5) & ~exclude

    def cost(s, tx, ty, step=2):
        Bw = warp(B, s, tx, ty, (w, h))
        d = np.abs(gray(Bw) * Bw[..., 3] - gA)
        return float(d[::step, ::step][valid[::step, ::step]].mean())

    best = (cost(s0, *t0), s0, t0[0], t0[1])
    for rng, st, step in ((4.0, 1.0, 3), (1.0, 0.25, 2)):
        _, s_b, x_b, y_b = best
        for ds in (-0.004, -0.002, 0.0, 0.002, 0.004) if rng > 2 else (-0.001, 0.0, 0.001):
            for dx in np.arange(-rng, rng + 1e-6, st):
                for dy in np.arange(-rng, rng + 1e-6, st):
                    s = s_b + ds
                    # Maßstabsänderung um die Bildmitte, damit dx/dy unabhängig bleiben
                    tx = x_b + dx - ds * cA[0]
                    ty = y_b + dy - ds * cA[1]
                    c = cost(s, tx, ty, step)
                    if c < best[0]:
                        best = (c, s, tx, ty)
    c, s, tx, ty = best
    log(f"Ausrichtung faces → portrait: Maßstab {s:.4f}, Versatz {tx:.2f}/{ty:.2f}, Restfehler {c:.4f}")
    return warp(B, s, tx, ty, (w, h)), {"scale": s, "tx": tx, "ty": ty, "residual": c}


# ---------------------------------------------------------------- Zerlegen
def hsv(a):
    im = Image.fromarray(np.clip(a[..., :3] * 255, 0, 255).astype(np.uint8), "RGB").convert("HSV")
    return np.asarray(im, np.float32) / 255.0


def segment(A):
    h, w = A.shape[:2]
    alpha = A[..., 3] > 0.5
    H = hsv(A)
    hue, sat, val = H[..., 0], H[..., 1], H[..., 2]
    c = CFG["scarf_color"]
    # Rot gegen Grün statt Farbton: erfasst auch das orange angestrahlte und das violett beschattete Schalende,
    # nicht aber Riemen, Paket und Fell (r − g dort ≤ 0,25)
    red = ((A[..., 0] - A[..., 1]) > c["rg_min"]) & alpha
    red[:c.get("y_min", 0)] = False  # Mützenband und Ohren liegen darüber
    red = ops.open_(red, 1)
    comps = ops.components(red, min_area=400)
    log("rote Komponenten:", [a for a, _ in comps[:6]])
    scarf = np.zeros_like(alpha)
    for area, m in comps:
        if area >= CFG["scarf_min_area"]:
            scarf |= m
    scarf = ops.fill_holes(ops.close(scarf, 4))
    # Kontur des Schals gehört zum Schal, aber nur dunkle Pixel (sonst nimmt die Schalebene Fellspitzen mit)
    dark = (val < CFG["outline_val_max"]) & alpha
    scarf = scarf | (ops.dilate(scarf, CFG["scarf_outline_px"]) & dark)
    rest = alpha & ~scarf
    comps = ops.components(rest, min_area=20)
    # Kopf: Komponente, die die Mützenmitte enthält
    ys, xs = np.nonzero(alpha)
    top = ys.min()
    cx = int(np.median(xs[ys < top + 40]))
    seed_y = top + 25
    head = np.zeros_like(alpha)
    body = np.zeros_like(alpha)
    sy = np.nonzero(scarf)[0]
    scarf_mid = (sy.min() + sy.max()) / 2 if len(sy) else h / 2
    for area, m in comps:
        if m[seed_y, cx] or m[seed_y - 5:seed_y + 5, cx - 5:cx + 5].any():
            head |= m
        else:
            cy = np.nonzero(m)[0].mean()
            (head if cy < scarf_mid - (sy.max() - sy.min()) * 0.25 else body).__ior__(m)
    return {"alpha": alpha, "scarf": scarf, "head": head, "body": body, "cx": cx}


def split_tail(seg):
    """Schalende (hängt frei) vom Wickel trennen: Zeile, ab der der Schal schmal wird."""
    scarf = seg["scarf"]
    rows = scarf.sum(1)
    ymax_w = int(np.argmax(rows))
    if CFG.get("tail_split"):
        split = int(CFG["tail_split"])
    else:
        split = ymax_w
        while split < len(rows) - 1 and rows[split] > CFG["tail_width_ratio"] * rows[ymax_w]:
            split += 1
    tail = scarf.copy()
    tail[:split] = False
    comps = ops.components(tail, min_area=200)
    tail = comps[0][1] if comps else tail
    ys, xs = np.nonzero(tail)
    info = {"split_y": split, "x0": int(xs.min()), "x1": int(xs.max()), "y1": int(ys.max())} if len(ys) else None
    return tail, info


def fill_under(rgba, known, region, mode="pullpush"):
    """Füllt `region` in rgba (HxWx4) aus den Pixeln `known`. Alpha in region = 1."""
    out = rgba.copy()
    if mode == "rows":
        # zeilenweise linear zwischen linkem und rechtem Rand interpolieren (für schmale senkrechte Lücken)
        est = ops.pull_push(rgba[..., :3], known)
        ys = np.nonzero(region.any(1))[0]
        for y in ys:
            row = region[y]
            xs = np.nonzero(row)[0]
            # zusammenhängende Läufe
            runs = np.split(xs, np.nonzero(np.diff(xs) > 1)[0] + 1)
            for r in runs:
                x0, x1 = r[0] - 1, r[-1] + 1
                if x0 >= 0 and x1 < row.size and known[y, x0] and known[y, x1]:
                    t = (r - x0) / (x1 - x0)
                    out[y, r, :3] = rgba[y, x0, :3] * (1 - t)[:, None] + rgba[y, x1, :3] * t[:, None]
                else:
                    out[y, r, :3] = est[y, r]
    elif mode == "down":
        # spaltenweise nach unten fortsetzen (Fellstreifen laufen senkrecht), danach leicht glätten
        est = ops.pull_push(rgba[..., :3], known)
        h, w = region.shape
        for x in np.nonzero(region.any(0))[0]:
            col = region[:, x]
            ys = np.nonzero(col)[0]
            ky = np.nonzero(known[:, x])[0]
            for y in ys:
                above = ky[ky < y]
                if len(above):
                    y0 = above.max()
                    src = rgba[max(0, y0 - 3):y0 + 1, x, :3].mean(0)
                    t = min(1.0, (y - y0) / 40.0)
                    out[y, x, :3] = src * (1 - t) + est[y, x] * t
                else:
                    out[y, x, :3] = est[y, x]
    else:
        est = ops.pull_push(rgba[..., :3], known)
        out[region, :3] = est[region]
    out[region, 3] = 1.0
    return out


# ---------------------------------------------------------------- Gesicht
def face_parts(A, B, head):
    d = np.abs(A[..., :3] - B[..., :3]).sum(-1)
    diff = (d > CFG["diff_thresh"]) & head & (A[..., 3] > 0.5) & (B[..., 3] > 0.5)
    diff = ops.open_(diff, 1)
    diff = ops.close(diff, 3)
    comps = ops.components(diff, min_area=CFG["diff_min_area"])
    log("Gesichtsänderungen (Flächen):", [a for a, _ in comps[:8]])
    ys, xs = np.nonzero(head)
    hy0, hy1, hx0, hx1 = ys.min(), ys.max(), xs.min(), xs.max()
    parts = {}
    if CFG.get("eye_rects") and CFG.get("mouth_rect"):
        rects = {"eye_l": CFG["eye_rects"][0], "eye_r": CFG["eye_rects"][1], "mouth": CFG["mouth_rect"]}
    else:
        cand = []
        for area, m in comps:
            yy, xx = np.nonzero(m)
            cand.append({"area": area, "cx": xx.mean(), "cy": yy.mean(), "box": [xx.min(), yy.min(), xx.max(), yy.max()], "m": m})
        upper = [c for c in cand if c["cy"] < hy0 + (hy1 - hy0) * CFG["eye_band"]]
        upper.sort(key=lambda c: -c["area"])
        eyes = sorted(upper[:2], key=lambda c: c["cx"])
        if len(eyes) < 2:
            sys.exit("Augen nicht gefunden – eye_rects in prep_config.json setzen")
        ey = max(e["box"][3] for e in eyes)
        lower = [c for c in cand if c["cy"] > ey and abs(c["cx"] - (eyes[0]["cx"] + eyes[1]["cx"]) / 2) < (hx1 - hx0) * 0.25]
        lower.sort(key=lambda c: -c["area"])
        if not lower:
            sys.exit("Mund nicht gefunden – mouth_rect in prep_config.json setzen")
        pad = CFG["part_pad"]
        rects = {}
        for k, c in (("eye_l", eyes[0]), ("eye_r", eyes[1]), ("mouth", lower[0])):
            x0, y0, x1, y1 = c["box"]
            rects[k] = [int(x0 - pad), int(y0 - pad), int(x1 + pad), int(y1 + pad)]
    for k, r in rects.items():
        x0, y0, x1, y1 = r
        m = np.zeros_like(diff)
        m[y0:y1 + 1, x0:x1 + 1] = diff[y0:y1 + 1, x0:x1 + 1]
        parts[k] = {"rect": r, "mask": m}
    return parts, diff


def eye_curves(A, B, part):
    """Je Spalte: obere Lidkante (offen) und untere Kante der Augenöffnung, in Quellpixeln (float, nan = kein Auge)."""
    x0, y0, x1, y1 = part["rect"]
    m = part["mask"]
    top = np.full(x1 - x0 + 1, np.nan)
    bot = np.full(x1 - x0 + 1, np.nan)
    for i, x in enumerate(range(x0, x1 + 1)):
        ys = np.nonzero(m[y0:y1 + 1, x])[0]
        if len(ys) >= 2:
            top[i] = y0 + ys.min()
            bot[i] = y0 + ys.max()
    return top, bot


def mouth_curves(A, B, part):
    """Je Spalte: Oberkante des offenen Mundinnenraums (u) und seine Höhe (h) in der Bearbeitung B.

    Innenraum = in der Bearbeitung geänderte Pixel mit Mundfarben (dunkles Rotbraun, rosa Zunge: rötlich und
    gesättigt; Fell ist ungesättigt, Linien sind fast schwarz). Lippenlinien werden durch Schließen überbrückt,
    die Zunge über das Füllen von Löchern aufgenommen."""
    x0, y0, x1, y1 = part["rect"]
    Hb = hsv(B)
    hue, sat, val = Hb[..., 0], Hb[..., 1], Hb[..., 2]
    col = ((hue < 0.09) | (hue > 0.88)) & (sat > CFG["mouth_sat_min"]) & (val > 0.12) & (val < 0.98)
    inner = col & part["mask"]
    comps = ops.components(ops.open_(inner, 1), min_area=30)
    if not comps:
        sys.exit("Mundinnenraum nicht gefunden")
    inner = ops.fill_holes(ops.close(comps[0][1], 3))
    u = np.full(x1 - x0 + 1, np.nan)
    hh = np.zeros(x1 - x0 + 1)
    for i, x in enumerate(range(x0, x1 + 1)):
        ys = np.nonzero(inner[y0:y1 + 1, x])[0]
        if len(ys):
            u[i] = y0 + ys.min()
            hh[i] = ys.max() - ys.min() + 1
    return u, hh, inner


def smooth_curve(v, r=2):
    out = v.copy()
    for i in range(len(v)):
        seg = v[max(0, i - r):i + r + 1]
        seg = seg[~np.isnan(seg)]
        if not np.isnan(v[i]) and len(seg):
            out[i] = seg.mean()
    return out


# ---------------------------------------------------------------- Ausgabe
def to_img(a):
    return Image.fromarray(np.clip(a * 255 + 0.5, 0, 255).astype(np.uint8), "RGBA")


def scaled_layer(rgba, mask, k, pad=2):
    """Ebene maskieren, auf Anzeigegröße verkleinern, auf Begrenzungsrahmen zuschneiden."""
    a = rgba.copy()
    a[..., 3] *= mask.astype(np.float32) if mask.dtype == bool else mask
    # Vormultipliziert verkleinern, damit transparente Pixel keine Farbe einschleppen
    pm = a.copy()
    pm[..., :3] *= pm[..., 3:4]
    h, w = a.shape[:2]
    W, H = round(w * k), round(h * k)
    small = np.asarray(Image.fromarray(np.clip(pm * 255 + 0.5, 0, 255).astype(np.uint8), "RGBA").resize((W, H), Image.LANCZOS), np.float32) / 255.0
    al = small[..., 3:4]
    rgb = np.where(al > 1e-3, small[..., :3] / np.maximum(al, 1e-3), 0)
    # Farbe in transparente Randpixel fortsetzen (lineare Filterung in Godot zieht sonst dunkle Säume)
    known = al[..., 0] > 0.02
    if known.any():
        est = ops.pull_push(np.clip(rgb, 0, 1), known, levels=6)
        rgb = np.where(known[..., None], rgb, est)
    out = np.concatenate([np.clip(rgb, 0, 1), np.clip(al, 0, 1)], -1)
    ys, xs = np.nonzero(out[..., 3] > 0.004)
    x0, y0 = max(0, xs.min() - pad), max(0, ys.min() - pad)
    x1, y1 = min(W, xs.max() + pad + 1), min(H, ys.max() + pad + 1)
    return out[y0:y1, x0:x1], (int(x0), int(y0))


def grid_mesh(x0, y0, w, h, g):
    nx = max(2, int(math.ceil(w / g)) + 1)
    ny = max(2, int(math.ceil(h / g)) + 1)
    xs = np.linspace(x0, x0 + w, nx)
    ys = np.linspace(y0, y0 + h, ny)
    verts = [(float(x), float(y)) for y in ys for x in xs]
    tris = []
    for j in range(ny - 1):
        for i in range(nx - 1):
            a = j * nx + i
            tris.append((a, a + 1, a + nx + 1))
            tris.append((a, a + nx + 1, a + nx))
    return verts, tris


def smoothstep(e0, e1, x):
    t = np.clip((x - e0) / (e1 - e0), 0, 1)
    return t * t * (3 - 2 * t)


def fmt(arr, nd=2):
    return ", ".join(f"{v:.{nd}f}".rstrip("0").rstrip(".") if isinstance(v, float) else str(v) for v in arr)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--portrait", default=str(HERE / "assets/raw/portrait.png"))
    ap.add_argument("--faces", default=str(HERE / "assets/raw/faces.png"))
    a = ap.parse_args()
    k = CFG["scale"]
    A = load_rgba(a.portrait)
    Braw = load_rgba(a.faces)
    log(f"Porträt {A.shape[1]}×{A.shape[0]}, Bearbeitung {Braw.shape[1]}×{Braw.shape[0]}")

    seg = segment(A)
    tail, tinfo = split_tail(seg)
    log("Schalende:", tinfo)

    # grobe Gesichtszone für die Ausrichtung ausnehmen (mittleres Drittel des Kopfes)
    ys, xs = np.nonzero(seg["head"])
    ex = np.zeros_like(seg["head"])
    hy0, hy1, hx0, hx1 = ys.min(), ys.max(), xs.min(), xs.max()
    ex[int(hy0 + (hy1 - hy0) * 0.3):hy1 + 60, int(hx0 + (hx1 - hx0) * 0.15):int(hx1 - (hx1 - hx0) * 0.15)] = True
    B, al_info = align(A, Braw, ex)

    parts, diff = face_parts(A, B, seg["head"])
    for kk, p in parts.items():
        log(f"{kk}: Rechteck {p['rect']}, {int(p['mask'].sum())} geänderte Pixel")

    # ---------- Ebenen in Quellauflösung
    alpha = seg["alpha"]
    scarf = seg["scarf"]
    head = seg["head"]
    body = seg["body"]
    # Kopf unter dem Schal fortsetzen (Kinn/Hals), damit Neigen keine Lücke öffnet
    ext = ops.dilate(head, CFG["head_ext_px"]) & scarf & ~head
    # nur dort, wo der Schal seitlich weit genug übersteht: sonst schaut die Fortsetzung beim Drehen
    # und Neigen seitlich unter dem Schalende hervor
    side = CFG["head_ext_side_px"]
    for y in np.nonzero(ext.any(1))[0]:
        xs = np.nonzero(scarf[y])[0]
        if len(xs) == 0:
            ext[y] = False
            continue
        ext[y, :xs.min() + side] = False
        ext[y, xs.max() - side + 1:] = False
    # Randstreifen des Kopfes am Schal (Kontur) ebenfalls neu füllen: die Kontur trägt die Schalebene,
    # sonst wandert beim Drehen eine dunkle Linie oder Streifen über dem Schal mit
    band = head & ops.dilate(scarf, CFG["head_band_px"])
    head_rgba = fill_under(A, head & ~band, ext | band, mode="pullpush")
    head_mask = head | ext
    # Kopf-Bearbeitung (B) im selben Raum; außerhalb des Kopfes A
    headB = B.copy()
    headB[..., 3] = A[..., 3]
    headB[~head] = head_rgba[~head]
    # Körper unter dem Schal füllen (unter dem Wickel und dem Schalende)
    under = scarf & ~head
    body_known = body.copy()
    body_rgba = A.copy()
    tail_reg = under & tail
    wrap_reg = under & ~tail
    body_rgba = fill_under(body_rgba, body_known, tail_reg | ops.dilate(tail_reg, 2) & ~body_known, mode="rows")
    body_rgba = fill_under(body_rgba, body_known | tail_reg, wrap_reg, mode="pullpush")
    body_mask = body | under
    scarf_rgba = A.copy()

    # ---------- Anzeigegröße
    ART.mkdir(parents=True, exist_ok=True)
    layers = {}
    for name, rgba, m in (("body", body_rgba, body_mask), ("head", head_rgba, head_mask), ("scarf", scarf_rgba, scarf)):
        img, off = scaled_layer(rgba, m, k)
        layers[name] = {"img": img, "off": off}
        to_img(img).save(ART / f"{name}.png")
        to_img(img).save(HERE / "assets" / f"layer_{name}.png")
    # Bearbeitung mit genau demselben Zuschnitt wie der Kopf
    hb, offb = scaled_layer(headB, head_mask, k)
    assert offb == layers["head"]["off"] and hb.shape == layers["head"]["img"].shape, (offb, layers["head"]["off"])
    to_img(hb).save(ART / "head_faces.png")
    to_img(hb).save(HERE / "assets" / "layer_head_faces.png")
    hox, hoy = layers["head"]["off"]
    hw = layers["head"]["img"].shape[1]

    # ---------- Kurven für den Kopf-Shader (in Pixeln der Kopftextur, je Anzeigespalte interpoliert)
    n = CFG["facecols"]
    if hw > n:
        sys.exit(f"Kopftextur {hw} px breit, facecols {n} zu klein")
    eyecols = np.full((n, 4), -1.0, np.float32)
    mouthcols = np.full((n, 4), -1.0, np.float32)
    mouthcols[:, 1] = 0.0

    def sample(curve, x0, xi):
        """Quellkurve (ab Quellspalte x0) an der Anzeigespalte xi lesen; nan außerhalb."""
        xs = (xi + hox + 0.5) / k - 0.5 - x0
        i0 = int(math.floor(xs))
        if i0 < 0 or i0 + 1 >= len(curve):
            return float("nan")
        a, b = curve[i0], curve[i0 + 1]
        if np.isnan(a) or np.isnan(b):
            return float("nan")
        t = xs - i0
        return float(a * (1 - t) + b * t)

    rig_face = {}
    lower_px_eye = []
    Hb = hsv(B)
    for kk in ("eye_l", "eye_r"):
        top, bot = eye_curves(A, B, parts[kk])
        top, bot = smooth_curve(top), smooth_curve(bot)
        # Lidlinie der KI-Fassung (geschlossen): Mitte der sehr dunklen Pixel je Spalte
        x0, y0, x1, y1 = parts[kk]["rect"]
        arc = np.full(len(top), np.nan)
        for i in range(len(top)):
            if np.isnan(top[i]):
                continue
            ya, yb = int(top[i]) - 4, int(bot[i]) + 4
            col = Hb[ya:yb, x0 + i, 2]
            ys = np.nonzero(col < CFG["arc_val_max"])[0]
            if len(ys):
                arc[i] = ya + float(np.median(ys))
        arc = smooth_curve(np.where(np.isnan(arc) & ~np.isnan(bot), bot, arc), 3)
        arc = np.minimum(np.maximum(arc, top + 2), bot)
        # innere Öffnung (ohne die dunkle Augenkontur): je Spalte die Länge des sehr dunklen Laufs ab oberer
        # bzw. unterer Kante; Median über die Spalten (einzelne Spalten mit Pupille an der Kontur zählen nicht)
        Va = hsv(A)[..., 2]
        ups, los = [], []
        for i in range(len(top)):
            if np.isnan(top[i]):
                continue
            col = Va[int(top[i]):int(bot[i]) + 1, x0 + i]
            if len(col) < 6:
                continue
            dark = col < CFG["eye_outline_val"]
            n_up = int(np.argmax(~dark)) if (~dark).any() else len(col)
            n_lo = int(np.argmax(~dark[::-1])) if (~dark).any() else len(col)
            ups.append(n_up)
            los.append(n_lo)
        t_up = float(np.median(ups)) if ups else 2.0
        t_lo = float(np.median(los)) if los else 2.0
        top_in = np.where(np.isnan(top), np.nan, np.minimum(top + t_up, (top + bot) / 2))
        bot_in = np.where(np.isnan(top), np.nan, np.maximum(bot - t_lo, (top + bot) / 2))
        # Spalten ohne helle Pixel zwischen den Konturen (Augenwinkel: nur Kontur) haben keine Öffnung
        has = np.zeros(len(top), bool)
        for i in range(len(top)):
            if not np.isnan(top_in[i]):
                col = Va[int(np.ceil(top_in[i])):int(bot_in[i]) + 1, x0 + i]
                has[i] = (col > 0.5).sum() >= 2
        idx = np.nonzero(has)[0]
        if len(idx):
            has[:] = False
            has[idx.min() + 1:idx.max()] = True
        bot_in = np.where(has, bot_in, np.nan)
        log(f"{kk}: Konturstärke oben {t_up:.1f}, unten {t_lo:.1f} Quellpixel")
        lower_px_eye.append(t_lo * k)
        for xi in range(hw):
            t_, b_, a_ = sample(top, x0, xi), sample(bot, x0, xi), sample(arc, x0, xi)
            ti, bi = sample(top_in, x0, xi), sample(bot_in, x0, xi)
            if not np.isnan(t_):
                ti = t_ + 2 / k if np.isnan(ti) else ti
                # w < 0: Spalte ohne innere Öffnung (Augenwinkel), dort kein Blick
                w_ = ti * k - hoy if not np.isnan(bi) else -(ti * k - hoy) - 1.0
                eyecols[xi] = [t_ * k - hoy, b_ * k - hoy, a_ * k - hoy, w_]
        rig_face[kk] = {"rect": parts[kk]["rect"], "top": [None if np.isnan(v) else round(float(v), 1) for v in top],
                        "bot": [None if np.isnan(v) else round(float(v), 1) for v in bot],
                        "arc": [None if np.isnan(v) else round(float(v), 1) for v in arc]}
    u, hh, inner = mouth_curves(A, B, parts["mouth"])
    u = smooth_curve(u)
    hh = np.convolve(hh, np.ones(3) / 3, mode="same")
    hh_n = np.where(hh >= 1, hh, np.nan)
    u = np.where(np.isnan(hh_n), np.nan, u)
    x0, y0m, x1m, y1m = parts["mouth"]["rect"]
    # Lachlinie des Porträts: dunkle Linienpixel im Mundbereich ohne die Nase (Nase = Kern, der eine Erosion
    # übersteht). Je Spalte die Unterkante des untersten Laufs; Linienstärke als Median.
    Va = hsv(A)[..., 2]
    darkA = np.zeros_like(seg["head"])
    darkA[y0m:y1m + 1, x0:x1m + 1] = Va[y0m:y1m + 1, x0:x1m + 1] < CFG["lip_val_max"]
    core = ops.components(ops.erode(darkA, 3), min_area=20)
    nose = ops.dilate(core[0][1], 5) if core else np.zeros_like(darkA)
    line = darkA & ~nose
    wb = np.full(len(u), np.nan)
    runs = []
    for i in range(len(u)):
        if np.isnan(u[i]):
            continue
        lim = int(u[i] + hh[i])
        ys = np.nonzero(line[y0m:lim, x0 + i])[0]
        if len(ys):
            yb_ = ys.max()
            n = 1
            while n < len(ys) and ys[-1 - n] == yb_ - n:
                n += 1
            wb[i] = y0m + yb_
            if n <= 8:
                runs.append(n)
    lw = float(np.median(runs)) if runs else 3.0
    # Ausreißer (Nasenkontur, Philtrum) verwerfen: die Lachlinie liegt in diesem Bild unter der Oberkante des
    # offenen Innenraums; danach gleitender Median und Lücken linear füllen
    wb = np.where(wb >= u - CFG["lip_above_u_max"], wb, np.nan)
    med = wb.copy()
    for i in range(len(wb)):
        seg_ = wb[max(0, i - 4):i + 5]
        seg_ = seg_[~np.isnan(seg_)]
        med[i] = np.median(seg_) if len(seg_) else np.nan
    wb = np.where(np.abs(wb - med) > 4, np.nan, wb)
    ok = ~np.isnan(wb)
    if ok.sum() >= 2:
        idx = np.arange(len(wb))
        wb = np.where(np.isnan(u), np.nan, np.interp(idx, idx[ok], wb[ok]))
    wb = smooth_curve(wb, 2)
    wt = wb - lw + 1
    log(f"Lachlinie in {int((~np.isnan(wb)).sum())} von {int((~np.isnan(u)).sum())} Mundspalten, Stärke {lw:.1f} Quellpixel")
    for xi in range(hw):
        u_, h_, t_, b_ = sample(u, x0, xi), sample(hh_n, x0, xi), sample(wt, x0, xi), sample(wb, x0, xi)
        if not (np.isnan(u_) or np.isnan(t_)):
            mouthcols[xi] = [u_ * k - hoy, h_ * k, t_ * k - hoy, b_ * k - hoy]
    rig_face["mouth"] = {"rect": parts["mouth"]["rect"], "line_px": lw,
                         "line_bottom": [None if np.isnan(v) else round(float(v), 1) for v in wb],
                         "u": [None if np.isnan(v) else round(float(v), 1) for v in u],
                         "h": [round(float(v), 1) for v in hh]}

    # Masken für den Shader: G = Augenbereich links, B = rechts (je weich, Überblendung zum geschlossenen Auge);
    # R = Mundbereich nur noch für Prüfbilder (der Mund wird spaltenweise aus mouthcols gezeichnet)
    fm = np.zeros(A.shape[:2] + (4,), np.float32)
    # Nase ausnehmen: die Bearbeitung zeichnet sie leicht anders; nur ab knapp über dem Mundinnenraum mischen
    y_cut = int(np.nanmin(u)) - CFG["mouth_top_margin"]
    mm = parts["mouth"]["mask"].copy()
    mm[:y_cut] = False
    mouth_m = ops.blur(ops.dilate(mm, CFG["mouth_feather_px"]).astype(np.float32), CFG["mouth_feather_px"] * 0.6)
    ramp = np.clip((np.arange(A.shape[0]) - y_cut) / 4.0, 0, 1)[:, None]
    mouth_m = mouth_m * ramp
    log(f"Mundmaske ab Zeile {y_cut} (Mundinnenraum ab {int(np.nanmin(u))})")
    fm[..., 0] = mouth_m
    for ch, kk in ((1, "eye_l"), (2, "eye_r")):
        fm[..., ch] = ops.blur(ops.dilate(parts[kk]["mask"], 4).astype(np.float32), 2.5)
    fm[..., 3] = 1.0
    fmi, offm = scaled_layer(np.concatenate([fm[..., :3], np.ones(A.shape[:2] + (1,), np.float32)], -1), head_mask, k)
    # scaled_layer teilt durch Alpha; für Masken nur RGB übernehmen
    assert offm == layers["head"]["off"] and fmi.shape == layers["head"]["img"].shape
    fmi[..., 3] = 1.0
    to_img(fmi).save(ART / "head_masks.png")

    # ---------- Knochen (Anzeige-Koordinaten im Porträt-Knoten)
    def P(x, y):
        return [round(x * k, 2), round(y * k, 2)]

    hs, h_cx = A.shape[0], seg["cx"]
    sys_, sxs = np.nonzero(scarf & ~tail)
    neck_y = float(np.median(sys_))
    eyes_c = [np.mean(parts[kk]["rect"][0::2]) for kk in ("eye_l", "eye_r")]
    eye_y = np.mean([np.mean(parts[kk]["rect"][1::2]) for kk in ("eye_l", "eye_r")])
    mrect = parts["mouth"]["rect"]
    mouth_y = (mrect[1] + mrect[3]) / 2
    face_cx = (eyes_c[0] + eyes_c[1]) / 2
    face_cy = (eye_y + mouth_y) / 2
    ys, xs = np.nonzero(body)
    shoulder_y = float(np.percentile(ys, 2))
    bones = {
        "Huefte": P(h_cx, hs + 140),
        "Brust": P(h_cx, (shoulder_y + hs) / 2),
        "Hals": P(h_cx, neck_y),
        "Kopf": P(h_cx, neck_y - 20),
        "Gesicht": P(face_cx, face_cy),
        "Ohr_L": P(*CFG["ear_l"]) if CFG.get("ear_l") else P(hx0 + (hx1 - hx0) * 0.10, hy0 + (hy1 - hy0) * 0.22),
        "Ohr_R": P(*CFG["ear_r"]) if CFG.get("ear_r") else P(hx1 - (hx1 - hx0) * 0.10, hy0 + (hy1 - hy0) * 0.22),
    }
    if tinfo:
        tl = tinfo["y1"] - tinfo["split_y"]
        tx = (tinfo["x0"] + tinfo["x1"]) / 2
        bones["Schal_1"] = P(tx, tinfo["split_y"] - 10)
        bones["Schal_2"] = P(tx, tinfo["split_y"] + tl * 0.35)
        bones["Schal_3"] = P(tx, tinfo["split_y"] + tl * 0.7)
    parent = {"Huefte": None, "Brust": "Huefte", "Hals": "Brust", "Kopf": "Hals", "Gesicht": "Kopf",
              "Ohr_L": "Kopf", "Ohr_R": "Kopf", "Schal_1": "Hals", "Schal_2": "Schal_1", "Schal_3": "Schal_2"}
    paths = {}
    for b in bones:
        chain, p = [b], parent[b]
        while p:
            chain.insert(0, p)
            p = parent[p]
        paths[b] = "/".join(chain)

    # ---------- Gitter und Gewichte
    g = CFG["grid"]
    meshes = {}
    hc = np.array(bones["Gesicht"])
    hwid, hhei = (hx1 - hx0) * k, (hy1 - hy0) * k
    for name in ("body", "head", "scarf"):
        img, (ox, oy) = layers[name]["img"], layers[name]["off"]
        verts, tris = grid_mesh(ox, oy, img.shape[1], img.shape[0], g)
        V = np.array(verts)
        W = {}
        if name == "body":
            ys0, ys1 = shoulder_y * k, hs * k
            wb = np.clip((ys1 - V[:, 1]) / (ys1 - ys0), 0, 1) ** 1.2
            W["Brust"] = wb
            W["Huefte"] = 1 - wb
        elif name == "head":
            dx = (V[:, 0] - hc[0]) / (hwid * CFG["dome_rx"])
            dy = (V[:, 1] - hc[1]) / (hhei * CFG["dome_ry"])
            dome = np.clip(1 - dx * dx - dy * dy, 0, 1) ** 0.7
            nose = np.exp(-((V[:, 0] - hc[0]) ** 2 + (V[:, 1] - hc[1]) ** 2) / (2 * (hwid * 0.12) ** 2))
            depth = np.clip(dome * 0.85 + nose * 0.15, 0, 1)
            ears = {}
            for e in ("Ohr_L", "Ohr_R"):
                c = np.array(bones[e])
                r = np.hypot(V[:, 0] - c[0], V[:, 1] - c[1])
                ears[e] = np.clip(1 - r / (hwid * CFG["ear_radius"]), 0, 1) ** 1.5 * (1 - depth)
            W["Gesicht"] = depth
            W["Ohr_L"], W["Ohr_R"] = ears["Ohr_L"], ears["Ohr_R"]
            W["Kopf"] = np.clip(1 - depth - ears["Ohr_L"] - ears["Ohr_R"], 0, 1)
        else:
            if tinfo:
                s = (V[:, 1] - tinfo["split_y"] * k) / max(1.0, (tinfo["y1"] - tinfo["split_y"]) * k)
                in_cols = (V[:, 0] >= (tinfo["x0"] - 30) * k) & (V[:, 0] <= (tinfo["x1"] + 30) * k)
                s = np.where(in_cols, s, -1)
                w1 = np.clip(1 - np.abs(s - 0.0) / 0.4, 0, 1) * (s > -0.15)
                w2 = np.clip(1 - np.abs(s - 0.4) / 0.35, 0, 1)
                w3 = np.clip((s - 0.4) / 0.35, 0, 1)
                wh = np.clip(-s / 0.15, 0, 1) * (s <= 0)
                wh = np.where(s < -0.5, 1.0, wh)
                tot = w1 + w2 + w3 + wh
                tot[tot == 0] = 1
                W["Hals"] = wh / tot
                W["Schal_1"] = w1 / tot
                W["Schal_2"] = w2 / tot
                W["Schal_3"] = w3 / tot
                W["Hals"] = np.where((W["Schal_1"] + W["Schal_2"] + W["Schal_3"] + W["Hals"]) == 0, 1.0, W["Hals"])
            else:
                W["Hals"] = np.ones(len(V))
        uv = V - np.array([ox, oy])
        meshes[name] = {"verts": V, "uv": uv, "tris": tris, "W": W}
        log(f"Gitter {name}: {len(V)} Punkte, {len(tris)} Dreiecke, Knochen {list(W)}")

    face_split = (np.mean(parts["eye_l"]["rect"][0::2]) + np.mean(parts["eye_r"]["rect"][0::2])) / 2 * k - hox
    # Augenweiß für den Blick: helle, ungesättigte Pixel in den Augenöffnungen
    Ha = hsv(A)
    em = (parts["eye_l"]["mask"] | parts["eye_r"]["mask"]) & (Ha[..., 2] > 0.78) & (Ha[..., 1] < 0.25)
    sclera = np.median(A[em][:, :3], axis=0) if em.sum() > 10 else np.array([0.93, 0.9, 0.84])
    log(f"Augenweiß {np.round(sclera, 3).tolist()} aus {int(em.sum())} Pixeln")
    write_scene(layers, meshes, bones, paths, (eyecols, mouthcols), hw, {"eye_split_x": round(float(face_split), 2), "lower_px": round(max(lower_px_eye), 2),
                                                                      "sclera": "Color(%.3f, %.3f, %.3f, 1)" % tuple(sclera)})
    rig = {"scale": k, "source_size": [A.shape[1], A.shape[0]], "align": al_info, "tail": tinfo,
           "bones": bones, "layers": {n: {"offset": v["off"], "size": [v["img"].shape[1], v["img"].shape[0]]} for n, v in layers.items()},
           "face": rig_face, "neck_y": neck_y, "shoulder_y": shoulder_y,
           "eye_size_display": [round((parts[kk]["rect"][2] - parts[kk]["rect"][0]) * k, 1) for kk in ("eye_l", "eye_r")],
           "mouth_open_max_display": round(float(hh.max() * k), 1)}
    (HERE / "assets" / "rig.json").write_text(json.dumps(rig, indent=1, ensure_ascii=False))
    debug_image(A, seg, tail, parts, layers, meshes, bones, k, inner)
    log("fertig:", DEMO / "portrait.tscn")


def write_scene(layers, meshes, bones, paths, cols, hw, extra):
    parent = {}
    lines = []
    ext = [("Script", "res://portrait.gd", "s"), ("Shader", "res://shaders/head.gdshader", "sh"),
           ("Texture2D", "res://art/body.png", "t_body"), ("Texture2D", "res://art/head.png", "t_head"),
           ("Texture2D", "res://art/head_faces.png", "t_faces"), ("Texture2D", "res://art/head_masks.png", "t_masks"),
           ("Texture2D", "res://art/scarf.png", "t_scarf")]
    lines.append(f"[gd_scene load_steps={len(ext) + 2} format=3]\n")
    for typ, path, i in ext:
        lines.append(f'[ext_resource type="{typ}" path="{path}" id="{i}"]')
    lines.append("")
    hsz = layers["head"]["img"].shape
    ev = ", ".join(f"{v:.2f}".rstrip("0").rstrip(".") for v in cols[0].reshape(-1))
    mv = ", ".join(f"{v:.2f}".rstrip("0").rstrip(".") for v in cols[1].reshape(-1))
    lines.append('[sub_resource type="ShaderMaterial" id="m_head"]')
    lines.append('shader = ExtResource("sh")')
    lines.append('shader_parameter/faces_tex = ExtResource("t_faces")')
    lines.append('shader_parameter/mask_tex = ExtResource("t_masks")')
    lines.append(f"shader_parameter/tex_size = Vector2({hsz[1]}, {hsz[0]})")
    lines.append(f"shader_parameter/eyecols = PackedVector4Array({ev})")
    lines.append(f"shader_parameter/mouthcols = PackedVector4Array({mv})")
    for kk, v in extra.items():
        lines.append(f"shader_parameter/{kk} = {v}")
    lines.append("")
    lines.append('[node name="Portrait" type="Node2D"]')
    lines.append('script = ExtResource("s")')
    lines.append("")
    lines.append('[node name="Skelett" type="Skeleton2D" parent="."]')
    lines.append("")
    for b, path in paths.items():
        par = "/".join(path.split("/")[:-1])
        p = bones[b]
        if par:
            pp = bones[path.split("/")[-2]]
            local = (p[0] - pp[0], p[1] - pp[1])
        else:
            local = (p[0], p[1])
        lines.append(f'[node name="{b}" type="Bone2D" parent="Skelett{"/" + par if par else ""}"]')
        lines.append(f"position = Vector2({local[0]:.2f}, {local[1]:.2f})")
        lines.append(f"rest = Transform2D(1, 0, 0, 1, {local[0]:.2f}, {local[1]:.2f})")
        lines.append("auto_calculate_length_and_angle = false")
        lines.append("length = 24.0")
        lines.append("bone_angle = -90.0")
        lines.append("")
    tex = {"body": "t_body", "head": "t_head", "scarf": "t_scarf"}
    names = {"body": "Koerper", "head": "Kopf", "scarf": "Schal"}
    for name in ("body", "head", "scarf"):
        m = meshes[name]
        lines.append(f'[node name="{names[name]}" type="Polygon2D" parent="."]')
        if name == "head":
            lines.append('material = SubResource("m_head")')
        lines.append(f'texture = ExtResource("{tex[name]}")')
        lines.append('skeleton = NodePath("../Skelett")')
        lines.append(f"polygon = PackedVector2Array({fmt([c for v in m['verts'] for c in v])})")
        lines.append(f"uv = PackedVector2Array({fmt([c for v in m['uv'] for c in v])})")
        lines.append("polygons = [" + ", ".join(f"PackedInt32Array({a}, {b}, {c})" for a, b, c in m["tris"]) + "]")
        bl = []
        for b, w in m["W"].items():
            bl.append(f'"{paths[b]}", PackedFloat32Array({", ".join(f"{float(x):.3f}".rstrip("0").rstrip(".") for x in w)})')
        lines.append("bones = [" + ", ".join(bl) + "]")
        lines.append(f"internal_vertex_count = {len(m['verts'])}")
        lines.append("")
    (DEMO / "portrait.tscn").write_text("\n".join(lines))


def debug_image(A, seg, tail, parts, layers, meshes, bones, k, inner):
    h, w = A.shape[:2]
    base = to_img(A).resize((round(w * k), round(h * k)), Image.LANCZOS)
    col = np.zeros((h, w, 4), np.float32)
    col[seg["head"]] = [0.2, 0.5, 1.0, 0.35]
    col[seg["body"]] = [0.2, 1.0, 0.3, 0.25]
    col[seg["scarf"] & ~tail] = [1.0, 0.9, 0.1, 0.35]
    col[tail] = [1.0, 0.3, 1.0, 0.45]
    col[inner] = [1, 0, 0, 0.6]
    for kk, p in parts.items():
        col[p["mask"]] = [0, 1, 1, 0.6]
    ov = to_img(col).resize(base.size, Image.LANCZOS)
    img = Image.new("RGBA", base.size, (40, 40, 48, 255))
    img.alpha_composite(base)
    img.alpha_composite(ov)
    d = ImageDraw.Draw(img)
    colors = {"body": (120, 255, 120, 90), "head": (120, 170, 255, 90), "scarf": (255, 230, 60, 110)}
    for name, m in meshes.items():
        V = m["verts"]
        for a, b, c in m["tris"][::1]:
            d.line([tuple(V[a]), tuple(V[b]), tuple(V[c]), tuple(V[a])], fill=colors[name], width=1)
    for b, p in bones.items():
        d.ellipse((p[0] - 5, p[1] - 5, p[0] + 5, p[1] + 5), outline=(255, 80, 80, 255), width=2)
        d.text((p[0] + 7, p[1] - 6), b, fill=(255, 255, 255, 255))
    for kk, p in parts.items():
        r = [v * k for v in p["rect"]]
        d.rectangle(r, outline=(0, 255, 255, 255))
    img.convert("RGB").save(HERE / "assets" / "rig_debug.png")


if __name__ == "__main__":
    main()
