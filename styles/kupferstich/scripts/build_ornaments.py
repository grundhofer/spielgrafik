#!/usr/bin/env python3
"""Schneidet die drei Buchornamente aus assets/raw/ornaments.png und bringt sie auf Seitengröße.

    .venv/bin/python styles/kupferstich/scripts/build_ornaments.py

Ornamente (vom Bildmodell als ein Blatt gestochen): Initialrahmen mit leerem Feld (links), ovale Schlussvignette
(oben rechts), Zierlinie mit Knoten (unten rechts). Erkennung über Zusammenhangsflächen der aufgedickten Tusche;
das leere Feld im Initialrahmen ist die größte weiße Fläche, die den Rahmenrand nicht berührt.
Ausgabe (RGBA, Weiß mit Tusche als Alpha; Godot färbt mit der Druckfarbe): assets/orn_initial.png,
assets/orn_vignette.png, assets/orn_rule.png und assets/ornaments.json (Größen, leeres Feld in Zielpixeln).
"""
import json, shutil

import numpy as np
from PIL import Image

import inklib as K
from build_scene import components

TARGET = {"initial": ("h", 112), "vignette": ("w", 150), "rule": ("w", 300)}


def save(name, D):
    a = np.clip(D, 0, 1)
    rgba = np.dstack([np.ones_like(a)] * 3 + [a])
    out = K.SD / f"assets/orn_{name}.png"
    Image.fromarray(np.clip(rgba * 255 + 0.5, 0, 255).astype(np.uint8), "RGBA").save(out)
    shutil.copy(out, K.SD / "demo/art" / out.name)


def main():
    im = Image.open(K.SD / "assets/raw/ornaments.png").convert("RGB")
    D, _, _ = K.density(K.lum(im), lo_pct=0.5, hi_pct=99.5)
    D = np.clip((D - 0.06) / 0.9, 0, 1)
    small = K.resize_f(D, (D.shape[1] // 4, D.shape[0] // 4), Image.BOX)
    blobs = components(K.dilate(small, 3) > 0.2)
    boxes = []
    for n, ys, xs in blobs[:3]:
        boxes.append((xs.min() * 4, ys.min() * 4, xs.max() * 4 + 4, ys.max() * 4 + 4))
    boxes.sort(key=lambda b: (b[0], b[1]))
    initial = boxes[0]
    rest = sorted(boxes[1:], key=lambda b: b[1])
    named = {"initial": initial, "vignette": rest[0], "rule": rest[1]}
    meta = {}
    for name, (x0, y0, x1, y1) in named.items():
        sub = D[y0:y1, x0:x1]
        ys, xs = np.nonzero(sub > 0.15)
        sub = sub[ys.min():ys.max() + 1, xs.min():xs.max() + 1]
        axis, size = TARGET[name]
        s = size / (sub.shape[0] if axis == "h" else sub.shape[1])
        w, h = max(1, round(sub.shape[1] * s)), max(1, round(sub.shape[0] * s))
        out = K.resize_f(sub, (w, h)).clip(0, 1)
        meta[name] = {"w": w, "h": h, "scale": round(s, 4)}
        if name == "initial":
            white = K.blur(sub, 2) < 0.06
            for n, ys2, xs2 in components(white[::2, ::2]):
                if ys2.min() > 0 and xs2.min() > 0 and ys2.max() < white[::2].shape[0] - 1 \
                        and xs2.max() < white[:, ::2].shape[1] - 1:
                    meta[name]["field"] = [round(xs2.min() * 2 * s, 1), round(ys2.min() * 2 * s, 1),
                                           round((xs2.max() - xs2.min()) * 2 * s, 1),
                                           round((ys2.max() - ys2.min()) * 2 * s, 1)]
                    break
        save(name, out)
    (K.SD / "assets/ornaments.json").write_text(json.dumps(meta, indent=1))
    shutil.copy(K.SD / "assets/ornaments.json", K.SD / "demo/art/ornaments.json")
    print(json.dumps(meta))


if __name__ == "__main__":
    main()
