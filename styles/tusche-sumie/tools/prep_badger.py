#!/usr/bin/env python3
"""KI-Figurenbögen (Tuschzeichnung) -> Einzelbilder der Figur für Godot.

    .venv/bin/python styles/tusche-sumie/tools/prep_badger.py

Liest die Figurenbögen laut assets/badger_override.json → source (sonst assets/raw/walk.png und front.png),
assets/ref/layouts.json, die Blender-Posen in
assets/ref/poses_*/ und assets/badger_override.json (Maßstab, Ablauf, Teile).
Schritte je Bild:
  1. Komponenten des Alphakanals den Layoutzellen zuordnen (Schwerpunkt), Zelle mit Rand ausschneiden.
  2. Silhouette = deckender Teil des KI-Alphas (Papierweiß in der Figur bleibt deckend, damit der Kai dahinter
     nicht durchscheint), Rand 1–2 px aus dem KI-Alpha (Kantenglättung bleibt), Hintergrundschleier verworfen.
  3. Tusche d und Zinnober r je Pixel zurückrechnen (Papier = hellster Ton in der Figur), Papierstruktur unter
     ink_floor entfernen.
  4. Registrieren auf die Blender-Pose derselben Zelle: Maßstab (0,90–1,16) und Versatz mit der besten
     Überdeckung der Silhouetten (Kreuzkorrelation per FFT). Danach liegt jedes Bild im Layoutraum, in dem der
     Fußpunkt der Figur (Wurzel auf dem Boden) für alle Bilder derselbe ist; der Lauf auf der Stelle aus Blender
     bleibt erhalten, und der Vorschub je Laufbild ist der aus Blender (0,367 m/s, 8 Bilder je Sekunde Zyklus).
  5. Vorderbogen aus Teilen: fester Körper aus "front", Winkarm, Augen und Mund aus den anderen Bildern
     (Differenzmaske nur in den Bereichen laut Override-Datei, weich überblendet).
  6. Ein Maßstab für alle Bilder (scale), Lanczos auf d, r und Alpha getrennt; Lasur leicht wolkig (Rauschen im
     Layoutraum, also an derselben Figurstelle gleich); Tusche läuft 1–2 px ins Papier aus.
Ergebnis: assets/badger/<name>.png (RGB = Transmission inkl. Auslaufen, A = Silhouette für die Papierfüllung),
assets/badger_meta.json (Anker = Fußpunkt, Vorschub), assets/badger_walk.png und assets/badger_front.png
(Übersichtsblätter für den Katalog), assets/badger_register.json (Maßstab, Versatz, IoU je Bild).
"""
import json, math

import numpy as np
from PIL import Image

from components import label
from inkutil import ROOT, ALPHA_FLOOR, INK_RGB, VERMILION_RGB, blur, noise
from prep_bg import unmix

OUT = ROOT / "assets/badger"
P = 64                     # Rand um jede Zelle im Layoutraum


def fill_holes(mask):
    """Alles, was nicht vom Rand aus über Nicht-Maske erreichbar ist, gehört zur Figur."""
    outside = np.zeros_like(mask)
    outside[0, :] = ~mask[0, :]
    outside[-1, :] = ~mask[-1, :]
    outside[:, 0] |= ~mask[:, 0]
    outside[:, -1] |= ~mask[:, -1]
    free = ~mask
    while True:
        g = outside.copy()
        g[1:, :] |= outside[:-1, :]
        g[:-1, :] |= outside[1:, :]
        g[:, 1:] |= outside[:, :-1]
        g[:, :-1] |= outside[:, 1:]
        g &= free
        if (g == outside).all():
            break
        outside = g
    return ~outside


