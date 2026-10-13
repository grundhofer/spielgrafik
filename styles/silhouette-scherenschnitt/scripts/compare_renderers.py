#!/usr/bin/env python3
"""Vergleicht Forward+ mit mobile und gl_compatibility (PIPELINE.md: Selbstprüfung 5) und prüft den
Langzeitlauf (--t0=30) sowie zwei Läufe auf Gleichheit.

    .venv/bin/python styles/silhouette-scherenschnitt/scripts/compare_renderers.py <tmpdir>
"""
import hashlib, json, pathlib, subprocess, sys
import numpy as np
from PIL import Image

SD = pathlib.Path(__file__).resolve().parents[1]
N = 154   # bis zum Posterbild (153)


def run(out, extra_godot=(), user=()):
    out.mkdir(parents=True, exist_ok=True)
    for f in out.glob("*.png"):
        f.unlink()
    cmd = ["godot", "--path", str(SD / "demo"), "--position", "20000,20000", "--resolution", "1280x720",
           *extra_godot, "--write-movie", str(out / "f.png"), "--fixed-fps", "30", "--quit-after", str(N)]
    if user:
        cmd += ["--", *user]
    r = subprocess.run(cmd, capture_output=True, text=True)
    bad = [l for l in (r.stdout + r.stderr).splitlines() if "ERROR" in l or "WARNING" in l]
    return sorted(out.glob("f*.png")), bad


def arr(p):
    return np.asarray(Image.open(p).convert("RGB")).astype(np.int16)


def main():
    tmp = pathlib.Path(sys.argv[1])
    subprocess.run(["godot", "--headless", "--path", str(SD / "demo"), "--import"], capture_output=True)
    res = {}
    base, bad = run(tmp / "fwd")
    res["forward_plus_errors"] = bad
    again, _ = run(tmp / "fwd2")
    res["two_runs_identical"] = all(hashlib.md5(a.read_bytes()).hexdigest() == hashlib.md5(b.read_bytes()).hexdigest()
                                    for a, b in zip(base, again))
    for m in ("mobile", "gl_compatibility"):
        files, bad = run(tmp / m, ("--rendering-method", m))
        d = [np.abs(arr(a) - arr(b)) for a, b in zip(base[::30] + [base[153]], files[::30] + [files[153]])]
        res[m] = {"errors": bad, "mean_abs_diff": round(float(np.mean([x.mean() for x in d])), 3),
                  "max_abs_diff": int(max(x.max() for x in d)),
                  "share_px_over_8": round(float(np.mean([(x.max(2) > 8).mean() for x in d])), 4)}
        Image.fromarray(np.abs(arr(base[153]) - arr(files[153])).clip(0, 255).astype(np.uint8) * 8).save(
            tmp / f"diff_{m}.png")
    long, bad = run(tmp / "t30", user=("--t0=30",))
    res["t0_30_errors"] = bad
    Image.open(long[60]).save(tmp / "t30_f60.png")
    Image.open(long[150]).save(tmp / "t30_f150.png")
    (SD / "assets" / "check" / "renderer_compare.json").write_text(json.dumps(res, indent=1))
    print(json.dumps(res, indent=1))


if __name__ == "__main__":
    main()
