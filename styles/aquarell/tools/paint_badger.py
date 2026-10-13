#!/usr/bin/env python3
"""Malt die Blender-Hilfsbilder des Dachses (badger_passes.py) als Aquarell und setzt die Clips zu Bögen zusammen.

    .venv/bin/python styles/aquarell/tools/paint_badger.py [--passes DIR] [--only walk_00,wave_00] [--preview out.png]

Je Bild: Materialflächen aus der Kennfarben-Ebene, Licht aus der Schattierungs-Ebene, Falten- und Überdeckungskanten
aus der Normalen-Ebene. Gemalt wird in 630 px (3-fach) mit Lasuren im Pigmentmodell (wc.py), danach auf 210 px
verkleinert. Das Rauschen (Pigmentwolken, Trockenpinsel, Granulation, Randverwerfung) ist für alle Bilder gleich und
an die Figur gebunden, damit der Körper beim Abspielen nicht flimmert.
"""
import argparse, json, pathlib
import numpy as np
from PIL import Image

import wc

ROOT = pathlib.Path(__file__).resolve().parents[1]
SCALE = 3                 # Malauflösung / Zielauflösung

# Lasurfarben (sRGB, wie die Fläche auf weißem Papier aussähe) und Eigenschaften je Material
MAT = {
    #            Farbe      Schatten  Kante  Gran.  Trockenpinsel
    "FurDark":  ("#5b5560", 0.55, 0.35, 0.12, 0.18),
    "FurLight": ("#f0e8d8", 0.65, 0.45, 0.05, 0.00),
    "Cap":      ("#3f6140", 0.70, 0.45, 0.15, 0.10),
    "Brass":    ("#c99a3a", 0.60, 0.20, 0.00, 0.00),
    "Vest":     ("#557545", 0.75, 0.45, 0.15, 0.10),
    "Shirt":    ("#ece0c4", 0.65, 0.50, 0.05, 0.00),
    "Scarf":    ("#c23a2e", 0.70, 0.45, 0.15, 0.15),
    "Satchel":  ("#80502e", 0.65, 0.40, 0.15, 0.05),
    "Parcel":   ("#cfa36a", 0.80, 0.45, 0.10, 0.05),
    "Nose":     ("#2a2530", 0.20, 0.00, 0.00, 0.00),
    "Eye":      ("#221e28", 0.20, 0.00, 0.00, 0.00),
}
SHADOW = wc.hexc("#b3adcf")        # kühle Schattenlasur (Ultramarin + etwas Krapprosa)
SHADOW_LIGHT = wc.hexc("#d3cbd8")  # auf hellen Flächen (Fell, Hemd) eine dünnere, grauere Schattenlasur
LIGHT_MATS = ("FurLight", "Shirt")
# Zweites Pigment je Material, nass in nass eingeflossen (Farbton schwankt innerhalb der Fläche)
SECOND = {"FurDark": "#5a4f4a", "Cap": "#3d5c55", "Vest": "#6b7a40", "Scarf": "#b8303f", "Satchel": "#8a5a2a",
          "Parcel": "#d6a868", "FurLight": "#efe2d0", "Shirt": "#efe4cc"}
SHADE_LO, SHADE_HI = 0.43, 0.83    # Schattierungs-Ebene: nur Himmelslicht .. volles Licht (gemessen)


class Field:
    """Für alle Bilder gemeinsame Rauschfelder (an die Bildfläche der Figur gebunden)."""

    def __init__(self, n):
        self.pig = wc.value_noise(n, n, 45, 11, 3)                       # Pigmentwolken
        self.dry = wc.value_noise(n, n, 10, 12, 3, aniso=(0.35, 2.2))    # senkrechte Pinselspuren im Fell
        self.gran = wc.value_noise(n, n, 6, 13, 2)                       # Granulation
        self.wx = (wc.value_noise(n, n, 18, 14, 3) - 0.5) * 5.0          # Randverwerfung in px
        self.wy = (wc.value_noise(n, n, 18, 15, 3) - 0.5) * 5.0
        self.gap = wc.value_noise(n, n, 22, 16, 3)                       # wo zwischen Flächen Papier bleibt
        self.rag = wc.value_noise(n, n, 4, 17, 3)                        # ausgefranster Außenrand
        self.hue = wc.value_noise(n, n, 70, 18, 3)                       # zweites Pigment


def load_pass(d, kind, name):
    return np.asarray(Image.open(d / f"{kind}_{name}.png").convert("RGBA")).astype(np.float64) / 255.0


