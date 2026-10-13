"""Vergleichsschalter für die Mode-7-Ebene (PIPELINE.md: Effekte messen statt schätzen).

Aufruf: .venv/bin/python styles/mode7/scripts/compare_plane.py

Rechnet die Ebene für einige Zeitpunkte dreimal:
  A  wie die Hardware: 8.8-Festkomma je Zeile (HDMA), abgeschnittene untere 6 Bit, nächster Texel
  B  exakte Gleitkomma-Perspektive je Pixel, nächster Texel (ohne Festkomma-Treppung)
  C  exakte Perspektive mit 4×4-Überabtastung je Pixel (ungefähr das, was Mipmaps/Filter glätten würden)
und meldet den Anteil geänderter Pixel (A gegen B: Festkomma, B gegen C: Aliasing/Flimmern) sowie, wie
viele Pixel sich zwischen zwei aufeinanderfolgenden Bildern ändern (Flimmern in der Ferne).
Ausgabe: assets/compare_plane.png (Ausschnitte A | B | C), assets/compare_plane.json
"""
import json
import math
import sys
import pathlib

import numpy as np
from PIL import Image

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from m7lib import F, H, MAP, PLANE_END, STYLE, TPM, W, Y_H, basis, camera, hdma_table, render_plane, to_texel  # noqa

tiles = np.load(STYLE / "assets/m7_tiles.npy")
tmap = np.asarray(Image.open(STYLE / "demo/art/m7_map.png"))
cg = json.loads((STYLE / "demo/data/cgram.json").read_text())
lut = np.round(np.array(cg["base"]) * 255 / 31).astype(np.uint8)


def texel_index(px, py):
    px = np.floor(px).astype(np.int64)
    py = np.floor(py).astype(np.int64)
    oob = ((px | py) & ~1023) != 0
    tile = np.where(oob, 0, tmap[(py >> 3) & 127, (px >> 3) & 127])
    return tiles[tile, py & 7, px & 7]


def plane_float(cx, cy, th, h, ss=1):
    cu, cv = to_texel(cx, cy)
    fwd, right = basis(th)
    out = np.zeros((H, W, 3), np.float64)
    for y in range(Y_H + 1, PLANE_END):
        acc = np.zeros((W, 3))
        for sy in range(ss):
            for sx in range(ss):
                yy = y + (sy + 0.5) / ss - 0.5
                if yy - Y_H <= 0.05:
                    yy = Y_H + 0.05
                lam = F * h * TPM / (yy - Y_H)
                xs = np.arange(W) + (sx + 0.5) / ss - 0.5
                px = cu + lam * fwd[0] + (xs - 128) * lam / F * right[0]
                py = cv + lam * fwd[1] + (xs - 128) * lam / F * right[1]
                acc += lut[texel_index(px, py)]
        out[y] = acc / (ss * ss)
    return out


def main():
    res = {"times": []}
    panels = []
    for tt in (0.5, 2.0, 3.6):
        cx, cy, th, h = camera(tt)
        tab, regs = hdma_table(cx, cy, th, h)
        A = lut[render_plane(tab, regs, tmap, tiles)].astype(np.float64)
        B = plane_float(cx, cy, th, h, 1)
        C = plane_float(cx, cy, th, h, 4)
        sl = slice(Y_H + 1, PLANE_END)
        ab = float((np.abs(A[sl] - B[sl]).max(axis=2) > 0).mean())
        bc = float((np.abs(B[sl] - C[sl]).max(axis=2) > 24).mean())
        far = slice(Y_H + 1, Y_H + 41)
        bc_far = float((np.abs(B[far] - C[far]).max(axis=2) > 24).mean())
        # Flimmern: Änderung zwischen zwei Bildern (1/30 s) im fernen Band, Hardware gegen geglättet
        cx2, cy2, th2, h2 = camera(tt + 1 / 30)
        tab2, regs2 = hdma_table(cx2, cy2, th2, h2)
        A2 = lut[render_plane(tab2, regs2, tmap, tiles)].astype(np.float64)
        C2 = plane_float(cx2, cy2, th2, h2, 4)
        fl_a = float((np.abs(A2[far] - A[far]).max(axis=2) > 24).mean())
        fl_c = float((np.abs(C2[far] - C[far]).max(axis=2) > 24).mean())
        res["times"].append(dict(t=tt, fixed_vs_float=round(ab, 4), nearest_vs_supersampled=round(bc, 4),
                                 nearest_vs_supersampled_far40=round(bc_far, 4),
                                 frame_change_far40_hardware=round(fl_a, 4),
                                 frame_change_far40_supersampled=round(fl_c, 4)))
        crop = (slice(Y_H + 1, Y_H + 81), slice(0, 256))
        panels.append(np.concatenate([A[crop], B[crop], C[crop]], axis=1))
    img = np.concatenate(panels, axis=0).astype(np.uint8)
    Image.fromarray(img).resize((img.shape[1] * 2, img.shape[0] * 2), Image.NEAREST).save(
        STYLE / "assets/compare_plane.png")
    (STYLE / "assets/compare_plane.json").write_text(json.dumps(res, indent=1))
    print(json.dumps(res, indent=1))


if __name__ == "__main__":
    main()
