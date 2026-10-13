#!/usr/bin/env python3
"""Prüft, dass sich Himmel und Wolken über die Zeit nur an den Sternen ändern (keine Funkelflecken in den Wolken).

    godot --path styles/jugendstil/demo --write-movie <dir>/f.png --fixed-fps 30 --quit-after 180
    .venv/bin/python styles/jugendstil/scripts/check_sky.py <dir> [<dir_t0_31>]

Je Einstellung (Totale: Bilder 0-85, Nahaufnahme: Bilder 92-179; Bild i zeigt Takt i + 1) wird je Bildschirmpixel
die Spannweite über die Zeit (größte Abweichung eines Farbkanals) gemessen, und zwar auf allen Pixeln, die laut
Maske Himmel oder Wolken (Code 0/1) zeigen und nicht vom Rahmen verdeckt sind. Ausgenommen sind die gewollten
Effekte: Sterne (art/stars.png, um 2 px erweitert), Nimbus (Radius 92 um das Leuchtfeuer), Lichthof der Laterne
(Radius 56) und die Rauchbahn (Welt x 100-430, y 30-185). Erwartet: 0 geänderte Pixel außerhalb davon.
Optional ein zweiter Ordner mit einem Lauf ab -- --t0=31 (Totale, Bilder 0-59).
"""
import json, pathlib, sys
import numpy as np
from PIL import Image, ImageFilter

ROOT = pathlib.Path(__file__).resolve().parents[1]
A = ROOT / "assets"


def check(dirn, ks, zoom, pos, name):
    sc = json.loads((A / "scene.json").read_text())
    stars = np.asarray(Image.open(A / "stars.png"))[..., 1] > 0
    mask = np.asarray(Image.open(A / "mask.png"))[..., 0] // 32
    frame_a = np.asarray(Image.open(A / "frame.png"))[..., 3] > 0
    a = np.stack([np.asarray(Image.open(pathlib.Path(dirn) / ("f%08d.png" % k)).convert("RGB")).astype(np.int16)
                  for k in ks])
    rng = (a.max(0) - a.min(0)).max(-1)
    H, W = rng.shape
    yy, xx = np.mgrid[0:H, 0:W]
    wx = np.floor((xx + 0.5 - pos[0]) / zoom).astype(int)
    wy = np.floor((yy + 0.5 - pos[1]) / zoom).astype(int)
    ok = ~frame_a & (wx >= 0) & (wx < mask.shape[1]) & (wy >= 0) & (wy < mask.shape[0])
    code = np.full((H, W), 9)
    code[ok] = mask[wy[ok], wx[ok]]
    st = np.zeros((H, W), bool)
    st[ok] = stars[wy[ok], wx[ok]]
    st = np.asarray(Image.fromarray(st.astype(np.uint8) * 255).filter(ImageFilter.MaxFilter(5))) > 0
    lamp, lan = sc["lights"]["lamp"]["centre"], sc["lights"]["lantern"]["centre"]
    fx = ((wx - lamp[0]) ** 2 + (wy - lamp[1]) ** 2 < 92 ** 2) | ((wx - lan[0]) ** 2 + (wy - lan[1]) ** 2 < 56 ** 2)
    fx |= (wx > 100) & (wx < 430) & (wy > 30) & (wy < 185)
    sky = ok & (code <= 1)
    rest = sky & ~st & ~fx
    res = {"name": name, "sky_cloud_px": int(sky.sum()), "checked_px": int(rest.sum()),
           "changed_px": int((rng[rest] > 0).sum()), "max_change": int(rng[rest].max()) if rest.any() else None,
           "star_px": int((sky & st).sum()), "max_at_stars": int(rng[sky & st].max()) if (sky & st).any() else None}
    print(res)
    return res


def main():
    lay = json.loads((A / "layout.json").read_text())["shots"]
    out = [check(sys.argv[1], range(0, 86), lay[0]["zoom"], lay[0]["pos"], "Totale"),
           check(sys.argv[1], range(92, 180), lay[1]["zoom"], lay[1]["pos"], "Nahaufnahme")]
    if len(sys.argv) > 2:
        out.append(check(sys.argv[2], range(0, 60), lay[0]["zoom"], lay[0]["pos"], "Totale ab t0=31 s"))
    (A / "measure_sky.json").write_text(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
