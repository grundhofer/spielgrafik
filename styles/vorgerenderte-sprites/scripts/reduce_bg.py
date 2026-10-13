#!/usr/bin/env python3
"""Vorgerenderten Hintergrund auf 426×240 und 15-Bit-Farben bringen.

    .venv/bin/python styles/vorgerenderte-sprites/scripts/reduce_bg.py RENDERDIR/bg [--colors 120]

Eingaben (aus blender/render_bg.py, 4× überabgetastet): back.png, front.png (RGBA), skymask.png,
water_XX.png (Wasserband), bg_meta.json.
Ablauf: 4×4-Mittel (vorn mit Alpha-Gewichtung, Alpha hart bei 50 %), Farbabstimmung wie bei den Sprites,
eine gemeinsame Palette für alle Ebenen und Wasserbilder (gewichtetes k-means in Oklab, BGR555),
Sterne (fester Zufall) in reine Himmelspixel. Ausgabe nach assets/bg/ und demo/bg/.
"""
import json
import pathlib
import sys

import numpy as np
from PIL import Image

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import tilepal_vs as T  # noqa: E402
import vs_color as C  # noqa: E402

STYLE = pathlib.Path(__file__).resolve().parent.parent
SS = 4


def main():
    rd = pathlib.Path(sys.argv[1])
    ncol = int(sys.argv[sys.argv.index("--colors") + 1]) if "--colors" in sys.argv else 120
    meta = json.loads((rd / "bg_meta.json").read_text())
    r0, r1 = meta["water_rows"]
    back = C.downsample(C.load_rgba(rd / "back.png"), SS)[..., :3]
    front = C.downsample(C.load_rgba(rd / "front.png"), SS)
    sky = C.downsample(C.load_rgba(rd / "skymask.png"), SS)[..., 3] < 0.02
    water = [C.downsample(C.load_rgba(p), SS)[..., :3] for p in sorted(rd.glob("water_*.png"))]
    back = C.grade(back)
    front[..., :3] = C.grade(front[..., :3])
    water = [C.grade(w) for w in water]
    fmask = front[..., 3] >= 0.5
    # Sterne: nur in reinem Himmel über 14 % Höhe, wo es dunkel genug ist
    rng = np.random.default_rng(11)
    lab = C.oklab(back)
    stars = []
    for _ in range(400):
        y, x = int(rng.integers(0, 110)), int(rng.integers(0, C_W := back.shape[1]))
        if not sky[max(0, y - 1):y + 2, max(0, x - 1):x + 2].all() or lab[y, x, 0] > 0.52 or y > 95:
            continue
        b = float(rng.uniform(0.55, 1.0)) * (1.0 - y / 120)
        stars.append((x, y, b))
        if len(stars) >= 34:
            break
    for x, y, b in stars:
        back[y, x] = np.clip(back[y, x] + b * np.array([0.65, 0.65, 0.6]), 0, 1)
    out_dirs = [STYLE / "assets" / "bg", STYLE / "demo" / "bg"]
    for d in out_dirs:
        d.mkdir(parents=True, exist_ok=True)
    imgs = {}
    # Gemeinsame Palette mit 120 Farben (so viele hat Mode 1 für die beiden 4-bpp-Ebenen zusammen),
    # aber ohne die Kachelregel; die Kachelregel lässt sich mit --tiles VERGLEICH.png messen.
    px = [back.reshape(-1, 3), front[..., :3][fmask]] + [w.reshape(-1, 3) for w in water]
    pal = C.kmeans_palette(np.concatenate(px), ncol, weight_pow=0.5)
    bi = C.map_to_palette(back, pal)
    imgs["back.png"] = C.to_rgba8(bi, pal)[..., :3]
    imgs["front.png"] = C.to_rgba8(C.map_to_palette(front[..., :3], pal), pal, fmask)
    for k, w in enumerate(water):
        imgs[f"water_{k:02d}.png"] = C.to_rgba8(C.map_to_palette(w, pal), pal)[..., :3]
    ref = C.oklab(back)
    dev = lambda rgb8: np.sqrt(((C.oklab(rgb8 / 255.0) - ref) ** 2).sum(-1))
    e_glob = dev(imgs["back.png"].astype(float))
    tile_info = {"mode": "global", "colors": int(len(pal)), "mean_oklab_dev": round(float(e_glob.mean()), 4),
                 "mean_oklab_dev_sky": round(float(e_glob[:110].mean()), 4)}
    if "--tiles" in sys.argv:
        # Vergleich Mode 1: zwei 4-bpp-Ebenen teilen 8 Paletten à 15 Farben, je 8×8-Kachel eine Palette
        T.GAMMA = 1.0
        full = np.ones(back.shape[:2], bool)
        pal8, maps, out, err = T.solve([([back], full), ([front[..., :3]], fmask)], npal=8, per=15, iters=30, seed=11)
        e_t = dev(out[0][0].astype(float))
        tile_info["mode1_test"] = {"mean_oklab_dev": round(float(e_t.mean()), 4),
                                   "mean_oklab_dev_sky": round(float(e_t[:110].mean()), 4)}
        cmp_img = np.concatenate([out[0][0], imgs["back.png"]], 1)
        Image.fromarray(cmp_img).resize((cmp_img.shape[1] * 2, cmp_img.shape[0] * 2), Image.NEAREST).save(
            sys.argv[sys.argv.index("--tiles") + 1])
        print("Kachelregel-Vergleich:", tile_info["mode1_test"], "global:", tile_info["mean_oklab_dev"],
              tile_info["mean_oklab_dev_sky"])
    for d in out_dirs:
        for name, arr in imgs.items():
            Image.fromarray(arr).save(d / name)
    used = np.unique(np.concatenate([a[..., :3].reshape(-1, 3) if a.shape[-1] == 3 else a[a[..., 3] > 0][:, :3]
                                     for a in imgs.values()]), axis=0)
    info = {"palette": ["%02x%02x%02x" % tuple(p) for p in pal], "colors_used": int(len(used)), "tiles": tile_info,
            "all_555": bool(C.is555(used).all()), "water_rows": [r0, r1], "water_frames": len(water),
            "stars": len(stars), "camera": meta["camera"], "points": meta["points"]}
    for d in out_dirs:
        (d / "bg.json").write_text(json.dumps(info, indent=1))
    print(f"BG: {len(pal)} Palettenfarben, benutzt {len(used)}, 15 Bit {info['all_555']}, Sterne {len(stars)}")


if __name__ == "__main__":
    main()