def cells_of(sheet_rgba, layout):
    a = sheet_rgba[..., 3] / 255.0
    small = a[::4, ::4] > 0.3
    boxes = label(small)
    cells = layout["cells"]
    owner = {}
    for b in boxes:
        if b[4] < 6:
            continue
        cy, cx = (b[0] + b[2]) * 2, (b[1] + b[3]) * 2
        best = min(range(len(cells)), key=lambda i: (cells[i]["x"] + cells[i]["w"] / 2 - cx) ** 2
                   + (cells[i]["y"] + cells[i]["h"] / 2 - cy) ** 2)
        owner.setdefault(best, []).append(b)
    out = []
    for i, c in enumerate(cells):
        m = np.zeros(a.shape, bool)
        for b in owner.get(i, []):
            m[b[0] * 4:b[2] * 4 + 4, b[1] * 4:b[3] * 4 + 4] = True
        out.append((c, m))
    return out


def cell_arrays(sheet, cell, own, ov):
    """d, r, alpha der Zelle im Zellraum mit Rand P (Form (h+2P, w+2P)), Ursprung = Zellecke - P."""
    x, y, w, h = cell["x"], cell["y"], cell["w"], cell["h"]
    H, W = sheet.shape[:2]
    out = [np.zeros((h + 2 * P, w + 2 * P), np.float32) for _ in range(3)]
    X0, Y0, X1, Y1 = max(0, x - P), max(0, y - P), min(W, x + w + P), min(H, y + h + P)
    rgba = sheet[Y0:Y1, X0:X1].astype(np.float32) / 255.0
    a = rgba[..., 3] * own[Y0:Y1, X0:X1]
    rgb = rgba[..., :3] * a[..., None] + (1 - a[..., None])
    # Der Laufbogen kam mit halbtransparentem Schleier im Hintergrund (Alpha 0,1–0,3, dunkle Farbe): nur die
    # deckende Figur (Alpha > 0,5) und ein 1–2 px breiter Kantenring aus dem KI-Alpha zählen. Löcher werden nicht
    # gefüllt: Das Bildmodell hat das Papierweiß in der Figur deckend geliefert, verbleibende Löcher sind echte
    # Lücken (zwischen Arm und Körper).
    sil = a > 0.5
    near = blur(sil.astype(np.float32), 1.0) > 0.05
    alpha = np.where(sil, 1.0, a * near)
    inside = sil & (a > 0.98)
    pw = np.quantile(rgb[inside], 0.97, axis=0) if inside.any() else np.ones(3)
    paper = np.broadcast_to(np.maximum(pw, 0.5), rgb.shape)
    d, r = unmix(rgb, paper)
    sat = (rgb[..., 0] - rgb[..., 1]) / np.maximum(rgb[..., 0], 1e-3)
    red = np.clip((sat - ov.get("red_sat", 0.25)) * 8, 0, 1)
    r = r * np.clip(blur(red, 0.8) * 1.5, 0, 1)
    fl = ov.get("ink_floor", 0.06)
    d = np.clip((d - fl) / (1 - fl), 0, 1) ** ov.get("ink_gamma", 1.0)
    oy, ox = Y0 - (y - P), X0 - (x - P)
    for dst, src in zip(out, (d * alpha, r * alpha, alpha)):
        dst[oy:oy + src.shape[0], ox:ox + src.shape[1]] = src
    return out


def layout_alpha(key, cell):
    a = np.asarray(Image.open(ROOT / f"assets/ref/poses_{key}/{cell['name']}.png"), np.float32)[..., 3] / 255.0
    out = np.zeros((cell["h"] + 2 * P, cell["w"] + 2 * P), np.float32)
    out[P:P + a.shape[0], P:P + a.shape[1]] = a
    return out


def scale_about(a, s, g):
    """Ausgabe(p) = Eingabe(g + s (p - g)) mit bikubischer Abtastung."""
    h, w = a.shape
    im = Image.fromarray(a.astype(np.float32), "F")
    t = im.transform((w, h), Image.AFFINE, (s, 0, (1 - s) * g[0], 0, s, (1 - s) * g[1]), Image.BICUBIC)
    return np.asarray(t, np.float32)


def shift(a, ex, ey):
    """Ausgabe(p) = Eingabe(p + e) (bikubisch, Bruchteile erlaubt)."""
    h, w = a.shape
    im = Image.fromarray(a.astype(np.float32), "F")
    return np.asarray(im.transform((w, h), Image.AFFINE, (1, 0, ex, 0, 1, ey), Image.BICUBIC), np.float32)


