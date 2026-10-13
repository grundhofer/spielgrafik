#!/usr/bin/env python3
"""Zerlegt einen freigestellten, gemalten Dachs in Ebenen für die Shader-Animation (ein Standbild, keine Laufbilder).

    .venv/bin/python styles/kinemagramm/tools/prep_badger.py badger.json

Konfiguration (JSON, Koordinaten im Quellbild):
  src          RGBA-Bild (freigestellt)
  height       Zielhöhe in px (Füße bis Mützenspitze)
  tail         Polygon um das frei hängende Schalende (wird zur eigenen Ebene)
  anchor_y     Höhe, ab der der Schal frei schwingt (darüber fest am Hals)
  tail_axis    optional [[x, y] Ansatz, [x, y] Spitze] des Schalendes (z. B. waagerecht wehender Schal);
               ohne Angabe senkrecht von anchor_y bis zum unteren Ende des Schalendes
  despill      Magenta-Saum entfernen (nur bei agy-Freistellung nötig; Codex liefert echten Alphakanal)
  erode        Rand um so viele px zurücknehmen (Standard 1)
  eyes         [[x, y, r], ...] Augen (werden für das Blinzeln mit Fell aus der Umgebung "geschlossen")
  lid_color    optional: Farbe des Lidstrichs
Ausgaben in demo/art/:
  badger_body.png   Körper ohne Schalende, dahinter aufgefüllt
  badger_scarf.png  nur das Schalende
  badger_lids.png   geschlossene Lider (Alpha = Augenfläche)
  badger.json       Größe, Fußpunkt, Anker und Schalbereich in Texturkoordinaten
"""
import argparse, json, pathlib, sys

