"""Renderer- und Reproduzierbarkeitsprüfung (PIPELINE.md, Selbstprüfung 5 und 3).

Rendert die Demo (mit Filmabzug) mit Forward+ zweimal, mit --rendering-method mobile und gl_compatibility je
einmal, und vergleicht die Bilder 30, 100 und 144 mit dem ersten Forward+-Lauf (mittlere und größte
Abweichung, Anteil abweichender Pixel). Dazu ein Langzeitlauf ab --t0=30 (60 Bilder): Prüfbild
assets/check/t30.jpg (Bild 30 des Laufs). Ergebnis: assets/check/renderer_compare.json

    .venv/bin/python styles/gummischlauch/scripts/compare_renderers.py
"""
import json
import os
import pathlib
import shutil
import subprocess
import tempfile

import numpy as np
from PIL import Image

HERE = pathlib.Path(__file__).resolve().parent.parent
DEMO = HERE / "demo"
TMP = pathlib.Path(os.environ.get("GUMMI_TMP", pathlib.Path(tempfile.gettempdir()) / "gummischlauch")) / "probe_render"
FRAMES = [30, 100, 144]


def render(name, n=180, pre=(), post=()):
    out = TMP / name
    out.mkdir(parents=True)
    r = subprocess.run(["godot", *pre, "--path", str(DEMO), "--position", "20000,20000", "--resolution", "1280x720",
                        "--write-movie", str(out / "f.png"), "--fixed-fps", "30", "--quit-after", str(n), "--",
                        *post], capture_output=True, text=True)
    errs = [l for l in (r.stdout + r.stderr).splitlines() if "ERROR" in l or "WARNING" in l]
    return sorted(out.glob("f*.png")), errs


def load(f):
    return np.asarray(Image.open(f).convert("RGB")).astype(int)


def main():
    if TMP.exists():
        shutil.rmtree(TMP)
    subprocess.run(["godot", "--headless", "--path", str(DEMO), "--import"], capture_output=True)
    ref, e0 = render("forward")
    res = {"frames_compared": FRAMES, "log_errors_warnings": {"forward": e0}}
    for name, pre in [("forward_2", ()), ("mobile", ("--rendering-method", "mobile")),
                      ("gl_compatibility", ("--rendering-method", "gl_compatibility"))]:
        files, errs = render(name, pre=pre)
        res["log_errors_warnings"][name] = errs
        d = {}
        for i in FRAMES:
            diff = np.abs(load(files[i]) - load(ref[i]))
            d[str(i)] = {"mean": round(float(diff.mean()), 3), "max": int(diff.max()),
                         "share_diff": round(float((diff.max(axis=2) > 0).mean()), 4)}
        res[name] = d
        print(name, d)
    files, errs = render("t30", n=60, post=("--t0=30",))
    res["log_errors_warnings"]["t30"] = errs
    (HERE / "assets" / "check").mkdir(exist_ok=True)
    Image.open(files[30]).convert("RGB").save(HERE / "assets" / "check" / "t30.jpg", quality=80)
    (HERE / "assets" / "check" / "renderer_compare.json").write_text(json.dumps(res, indent=1))
    print(res["log_errors_warnings"])
    shutil.rmtree(TMP)


if __name__ == "__main__":
    main()
