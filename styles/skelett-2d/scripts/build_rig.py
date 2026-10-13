#!/usr/bin/env python3
"""Baut aus dem KI-Teileblatt den Mesh-Rig des Dachses für Godot (Skeleton2D + Polygon2D + AnimationPlayer).

    .venv/bin/python styles/skelett-2d/scripts/build_rig.py [--preview-only]

Schritte:
 1. Teile aus assets/raw/parts.png über Zusammenhangskomponenten des Alphakanals ausschneiden.
 2. In den Körperraum legen (rig_def.PARTS), Vorschau der Ruhelage neben der KI-Gesamtfigur
    (assets/check/rig_rest.png).
 3. Je Teil eine Textur im Rig-Maßstab (vormultipliziert mit Lanczos verkleinert) und ein Dreiecksgitter
    (regelmäßiges Raster, nur Zellen mit Deckung).
 4. Gewichte je Gitterpunkt aus Gelenk-Übergängen (weich) – starre Fassung entsteht in Godot per --rigid.
 5. Animationen walk/stop/idle aus Fußbahnen mit Zwei-Gelenk-IK berechnen (bake_anims.py) und
    demo/badger.tscn schreiben.
"""
import argparse, json, math, pathlib, sys

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import rig_def as R
from sk_label import label

HERE = pathlib.Path(__file__).resolve().parents[1]
SHEET = HERE / "assets" / "raw" / "parts.png"
CHECK = HERE / "assets" / "check"
ART = HERE / "demo" / "art"


# ---------------------------------------------------------------- Geometrie
def rot(deg):
    a = math.radians(deg)
    return np.array([[math.cos(a), -math.sin(a)], [math.sin(a), math.cos(a)]])


def sheet_to_body(part, xy):
    p = R.PARTS[part]
    v = np.asarray(xy, float) - np.asarray(p["anchor_sheet"], float)
    return rot(p["rot"]) @ v + np.asarray(p["anchor_body"], float)


def body_to_rig(xy):
    return (np.asarray(xy, float) - np.asarray(R.ORIGIN, float)) * R.S


def bone_body_pos(spec):
    if isinstance(spec[0], str):
        return sheet_to_body(spec[0], spec[1])
    return np.asarray(spec, float)


def bones_body():
    out = {}
    for name, parent, spec in R.BONES:
        out[name] = {"parent": parent, "pos": bone_body_pos(spec)}
    kids = {}
    for name, parent, _ in R.BONES:
        if parent:
            kids.setdefault(parent, []).append(name)
    for name, b in out.items():
        if name in R.TIPS:
            b["tip"] = bone_body_pos(R.TIPS[name])
        else:
            # erstes Kind gleichen Kettennamens (Gliedmaßen) bzw. erstes Kind
            ch = kids.get(name, [])
            b["tip"] = out[ch[0]]["pos"] if ch else b["pos"] + np.array([0, 20.0])
    return out


# ---------------------------------------------------------------- Teile
def load_parts():
    im = np.asarray(Image.open(SHEET).convert("RGBA")).astype(np.float32)
    a = im[..., 3]
    small = a[::2, ::2] > 8
    lab, n = label(small)
    lab_full = np.repeat(np.repeat(lab, 2, 0), 2, 1)[: a.shape[0], : a.shape[1]]
    parts = {}
    for name, p in R.PARTS.items():
        x0, y0, x1, y1 = p["bbox"]
        # Komponente mit größter Fläche im Rahmen
        sub = lab_full[y0:y1 + 1, x0:x1 + 1]
        ids, cnt = np.unique(sub[sub > 0], return_counts=True)
        cid = ids[np.argmax(cnt)]
        m = (lab_full == cid)
        if name.startswith("scarf"):
            xx = np.arange(a.shape[1])[None, :]
            m &= (xx < R.SCARF_SPLIT_X) if name == "scarf_f" else (xx >= R.SCARF_SPLIT_X)
        # weiche Kanten (Alpha < 8) der Komponente mitnehmen, nicht die der Nachbarn
        m = np.asarray(Image.fromarray((m * 255).astype(np.uint8)).filter(ImageFilter.MaxFilter(5))) > 0
        if name.startswith("scarf"):
            xx = np.arange(a.shape[1])[None, :]
            m &= (xx < R.SCARF_SPLIT_X) if name == "scarf_f" else (xx >= R.SCARF_SPLIT_X)
        ys, xs = np.nonzero(m & (a > 0))
        bx0, by0, bx1, by1 = xs.min(), ys.min(), xs.max() + 1, ys.max() + 1
        rgba = im[by0:by1, bx0:bx1].copy()
        rgba[..., 3] *= m[by0:by1, bx0:bx1]
        # Codex liefert höchstens 253/254: deckende Flächen auf 255 setzen
        al = rgba[..., 3]
        al[al >= 248] = 255
        parts[name] = {"rgba": rgba, "origin": (int(bx0), int(by0))}
    return parts