import numpy as np
from PIL import Image

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import imgops as K  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("config")
    ap.add_argument("--out")
    ap.add_argument("--debug")
    a = ap.parse_args()
    cfgp = pathlib.Path(a.config).resolve()
    cfg = json.loads(cfgp.read_text())
    base = (cfgp.parent / cfg.get("base", "..")).resolve()
    out = pathlib.Path(a.out or base / "demo" / "art")
    out.mkdir(parents=True, exist_ok=True)

    im = Image.open(base / cfg["src"]).convert("RGBA")
    if cfg.get("crop"):
        im = im.crop(tuple(cfg["crop"]))
    pad = cfg.get("pad", 24)
    padded = Image.new("RGBA", (im.width + 2 * pad, im.height + 2 * pad), (0, 0, 0, 0))
    padded.paste(im, (pad, pad))
    im = padded
    shift = lambda v: [c + pad for c in v]  # noqa: E731
    for key in ("tail",):
        if cfg.get(key):
            cfg[key] = [shift(p) for p in cfg[key]]
    if cfg.get("anchor_y") is not None:
        cfg["anchor_y"] += pad
    cfg["eyes"] = [[ex + pad, ey + pad, er] for ex, ey, er in cfg.get("eyes", [])]
    if cfg.get("tail_axis"):
        cfg["tail_axis"] = [shift(p) for p in cfg["tail_axis"]]
    arr = np.asarray(im, np.float32).copy() / 255.0
    alpha = arr[..., 3]
    # Reste mit sehr geringer Deckung entfernen (Saum vom Freistellen)
    alpha = np.where(alpha < cfg.get("alpha_floor", 0.08), 0, alpha)
    if cfg.get("despill", True):
        # Magenta-Saum (agy-Freistellung): im Randstreifen Rot und Blau auf Grün + Rest begrenzen
        band = K.blur((alpha < 0.98).astype(np.float32), 3) > 0.01
        r_, g_, b_ = arr[..., 0], arr[..., 1], arr[..., 2]
        spill = np.clip(np.minimum(r_, b_) - g_ - 0.04, 0, 1) * band
        arr[..., 0] = r_ - spill
        arr[..., 2] = b_ - spill
    # Rand um ~1 px zurücknehmen
    er = cfg.get("erode", 1)
    if er:
        alpha = np.minimum(alpha, np.clip((K.box(alpha, er) - 0.5) * 2.2 + 0.5, 0, 1))
    ys, xs = np.where(alpha > 0.5)
    x0, x1 = xs.min() - pad, xs.max() + pad
    y0, y1 = ys.min() - pad, ys.max() + 4
    fig_h = ys.max() - ys.min()
    scale = cfg["height"] / fig_h

    size_src = (alpha.shape[1], alpha.shape[0])
    tail = K.poly_mask(size_src, [cfg["tail"]]) if cfg.get("tail") else np.zeros_like(alpha)
    rgb = arr[..., :3]
    red = (rgb[..., 0] > 0.22) & (rgb[..., 0] > rgb[..., 1] * 1.45) & (rgb[..., 0] > rgb[..., 2] * 1.3)
    tail = tail * red * (alpha > 0.3)
    tail = np.clip(K.blur(tail.astype(np.float32), 1) * 1.6, 0, 1) * (alpha > 0.05)

    # Körper hinter dem Schalende: innerhalb der Körperbreite je Zeile deckend, außerhalb durchsichtig
    body_only = (alpha > 0.5) & (tail < 0.5)
    span = np.zeros_like(alpha)
    for y in range(alpha.shape[0]):
        xx = np.where(body_only[y])[0]
        if len(xx):
            span[y, xx.min():xx.max() + 1] = 1
    span = K.blur(span, 1)
    body_alpha = np.where(tail > 0.02, np.minimum(np.maximum(alpha * (1 - tail), span), 1), alpha)
    known = (alpha > 0.6) & (tail < 0.02)
    fill = K.pushpull(rgb, known.astype(np.float32))
    body_rgb = np.where((tail > 0.02)[..., None], fill, rgb)
    scarf_rgb, scarf_a = rgb, alpha * tail

    # Lider: Augenfläche aus dem umgebenden Fell füllen, unten ein dunkler Lidstrich
    lids_a = np.zeros_like(alpha)
    yy, xx = np.mgrid[0:alpha.shape[0], 0:alpha.shape[1]].astype(np.float32)
    lid_rgb = rgb.copy()
    for ex, ey, er in cfg.get("eyes", []):
        d = np.hypot((xx - ex) / 1.15, yy - ey)
        lids_a = np.maximum(lids_a, K.smoothstep(er * 1.15, er * 0.75, d))
    ring = (lids_a < 0.05) & (alpha > 0.5)
    lfill = K.pushpull(rgb, ring.astype(np.float32))
    lid_rgb = lfill
    if cfg.get("eyes"):
        lc = np.array(cfg.get("lid_color", [0.08, 0.07, 0.07]), np.float32)
        for ex, ey, er in cfg["eyes"]:
            line = K.smoothstep(er * 0.32, 0.0, np.abs(yy - (ey + er * 0.25))) * (np.abs(xx - ex) < er * 1.05)
            lid_rgb = lid_rgb * (1 - line[..., None] * 0.85) + lc * line[..., None] * 0.85

    def finish(rgb_, a_, name):
        rgba = np.dstack([rgb_, a_])[y0:y1, x0:x1]
        pil = Image.fromarray(np.clip(rgba * 255 + 0.5, 0, 255).astype(np.uint8), "RGBA")
        # vormultipliziert verkleinern, damit keine dunklen/farbigen Säume entstehen
        pm = np.asarray(pil, np.float32) / 255.0
        pm[..., :3] *= pm[..., 3:4]
        w2, h2 = round(pil.width * scale), round(pil.height * scale)
        ch = [np.asarray(Image.fromarray(pm[..., k], "F").resize((w2, h2), Image.LANCZOS)) for k in range(4)]
        r = np.stack(ch, -1)
        r[..., 3] = np.clip(r[..., 3], 0, 1)
        # Lanczos-Überschwinger begrenzen (vormultipliziert: RGB <= Alpha), sonst helle Säume an weichen Kanten
        r[..., :3] = np.clip(r[..., :3], 0, r[..., 3:4])
        r[..., :3] = np.where(r[..., 3:4] > 1e-3, r[..., :3] / np.maximum(r[..., 3:4], 1e-3), 0)
        # Farbe in durchsichtige Ränder ausbluten lassen (lineare Filterung ohne Saum)
        r[..., :3] = K.pushpull(r[..., :3], (r[..., 3] > 0.5).astype(np.float32)) * (r[..., 3:4] <= 0.5) + \
            r[..., :3] * (r[..., 3:4] > 0.5)
        Image.fromarray(np.clip(r * 255 + 0.5, 0, 255).astype(np.uint8), "RGBA").save(out / name)
        return w2, h2

    w2, h2 = finish(body_rgb, body_alpha, "badger_body.png")
    finish(scarf_rgb, scarf_a, "badger_scarf.png")
    finish(lid_rgb, lids_a, "badger_lids.png")

    def to_tex(y):
        return (y - y0) * scale / h2

    ty = np.where(tail.sum(1) > 0)[0]
    meta = {"size": [w2, h2], "feet_v": float(to_tex(ys.max())),
            "anchor_v": float(to_tex(cfg.get("anchor_y", ty.min() if len(ty) else 0))),
            "tail_end_v": float(to_tex(ty.max() if len(ty) else 0)),
            "eyes_v": [[float((ex - x0) * scale / w2), float(to_tex(ey))] for ex, ey, er in cfg.get("eyes", [])],
            "scale": scale}
    if cfg.get("tail_axis"):
        meta["tail_axis"] = [[float((x - x0) * scale / w2), float(to_tex(y))] for x, y in cfg["tail_axis"]]
    (out / "badger.json").write_text(json.dumps(meta, indent=1))
    print(json.dumps(meta))
    if a.debug:
        d = pathlib.Path(a.debug)
        d.mkdir(parents=True, exist_ok=True)
        K.save_gray(tail, d / "badger_tail.png")
        K.save_gray(lids_a, d / "badger_lids_a.png")


if __name__ == "__main__":
    main()
