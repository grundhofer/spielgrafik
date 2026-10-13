"""Materialtreue Verkleinerung der Blender-Renderings des Dachses auf das Zielraster.

Je Zielpixel (SS x SS Renderpixel) entscheidet der ID-Pass, welches Material gewinnt (Mehrheit, kleine Teile wie
Auge, Nase und Messingknopf mit Vorrang); der Farbton ist das Mittel (lineares Licht) nur der Renderpixel dieses
Materials. Deckung unter 50 % = transparent. Ergebnis je Bild: Material-Index (-1 = leer) und sRGB-Ton.
"""
import json
import pathlib

import numpy as np
from PIL import Image

from amiga import lin_to_srgb, srgb_to_lin

MATERIALS = ["FurDark", "FurLight", "Cap", "Brass", "Vest", "Shirt", "Scarf", "Satchel", "Parcel", "Nose", "Eye"]
PRIORITY = {"Eye": 3.0, "Nose": 2.5, "Brass": 1.6, "Scarf": 1.1}
# Vorderansicht (zweite Hälfte der Drehung, Winken, Stehen frontal): Die Mütze sitzt tief, das Gesicht ist nur
# 4-5 Zielzeilen hoch. Mit dem Vorrang der Seitenansicht frisst die große Nase den weißen Mittelstreifen, das
# Gesicht liest sich als dunkle Maske. Hier gewinnt deshalb das helle Fell, Nase und Auge nur knapp.
PRIORITY_FRONT = {"Eye": 1.6, "Nose": 0.8, "Brass": 1.6, "Scarf": 1.0, "FurLight": 1.5}


def frontal(fr, times):
    """Bild zeigt die Figur (fast) von vorn: Winken, Stehen frontal, zweite Hälfte der Drehung."""
    if fr["state"] in ("wave", "front"):
        return True
    t0, t1 = times.get("turn", [0, 0])
    return fr["state"] == "turn" and fr["t"] >= (t0 + t1) / 2


def hexrgb(h):
    h = h.lstrip("#")
    return np.array([int(h[i:i + 2], 16) for i in (0, 2, 4)], dtype=np.float64)


def load(raw_dir):
    raw = pathlib.Path(raw_dir)
    meta = json.loads((raw / "frames.json").read_text())
    ss = meta["ss"]
    idcols = np.array([hexrgb(meta["id_colors"][m]) for m in MATERIALS])
    # Workbench gibt die Kennfarben über die Farbverwaltung aus (Standard = sRGB); nächste Kennfarbe suchen
    frames = []
    for fr in meta["frames"]:
        i = fr["i"]
        if not (raw / f"id_{i:03d}.png").exists():
            continue
        sh = np.asarray(Image.open(raw / f"shaded_{i:03d}.png").convert("RGBA")).astype(np.float64)
        idim = np.asarray(Image.open(raw / f"id_{i:03d}.png").convert("RGBA")).astype(np.float64)
        H, W = idim.shape[0] // ss, idim.shape[1] // ss
        opaque = idim[..., 3] > 127
        d = ((idim[..., None, :3] - idcols[None, None]) ** 2).sum(-1)
        mat = np.where(opaque, np.argmin(d, -1), -1)
        lin = srgb_to_lin(sh[..., :3])
        mat_c = mat[:H * ss, :W * ss].reshape(H, ss, W, ss).transpose(0, 2, 1, 3).reshape(H, W, ss * ss)
        lin_c = lin[:H * ss, :W * ss].reshape(H, ss, W, ss, 3).transpose(0, 2, 1, 3, 4).reshape(H, W, ss * ss, 3)
        cnt = np.stack([(mat_c == k).sum(-1) for k in range(len(MATERIALS))], -1).astype(np.float64)
        pr = PRIORITY_FRONT if frontal(fr, meta.get("times", {})) else PRIORITY
        prio = np.array([pr.get(m, 1.0) for m in MATERIALS])
        win = np.argmax(cnt * prio, -1)
        cover = (mat_c >= 0).sum(-1)
        win = np.where(cover * 2 >= ss * ss, win, -1)
        sel = mat_c == np.maximum(win, 0)[..., None]
        n = np.maximum(sel.sum(-1), 1)
        tone = (lin_c * sel[..., None]).sum(-2) / n[..., None]
        frames.append({"mat": win, "rgb": lin_to_srgb(tone), "meta": fr})
    return meta, frames