def register(ai, lay, g, scales):
    """Bester Maßstab s und Versatz e, so dass Layout(p) ≈ KI(g + s (p - g) + s e) (IoU der Silhouetten)."""
    L = (lay > 0.5).astype(np.float32)
    FL = np.conj(np.fft.rfft2(L))
    best = None
    for s in scales:
        A = (scale_about(ai, s, g) > 0.5).astype(np.float32)
        c = np.fft.irfft2(FL * np.fft.rfft2(A), s=A.shape)
        iy, ix = np.unravel_index(np.argmax(c), c.shape)
        ey = iy if iy < A.shape[0] // 2 else iy - A.shape[0]
        ex = ix if ix < A.shape[1] // 2 else ix - A.shape[1]
        inter = c[iy, ix]
        iou = inter / (L.sum() + A.sum() - inter)
        if best is None or iou > best[0]:
            best = (float(iou), float(s), int(ex), int(ey))
    return best


def to_layout(arrs, s, ex, ey, g):
    return [np.clip(shift(scale_about(a, s, g), ex, ey), 0, 1) for a in arrs]


def compose_parts(frames, parts):
    """Vorderbilder aus Teilen: Basis + Differenz in einem Bereich (Layoutraum), weich überblendet."""
    out = dict(frames)
    for name, spec in parts.items():
        base = frames[spec["base"]]
        src = frames[name]
        x0, y0, x1, y1 = spec["region"]
        diff = np.maximum(np.abs(src[2] - base[2]), np.abs(src[0] - base[0]) * spec.get("ink_weight", 1.0))
        m = np.zeros_like(diff)
        m[y0 + P:y1 + P, x0 + P:x1 + P] = 1.0
        if spec.get("whole_region"):
            mask = m
        else:
            mask = (blur((diff > spec.get("thresh", 0.2)).astype(np.float32), spec.get("grow", 6)) > 0.05) * m
        mask = np.clip(blur(mask.astype(np.float32), spec.get("feather", 3)), 0, 1) * m
        out[name] = [b * (1 - mask) + c * mask for b, c in zip(base, src)]
    return out


def to_rgba(d, r, alpha):
    t = (1 - d[..., None] * (1 - INK_RGB)) * (1 - r[..., None] * (1 - VERMILION_RGB))
    rgba = np.dstack([t, alpha])
    return Image.fromarray((np.clip(rgba, 0, 1) * 255 + 0.5).astype(np.uint8), "RGBA")


def foot_shear(a, dx, sole, span):
    """Schiebt die Füße um dx px waagerecht, nach oben über span Zeilen auslaufend (Kopf und Rumpf bleiben):
    gleicht einzelne KI-Bilder aus, in denen der Standfuß ein paar Pixel neben dem der Nachbarbilder gezeichnet ist."""
    out = a.copy()
    xs = np.arange(a.shape[1], dtype=np.float32)
    for y in range(max(0, sole - span), a.shape[0]):
        k = min(1.0, (y - (sole - span)) / span)
        out[y] = np.interp(xs - dx * k, xs, a[y], left=0, right=0)
    return out


def resize(a, s):
    h, w = a.shape
    im = Image.fromarray(a.astype(np.float32), "F").resize((max(1, round(w * s)), max(1, round(h * s))), Image.LANCZOS)
    return np.clip(np.asarray(im, np.float32), 0, 1)


