#!/usr/bin/env python3
"""Vergleicht Forward+ mit mobile und gl_compatibility (Bilder 60 und 141 der Demo).

Schreibt assets/check/renderer_compare.json und assets/check/renderer_compat.png (Forward+ | compat | Differenz x8).

    .venv/bin/python styles/papier-collage/scripts/compare_renderers.py
"""
import json, pathlib, subprocess, tempfile
import numpy as np
from PIL import Image

HERE = pathlib.Path(__file__).resolve().parent.parent
FRAMES = (60, 141)


def render(method):
    tmp_root = pathlib.Path(tempfile.gettempdir()) / "papier-collage"
    tmp_root.mkdir(exist_ok=True)
    td = pathlib.Path(tempfile.mkdtemp(prefix=f"{method or 'fwd'}-", dir=tmp_root))
    cmd = ["godot", "--path", str(HERE / "demo"), "--position", "20000,20000", "--resolution", "1280x720",
           "--write-movie", str(td / "f.png"), "--fixed-fps", "30", "--quit-after", str(max(FRAMES) + 2)]
    if method:
        cmd[1:1] = ["--rendering-method", method]
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
    errs = [l for l in (r.stdout + r.stderr).splitlines() if "ERROR" in l]
    return {f: np.asarray(Image.open(td / f"f{f:08d}.png").convert("RGB")).astype(int) for f in FRAMES}, errs


def main():
    base, e0 = render(None)
    out = {"errors_forward_plus": e0}
    for m in ("mobile", "gl_compatibility"):
        imgs, errs = render(m)
        out[m] = {"errors": errs}
        for f in FRAMES:
            d = np.abs(imgs[f] - base[f])
            out[m][f"frame_{f}"] = {"mean": round(float(d.mean()), 3), "max": int(d.max()),
                                    "share_gt8": round(float((d.max(-1) > 8).mean()), 4)}
        if m == "gl_compatibility":
            f = FRAMES[1]
            d = np.clip(np.abs(imgs[f] - base[f]) * 8, 0, 255)
            row = np.concatenate([base[f], imgs[f], d], 1).astype(np.uint8)
            Image.fromarray(row).resize((1920, 360)).save(HERE / "assets" / "check" / "renderer_compat.png")
    (HERE / "assets" / "check" / "renderer_compare.json").write_text(json.dumps(out, indent=1))
    print(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
