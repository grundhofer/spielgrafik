#!/usr/bin/env python3
"""Vergleicht dasselbe Bild (t = 4,68 s, wie das Poster) in Forward+, Mobile und Compatibility.

    .venv/bin/python styles/flat-vektor/scripts/compare_renderers.py <tempordner>

Schreibt assets/renderers.json (Anteil abweichender Pixel) und <tempordner>/renderers_crop.png (Ausschnitt
zum Ansehen). Große Bilder bleiben im Tempordner und werden vom Aufrufer gelöscht.
"""
import json, pathlib, subprocess, sys
import numpy as np
from PIL import Image

ROOT = pathlib.Path(__file__).resolve().parents[3]
STYLE = ROOT / "styles" / "flat-vektor"
DEMO = STYLE / "demo"


def render(method, out, extra=()):
    out.mkdir(parents=True, exist_ok=True)
    r = subprocess.run(["godot", "--path", str(DEMO), "--rendering-method", method, "--position", "20000,20000",
                        "--resolution", "1280x720", "--write-movie", str(out / "f.png"), "--fixed-fps", "30",
                        "--quit-after", "2", "--", "--t0=4.68", *extra], capture_output=True, text=True)
    bad = [l for l in (r.stdout + r.stderr).splitlines() if "ERROR" in l]
    return np.asarray(Image.open(sorted(out.glob("f*.png"))[-1]).convert("RGB"), dtype=np.int16), bad


def main():
    tmp = pathlib.Path(sys.argv[1])
    subprocess.run(["godot", "--headless", "--path", str(DEMO), "--import"], capture_output=True)
    imgs, res = {}, {}
    for m in ("forward_plus", "mobile", "gl_compatibility"):
        imgs[m], bad = render(m, tmp / f"r_{m}")
        res[m] = {"errors": bad[:3]}
    ref = imgs["forward_plus"]
    for m in ("mobile", "gl_compatibility"):
        d = np.abs(imgs[m] - ref).max(axis=2)
        res[m].update({"share_diff_any": round(float((d > 0).mean()), 4),
                       "share_diff_over_24": round(float((d > 24).mean()), 4),
                       "max_diff": int(d.max())})
    crop = (440, 380, 760, 600)
    tiles = [Image.fromarray(imgs[m].astype(np.uint8)).crop(crop).resize((640, 440), Image.NEAREST) for m in imgs]
    sheet = Image.new("RGB", (640 * 3, 440))
    for i, t in enumerate(tiles):
        sheet.paste(t, (640 * i, 0))
    sheet.save(tmp / "renderers_crop.png")
    (STYLE / "assets" / "renderers.json").write_text(json.dumps(res, indent=1))
    print(json.dumps(res))


if __name__ == "__main__":
    main()
