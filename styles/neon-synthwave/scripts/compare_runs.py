#!/usr/bin/env python3
"""Prüfläufe außerhalb von tools/capture.py, Ergebnis in assets/check/runs.json:

1. Zwei Forward+-Läufe (Bild 147 = Poster bei --poster-at 0.82): bitgleich?
2. Renderer: Mobile und gl_compatibility gegen Forward+ (Bild 147), mittlere Abweichung und Anteil der Pixel,
   die sich um mehr als 24 Stufen ändern; Sparfassung --ss=1 (ID-Puffer in Bildgröße) ebenso.
3. Langzeitlauf ab t = 30 s (1 s) und ab t = 300 s: Fehlerfreiheit; Kontaktbogen zum Ansehen wird mit --sheet
   geschrieben (nicht im Eintrag gespeichert).

    .venv/bin/python styles/neon-synthwave/scripts/compare_runs.py [--sheet out.png]
"""
import argparse
import json
import pathlib
import subprocess
import tempfile

import numpy as np
from PIL import Image

ENTRY = pathlib.Path(__file__).resolve().parent.parent
DEMO = ENTRY / "demo"
FRAME = 147


def run(out: pathlib.Path, frames: int, extra_godot=(), user=()) -> tuple[list[pathlib.Path], list[str]]:
    out.mkdir(parents=True, exist_ok=True)
    cmd = ["godot", *extra_godot, "--path", str(DEMO), "--position", "20000,20000", "--resolution", "1280x720",
           "--write-movie", str(out / "f.png"), "--fixed-fps", "30", "--quit-after", str(frames)]
    if user:
        cmd += ["--", *user]
    r = subprocess.run(cmd, capture_output=True, text=True)
    errs = [l for l in (r.stdout + r.stderr).splitlines() if "ERROR" in l or "WARNING" in l]
    return sorted(out.glob("f*.png")), errs


def arr(p: pathlib.Path) -> np.ndarray:
    return np.asarray(Image.open(p).convert("RGB"), dtype=np.float32)


def diff(a: np.ndarray, b: np.ndarray) -> dict:
    d = np.abs(a - b)
    return {"mean": round(float(d.mean()), 3), "share_gt24": round(float((d.max(axis=2) > 24).mean()), 4),
            "max": int(d.max()), "channel_mean": [round(float(x), 1) for x in a.reshape(-1, 3).mean(0)]}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--sheet")
    a = ap.parse_args()
    subprocess.run(["godot", "--headless", "--path", str(DEMO), "--import"], capture_output=True)
    res = {}
    with tempfile.TemporaryDirectory() as td:
        td = pathlib.Path(td)
        f1, e1 = run(td / "a", FRAME + 1)
        f2, e2 = run(td / "b", FRAME + 1)
        ref = arr(f1[FRAME])
        res["forward_plus_two_runs"] = {"frame": FRAME, **diff(arr(f2[FRAME]), ref), "errors": e1 + e2}
        res["forward_plus_channel_mean"] = diff(ref, ref)["channel_mean"]
        for name, g, u in (("mobile", ["--rendering-method", "mobile"], []),
                           ("gl_compatibility", ["--rendering-method", "gl_compatibility"], []),
                           ("ss1", [], ["--ss=1"])):
            f, e = run(td / name, FRAME + 1, g, u)
            res[name] = {"frame": FRAME, **diff(arr(f[FRAME]), ref), "errors": e[:5]}
        sheet = []
        for name, t0 in (("t30", "30"), ("t300", "300")):
            f, e = run(td / name, 30, (), ["--t0=" + t0])
            res["long_run_" + name] = {"frames": len(f), "errors": e[:5],
                                       "motion_share_gt24": round(float((np.abs(arr(f[-1]) - arr(f[0])).max(axis=2) > 24).mean()), 4)}
            sheet.append(Image.open(f[-1]).convert("RGB").resize((640, 360)))
        if a.sheet:
            s = Image.new("RGB", (1280, 360))
            for i, im in enumerate(sheet):
                s.paste(im, (640 * i, 0))
            s.save(a.sheet)
    out = ENTRY / "assets" / "check"
    out.mkdir(parents=True, exist_ok=True)
    (out / "runs.json").write_text(json.dumps(res, indent=1, ensure_ascii=False))
    print(json.dumps(res, indent=1, ensure_ascii=False))


if __name__ == "__main__":
    main()
