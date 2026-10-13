#!/usr/bin/env python3
"""Vergleichsläufe: Schalter (Nearest gegen linear, Streifen, Kuppe) und Renderer (Forward+, Mobile,
Compatibility) am selben Zeitpunkt; Anteil geänderter Pixel. Dazu Dauerlauf ab t = 30 s.

    .venv/bin/python styles/sprite-skalierung/scripts/compare.py <tmpdir> [t]

Schreibt assets/compare.json und assets/compare_switches.png.
"""
import json, pathlib, subprocess, sys

import numpy as np
from PIL import Image, ImageDraw

SD = pathlib.Path(__file__).resolve().parents[1]


def run(td, name, t, extra=(), godot_extra=(), n=2):
    out = td / name
    out.mkdir(parents=True, exist_ok=True)
    for p in out.glob("*.png"):
        p.unlink()
    cmd = ["godot", *godot_extra, "--path", str(SD / "demo"), "--position", "20000,20000", "--write-movie",
           str(out / "f.png"), "--fixed-fps", "30", "--quit-after", str(n), "--", f"--t0={t}", *extra]
    r = subprocess.run(cmd, capture_output=True, text=True)
    log = r.stdout + r.stderr
    issues = [l for l in log.splitlines() if "ERROR" in l or "WARNING" in l]
    frames = sorted(out.glob("f*.png"))
    return [np.asarray(Image.open(f).convert("RGB")).astype(int) for f in frames], issues


def share(a, b):
    return round(float((np.abs(a - b).max(-1) > 0).mean()), 4)


def on5bit(a):
    k = np.round(a * 31 / 255)
    return float((np.round(k * 255 / 31) == a).all(-1).mean())


def main():
    td = pathlib.Path(sys.argv[1])
    t = float(sys.argv[2]) if len(sys.argv) > 2 else 3.0
    subprocess.run(["godot", "--headless", "--path", str(SD / "demo"), "--import"], capture_output=True)
    res = {"t": t}
    base, iss = run(td, "base", t)
    res["base_issues"] = iss[:5]
    ref = base[0]
    res["share_on_5bit_grid"] = round(on5bit(ref), 4)
    res["colors_in_frame"] = int(len(np.unique(ref.reshape(-1, 3), axis=0)))
    imgs = {"normal": ref}
    for name, extra in (("smooth", ["--smooth"]), ("nostripes", ["--nostripes"]), ("nohill", ["--nohill"])):
        fr, iss = run(td, name, t, extra)
        res[name] = {"changed_share": share(ref, fr[0]), "issues": iss[:5]}
        imgs[name] = fr[0]
    for name, ge in (("mobile", ["--rendering-method", "mobile"]),
                     ("gl_compatibility", ["--rendering-method", "gl_compatibility"])):
        fr, iss = run(td, name, t, (), ge)
        d = np.abs(ref - fr[0]).max(-1)
        res[name] = {"changed_share": share(ref, fr[0]), "max_diff": int(d.max()), "issues": iss[:5]}
    # Dauerlauf: ab t = 30 s, 60 Bilder
    fr, iss = run(td, "t30", 30.0, (), (), n=60)
    res["t30"] = {"frames": len(fr), "issues": iss[:5],
                  "motion_share": share(fr[0], fr[-1]) if len(fr) > 1 else None}
    Image.fromarray(fr[-1].astype(np.uint8)).save(td / "t30_last.png")
    (SD / "assets" / "compare.json").write_text(json.dumps(res, indent=1))
    # Vergleichsbild: normal | linear | ohne Streifen | ohne Kuppe (Ausschnitt um Straße und Sprites)
    crop = (0, 50, 320, 224)
    tiles = []
    for name in ("normal", "smooth", "nostripes", "nohill"):
        im = Image.fromarray(imgs[name].astype(np.uint8)).crop(crop).resize((640, 348), Image.NEAREST)
        d = ImageDraw.Draw(im)
        d.rectangle([0, 0, 110, 14], fill="black")
        d.text((4, 2), name, fill="white")
        tiles.append(im)
    sheet = Image.new("RGB", (1284, 700), "white")
    for i, im in enumerate(tiles):
        sheet.paste(im, ((i % 2) * 644, (i // 2) * 352))
    sheet.save(SD / "assets" / "compare_switches.png")
    print(json.dumps(res, indent=1))


if __name__ == "__main__":
    main()
