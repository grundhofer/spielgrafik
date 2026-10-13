#!/usr/bin/env python3
"""Probelauf mit anderen Renderern und Wiederholbarkeit.

Aufruf aus dem Projektordner:
    .venv/bin/python styles/hintergrund-serie/tools/render_check.py

Nimmt die Demo mit Forward+ zweimal auf (Wiederholbarkeit, md5 je Bild) und je einmal mit
--rendering-method mobile und gl_compatibility, alles in ein Temp-Verzeichnis. Verglichen werden die
Bilder an den Zeitpunkten von frames.jpg: mittlere Abweichung je Kanal und Anteil der Pixel mit
Abweichung > 8/255. Schreibt <out>/render_check.json und eine Vergleichsleiste nach <out>/render_check.png
(--out, Standard assets/; mit Platzhaltern in demo/art einen Temp-Ordner angeben).
"""
import argparse, hashlib, json, pathlib, subprocess, sys, tempfile

import numpy as np
from PIL import Image

SD = pathlib.Path(__file__).resolve().parent.parent
DEMO = SD / "demo"
FPS, N = 30, 180
IDX = [int(i * (N - 1) / 7) for i in range(8)]


def record(td, tag, method=None):
    out = pathlib.Path(td) / tag
    out.mkdir()
    cmd = ["godot", "--path", str(DEMO), "--position", "20000,20000", "--resolution", "1280x720",
           "--write-movie", str(out / "f.png"), "--fixed-fps", str(FPS), "--quit-after", str(N)]
    if method:
        cmd[1:1] = ["--rendering-method", method]
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
    errs = [l for l in (r.stdout + r.stderr).splitlines() if "ERROR" in l]
    frames = sorted(out.glob("f*.png"))
    return frames, errs


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(SD / "assets"))
    out_dir = pathlib.Path(ap.parse_args().out)
    out_dir.mkdir(parents=True, exist_ok=True)
    report = {}
    with tempfile.TemporaryDirectory() as td:
        runs = {}
        for tag, method in (("forward", None), ("forward2", None), ("mobile", "mobile"),
                            ("compat", "gl_compatibility")):
            frames, errs = record(td, tag, method)
            runs[tag] = frames
            report[tag] = {"frames": len(frames), "errors": errs[:5]}
            print(tag, len(frames), "Bilder", f"{len(errs)} Fehler")
        md5 = lambda p: hashlib.md5(p.read_bytes()).hexdigest()
        same = sum(md5(a) == md5(b) for a, b in zip(runs["forward"], runs["forward2"]))
        report["repeat_identical_frames"] = f"{same}/{len(runs['forward'])}"
        strip = []
        for tag in ("mobile", "compat"):
            diffs, shares = [], []
            for i in IDX:
                if i >= len(runs[tag]) or i >= len(runs["forward"]):
                    continue
                a = np.asarray(Image.open(runs["forward"][i]).convert("RGB"), np.int16)
                b = np.asarray(Image.open(runs[tag][i]).convert("RGB"), np.int16)
                d = np.abs(a - b)
                diffs.append(float(d.mean()))
                shares.append(float((d.max(2) > 8).mean()))
            report[tag]["mean_abs_diff"] = [round(x, 2) for x in diffs]
            report[tag]["share_gt8"] = [round(x, 3) for x in shares]
        for tag in ("forward", "mobile", "compat"):
            strip.append(Image.open(runs[tag][IDX[4]]).convert("RGB").resize((640, 360), Image.LANCZOS))
        sheet = Image.new("RGB", (640 * 3, 360))
        for k, im in enumerate(strip):
            sheet.paste(im, (640 * k, 0))
        sheet.save(out_dir / "render_check.png")
    (out_dir / "render_check.json").write_text(json.dumps(report, indent=1) + "\n")
    print(json.dumps(report, indent=1))


if __name__ == "__main__":
    sys.exit(main())
