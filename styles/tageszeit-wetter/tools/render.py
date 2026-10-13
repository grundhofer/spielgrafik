#!/usr/bin/env python3
"""Rendert die Demo in ein beliebiges Verzeichnis (Einzelzustände oder ganze Läufe), ohne media/ anzufassen.

    .venv/bin/python styles/tageszeit-wetter/tools/render.py OUT --states 0 1 2 3 4 5   # je ein Standbild
    .venv/bin/python styles/tageszeit-wetter/tools/render.py OUT --frames 180            # ganze Aufnahme
    ... --method mobile|gl_compatibility   (Renderer-Vergleich)   ... --args --no-badger

Standbilder: Zustand eingefroren, 20 Bilder laufen lassen (Partikel stehen dann), das letzte wird gespeichert.
"""
import argparse, pathlib, re, shutil, subprocess, sys, tempfile

ENTRY = pathlib.Path(__file__).resolve().parent.parent
DEMO = ENTRY / "demo"


def run(out_pattern, frames, user_args, method):
    cmd = ["godot", "--path", str(DEMO), "--position", "20000,20000", "--resolution", "1280x720",
           "--write-movie", str(out_pattern), "--fixed-fps", "30", "--quit-after", str(frames)]
    if method:
        cmd += ["--rendering-method", method]
    if user_args:
        cmd += ["--"] + user_args
    p = subprocess.run(cmd, capture_output=True, text=True, timeout=900)
    log = p.stdout + p.stderr
    errs = [l for l in log.splitlines() if re.search(r"\bERROR\b|SCRIPT ERROR|WARNING", l)]
    return errs, log


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("out")
    ap.add_argument("--states", type=int, nargs="*")
    ap.add_argument("--frames", type=int, default=0)
    ap.add_argument("--method", default="")
    ap.add_argument("--args", nargs=argparse.REMAINDER, default=[])
    a = ap.parse_args()
    out = pathlib.Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    subprocess.run(["godot", "--headless", "--path", str(DEMO), "--import"], capture_output=True, timeout=600)
    if a.states is not None:
        for s in a.states:
            with tempfile.TemporaryDirectory() as td:
                errs, log = run(pathlib.Path(td) / "f.png", 20, [f"--state={s}"] + a.args, a.method)
                pngs = sorted(pathlib.Path(td).glob("f*.png"))
                if not pngs:
                    sys.exit(log[-2000:])
                shutil.copy2(pngs[-1], out / f"state_{s}.png")
                for e in errs[:8]:
                    print(f"[state {s}] {e}")
    if a.frames:
        errs, log = run(out / "f.png", a.frames, a.args, a.method)
        for e in errs[:12]:
            print(e)
    print(out)


if __name__ == "__main__":
    main()