def main():
    ov = json.loads((ROOT / "assets/badger_override.json").read_text())
    lay = json.loads((ROOT / "assets/ref/layouts.json").read_text())
    OUT.mkdir(parents=True, exist_ok=True)
    S = ov["scale"]
    ppm = lay["walk"]["px_per_m"]
    adv_layout = 0.367 / 8 * ppm * S                   # Vorschub je Laufbild laut Blender (Lauf auf der Stelle)
    # gemessen am Standfuß der fertigen Laufbilder (Spitze des stehenden Fußes rückt je Bild 9–10 px zurück,
    # das KI-Bild zeichnet den Schritt etwas länger als das Layout); siehe measure_badger.py
    adv = ov.get("advance_px", adv_layout)
    meta = {"frames": {}, "walk": ov["walk_order"], "advance": [round(adv, 3)] * len(ov["walk_order"]),
            "plan": ov["plan"], "scale": S, "advance_layout": round(adv_layout, 3),
            "advance_note": "Layout: 0,367 m/s / 8 Bilder je Zyklus * px_per_m * scale; verwendet: advance_px"}
    reg = {}
    scales = np.arange(0.90, 1.30, 0.005)
    for key in ("walk", "front"):
        raw = ROOT / ov.get("source", {}).get(key, f"assets/raw/{key}.png")
        if not raw.exists():
            continue
        sheet = np.asarray(Image.open(raw).convert("RGBA"))
        root = ov["root_px"][key]                      # Fußpunkt der Figur in der Zelle (aus pose_layout.py)
        frames, gs = {}, None
        # Übermalter Bogen (gleiche Posen wie ein früherer Bogen): erst den früheren Bogen wie gewohnt auf die
        # Blender-Pose registrieren, dann jedes Bild des neuen Bogens auf das frühere Bild im Layoutraum. So erbt
        # der neue Bogen die gemessene Fußlage des früheren, statt neu (und anders) auf die Pose zu passen.
        via_sheet, via_cells = None, {}
        if ov.get("register_via", {}).get(key):
            via_sheet = np.asarray(Image.open(ROOT / ov["register_via"][key]).convert("RGBA"))
            via_cells = {c["name"]: (c, o) for c, o in cells_of(via_sheet, lay[key])}
        base = ov.get("base", {}).get(key)
        cells = sorted(cells_of(sheet, lay[key]), key=lambda co: co[0]["name"] != base)   # Basis zuerst
        for cell, own in cells:
            name = cell["name"]
            if name not in ov["use"]:
                continue
            g = (root + P, cell["ground_y"] - cell["y"] + P)
            arrs = cell_arrays(sheet, cell, own, ov)
            if base and name != base:
                # Bilder aus Teilen: auf das Basisbild (schon im Layoutraum) registrieren, nicht auf die Pose
                iou, s, ex, ey = register(arrs[2], frames[base][2], g, np.arange(0.85, 1.35, 0.005))
            elif name in via_cells:
                vc, vo = via_cells[name]
                va = cell_arrays(via_sheet, vc, vo, ov)
                viou, vs, vex, vey = register(va[2], layout_alpha(key, vc), g, scales)
                ref_alpha = to_layout(va, vs, vex, vey, g)[2]
                iou, s, ex, ey = register(arrs[2], ref_alpha, g, np.arange(0.85, 1.20, 0.005))
                reg.setdefault("_via", {})[name] = {"iou": round(viou, 3), "s": round(vs, 3), "ex": vex, "ey": vey}
            else:
                iou, s, ex, ey = register(arrs[2], layout_alpha(key, cell), g, scales)
            reg[name] = {"iou": round(iou, 3), "s": round(s, 3), "ex": ex, "ey": ey}
            frames[name] = to_layout(arrs, s, ex, ey, g)
            gs = g
        frames = compose_parts(frames, {k: v for k, v in ov.get("parts", {}).items() if k in frames})
        # gemeinsames Rauschen im Layoutraum
        any_f = next(iter(frames.values()))[0]
        # Maßstab je Bogen: Der Vorderbogen ist nach der Registrierung auf die Blender-Pose niedriger als die
        # Seitenansicht (die KI zeichnet ihn gedrungener); sheet_scale gleicht die Höhe an, sonst springt der Kopf
        # beim Wechsel Dreiviertel -> Vorderansicht
        Sk = S * ov.get("sheet_scale", {}).get(key, 1.0)
        hs, ws = round(any_f.shape[0] * Sk), round(any_f.shape[1] * Sk)
        nz = noise(hs, ws, 5, 99, octaves=2)
        tiles = []
        for name, (d, r, alpha) in frames.items():
            ds, rs, as_ = resize(d, Sk), resize(r, Sk), resize(alpha, Sk)
            as_ = np.clip((as_ - 0.04) / 0.96, 0, 1)
            fx = ov.get("foot_fix", {}).get(name)
            if fx:
                sole = int(np.where(as_.max(axis=1) > 0.5)[0].max())
                ds, rs, as_ = (foot_shear(v, fx["dx"], sole, fx["span"]) for v in (ds, rs, as_))
            n = nz[:ds.shape[0], :ds.shape[1]]
            ds = np.clip(ds * (1 + ov.get("wash_var", 0.2) * n * 4 * ds * (1 - ds)), 0, 1)
            rs = np.clip(rs * ov.get("red_gain", 1.0) * (1 + 0.15 * n), 0, 1)
            ds = np.maximum(ds, blur(ds, ov.get("bleed_sigma", 1.1)) * ov.get("bleed", 0.5))
            rs = np.maximum(rs, blur(rs, ov.get("bleed_sigma", 1.1)) * ov.get("bleed", 0.5))
            vis = np.maximum(as_, ds)
            cols = np.where(vis.max(axis=0) > 0.02)[0]
            rws = np.where(vis.max(axis=1) > 0.02)[0]
            cx0, cx1 = max(0, cols.min() - 2), min(vis.shape[1], cols.max() + 3)
            cy0, cy1 = max(0, rws.min() - 2), min(vis.shape[0], rws.max() + 3)
            # Alpha nie unter ALPHA_FLOOR: Godots Import überschreibt sonst die Farbe fast transparenter Pixel mit
            # Nachbarfarben (graue Blöcke um die Figur in der multiplizierenden Tusche-Ebene); figure.gdshader
            # rechnet die Silhouette zurück
            a_out = ALPHA_FLOOR + as_ * (1 - ALPHA_FLOOR)
            im = to_rgba(ds[cy0:cy1, cx0:cx1], rs[cy0:cy1, cx0:cx1], a_out[cy0:cy1, cx0:cx1])
            im.save(OUT / f"{name}.png")
            ax, ay = gs[0] * Sk - cx0, gs[1] * Sk - cy0
            solid = np.where(as_.max(axis=1) > 0.5)[0]
            if name not in ov["walk_order"]:
                ay = solid.max() + 1 - cy0               # Stehbilder: Sohle auf die Fußlinie
            meta["frames"][name] = {"ax": round(float(ax), 2), "ay": round(float(ay), 2), "w": im.width,
                                    "h": im.height, "height_px": int(solid.max() - solid.min() + 1),
                                    "sole_y": int(solid.max() + 1 - cy0)}
            tiles.append(im)
        W = sum(t.width for t in tiles) + 8 * (len(tiles) + 1)
        Hh = max(t.height for t in tiles) + 16
        sheet_im = Image.new("RGBA", (W, Hh), (255, 255, 255, 0))
        x = 8
        for t in tiles:
            sheet_im.paste(t, (x, Hh - 8 - t.height))
            x += t.width + 8
        sheet_im.save(ROOT / f"assets/badger_{key}.png")
    # Laufbilder: registrierter Fußpunkt liegt im Layout 2,4 px unter der Sohle; gemeinsam so verschieben, dass die
    # Sohle (Median über den Zyklus) auf der Fußlinie steht wie bei den Stehbildern
    off = float(np.median([meta["frames"][n]["sole_y"] - meta["frames"][n]["ay"] for n in ov["walk_order"]]))
    for n in ov["walk_order"]:
        meta["frames"][n]["ay"] = round(meta["frames"][n]["ay"] + off, 2)
    meta["walk_sole_offset"] = off
    (ROOT / "assets/badger_meta.json").write_text(json.dumps(meta, indent=1))
    (ROOT / "assets/badger_register.json").write_text(json.dumps(reg, indent=1))
    for k, v in reg.items():
        if k == "_via":
            continue
        f = meta["frames"][k]
        print(f"{k:11s} IoU {v['iou']:.3f}  s {v['s']:.3f}  e ({v['ex']:+d},{v['ey']:+d})  Höhe {f['height_px']} px  "
              f"Sohle-Anker {f['sole_y'] - f['ay']:+.1f}")
    print("Vorschub je Laufbild %.2f px" % adv)


if __name__ == "__main__":
    main()