def premul_resize(rgba, size):
    a = rgba[..., 3:4] / 255.0
    pm = np.concatenate([rgba[..., :3] * a, a * 255.0], axis=2)
    ch = [np.asarray(Image.fromarray(pm[..., i].astype(np.float32), "F").resize(size, Image.LANCZOS)) for i in range(4)]
    out = np.stack(ch, axis=2)
    al = np.clip(out[..., 3], 0, 255)
    rgb = np.where(al[..., None] > 0.5, out[..., :3] / np.maximum(al[..., None], 1e-3) * 255.0, 0)
    return np.dstack([np.clip(rgb, 0, 255), al]).astype(np.uint8)


# ---------------------------------------------------------------- Vorschau Ruhelage
def preview_rest(parts, bones, path):
    """Teile per affiner Abbildung in den Körperraum legen (Blattauflösung) und neben die KI-Gesamtfigur stellen."""
    W, H = 760, 980
    off = np.array([560.0, 10.0])          # Körperraum -> Vorschau: body - off
    canvas = Image.new("RGBA", (W, H), (120, 122, 135, 255))
    for name in sorted(R.PARTS, key=lambda k: R.PARTS[k]["draw"]):
        p = parts[name]
        src = Image.fromarray(p["rgba"].astype(np.uint8), "RGBA")
        pr = R.PARTS[name]
        # inverse Abbildung Vorschau -> Blatt: sheet = R^-1 (prev + off - anchor_body) + anchor_sheet - origin
        Ri = rot(-pr["rot"])
        ab, ash, org = np.array(pr["anchor_body"], float), np.array(pr["anchor_sheet"], float), np.array(p["origin"], float)
        c = Ri @ (off - ab) + ash - org
        coeffs = (Ri[0, 0], Ri[0, 1], c[0], Ri[1, 0], Ri[1, 1], c[1])
        layer = src.transform((W, H), Image.AFFINE, coeffs, resample=Image.BICUBIC)
        canvas.alpha_composite(layer)
    d = ImageDraw.Draw(canvas)
    for name, b in bones.items():
        p0, p1 = b["pos"] - off, b["tip"] - off
        d.line([tuple(p0), tuple(p1)], fill=(255, 220, 0, 255), width=2)
        d.ellipse([p0[0] - 4, p0[1] - 4, p0[0] + 4, p0[1] + 4], outline=(255, 60, 60, 255), width=2)
    gy = R.ORIGIN[1] - off[1]
    d.line([(0, gy), (W, gy)], fill=(0, 255, 255, 255))
    # KI-Gesamtfigur daneben (gleicher Maßstab)
    sheet = Image.open(SHEET).convert("RGBA").crop((20, 40, 560, 980))
    ref = Image.new("RGBA", sheet.size, (120, 122, 135, 255))
    ref.alpha_composite(sheet)
    out = Image.new("RGBA", (W + ref.width, H), (0, 0, 0, 255))
    out.paste(canvas, (0, 0))
    out.paste(ref, (W, 20))
    out.convert("RGB").save(path)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--preview-only", action="store_true")
    a = ap.parse_args()
    CHECK.mkdir(parents=True, exist_ok=True)
    parts = load_parts()
    bones = bones_body()
    preview_rest(parts, bones, CHECK / "rig_rest.png")
    print("Vorschau:", CHECK / "rig_rest.png")
    for k, p in parts.items():
        print(k, p["origin"], p["rgba"].shape[:2])
    if a.preview_only:
        return
    import mesh_export
    mesh_export.export(parts, bones)


if __name__ == "__main__":
    main()