def paint(d, name, ids, F):
    idp = load_pass(d, "id", name)
    sh = load_pass(d, "shade", name)
    nr = load_pass(d, "nrm", name)
    n = idp.shape[0]
    alpha = sh[..., 3]
    # Kennfarben -> Materialnummer (nächste Farbe; Workbench liefert sRGB-codierte Werte)
    names = list(ids)
    cols = np.array([wc.l2s(np.array(ids[k])) for k in names])
    dist = ((idp[..., None, :3] - cols[None, None]) ** 2).sum(-1)
    lab = np.argmin(dist, -1)
    lab[idp[..., 3] < 0.5] = -1
    # verwerfen: Flächen, Licht und Deckung mit demselben Feld verschieben -> unregelmäßige Ränder
    lab = wc.warp(lab, F.wx, F.wy, order=0)
    light = wc.warp(np.where(sh[..., 3] > 0, sh[..., 0] / np.maximum(sh[..., 3], 1e-3), 0), F.wx, F.wy)
    alpha = wc.warp(alpha, F.wx, F.wy)
    nrm = wc.warp(nr[..., :3], F.wx * 0.5, F.wy * 0.5)

    D = np.zeros((n, n, 3))
    # Licht in drei Lagen: Grundlasur überall, Schattenlasur mit harter Trockenkante, Aufhellung im Licht
    L = np.clip((light - SHADE_LO) / (SHADE_HI - SHADE_LO), 0, 1)
    shadow = wc.smoothstep(0.30, 0.22, L + (F.pig - 0.5) * 0.12)
    for i, k in enumerate(names):
        col, shk, edge, gran, dry = MAT[k]
        m = (lab == i).astype(np.float64)
        if m.sum() == 0:
            continue
        small = k in ("Eye", "Nose", "Brass")
        ms = m if small else wc.blur(m, 0.8)
        # Papierspalt zwischen Flächen: Maske stellenweise einen Hauch schrumpfen
        if not small:
            ms = np.clip((ms - 0.5) * 3 + 0.5 - wc.smoothstep(0.62, 0.8, F.gap) * 0.9 * (1 - ms), 0, 1)
        dens = wc.density(wc.hexc(col))
        if k in SECOND:
            mix = (0.25 + 0.5 * F.hue)[..., None]
            dens = dens * (1 - mix) + wc.density(wc.hexc(SECOND[k])) * mix
        mod = (0.86 + 0.28 * F.pig)                                  # Pigmentwolken
        mod *= 1.0 + edge * wc.inner_edge(ms, 5.0)                   # Trockenrand
        mod *= 1.0 + gran * (F.gran - 0.5) * 2.0                     # Granulation
        mod *= 1.0 + dry * (wc.smoothstep(0.55, 0.85, F.dry) - 0.35)  # Pinselspuren
        mod *= 0.92 + 0.16 * (1 - L)                                 # Form: im Licht dünner
        lift = wc.smoothstep(0.86, 1.0, L) * (0.55 if k in ("FurLight", "Shirt", "Parcel") else 0.2)
        D += ms[..., None] * dens * (mod * (1 - lift))[..., None]
        # Schattenlasur
        if not small:
            sd = wc.density(SHADOW_LIGHT if k in LIGHT_MATS else SHADOW) * (1.0 if k in LIGHT_MATS else shk)
            sm = shadow * ms
            D += sm[..., None] * sd * (1.0 + 0.55 * wc.inner_edge(sm, 3.0))[..., None]
    # Überdeckungs- und Faltenkanten aus Sprüngen der Normalen: dünne, unterbrochene dunklere Striche
    gx = np.abs(np.diff(nrm, axis=1, append=nrm[:, -1:])).sum(-1)
    gy = np.abs(np.diff(nrm, axis=0, append=nrm[-1:])).sum(-1)
    crease = wc.smoothstep(0.35, 0.8, wc.blur(gx + gy, 0.7)) * wc.smoothstep(0.3, 0.6, F.dry * 0.6 + F.pig * 0.6)
    crease *= (alpha > 0.9)
    D += crease[..., None] * wc.density(wc.hexc("#6d6478")) * 0.9
    # Außenrand: ausfransen und Pigment am Rand sammeln
    a = np.clip(alpha * (1.0 + 0.6 * (F.rag - 0.5)) - 0.15 * (1 - alpha), 0, 1)
    a = wc.smoothstep(0.25, 0.75, a)
    D *= (1.0 + 0.45 * wc.inner_edge(a, 3.0))[..., None]
    lin = wc.s2l(wc.PAPER) * np.exp(-D)
    return wc.to_srgb_image(lin, a)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--passes", default=str(ROOT / "assets/raw/badger_passes"))
    ap.add_argument("--only", default="")
    ap.add_argument("--preview", default="")
    ap.add_argument("--out", default=str(ROOT / "assets"))
    a = ap.parse_args()
    d = pathlib.Path(a.passes)
    info = json.loads((d / "passes.json").read_text())
    n = info["px"]
    F = Field(n)
    tgt = n // SCALE
    if a.only:
        ims = [wc.downscale_rgba(paint(d, nm, info["ids"], F), (tgt, tgt)) for nm in a.only.split(",")]
        big = [paint(d, nm, info["ids"], F) for nm in a.only.split(",")[:2]]
        W = Image.new("RGBA", (n * len(big) + tgt * len(ims), n), (244, 239, 228, 255))
        for i, im in enumerate(big):
            W.alpha_composite(im, (i * n, 0))
        for i, im in enumerate(ims):
            W.alpha_composite(im, (n * len(big) + i * tgt, n - tgt))
        W.convert("RGB").save(a.preview or "/tmp/badger_preview.png")
        return
    meta = {"frame_px": tgt, "scale": 1.0 / SCALE, "ground_y": info["ground_y"] / SCALE, "clips": {}}
    out = pathlib.Path(a.out)
    for clip, rows in info["clips"].items():
        frames = [wc.downscale_rgba(paint(d, f"{clip}_{r['n']:02d}", info["ids"], F), (tgt, tgt)) for r in rows]
        sheet = Image.new("RGBA", (tgt * len(frames), tgt), (0, 0, 0, 0))
        for i, im in enumerate(frames):
            sheet.paste(im, (i * tgt, 0))
        sheet.save(out / f"badger_{clip}.png")
        meta["clips"][clip] = {"frames": len(frames),
                               "feet": [{s: {k: v / SCALE for k, v in r["feet"][s].items()} for s in "LR"} for r in rows]}
        print("ok", clip, len(frames))
    (out / "badger_meta.json").write_text(json.dumps(meta, indent=1))


if __name__ == "__main__":
    main()
