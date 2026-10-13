#!/usr/bin/env python3
"""Probebilder der Demo für die Entwicklung (ohne media/ anzufassen).

    .venv/bin/python styles/raymarching-sdf/scripts/snap.py OUT_DIR --times 0.5,2.0,4.8 [--renderer mobile] [-- --debug 1]

Jeder Zeitpunkt ist eine reine Funktion von t (main.gd --start), deshalb startet das Skript Godot je
Zeitpunkt neu und nimmt nur wenige Bilder auf (Movie Maker, feste Bildrate 30). Das zweite Bild wird
als OUT_DIR/t<zeit>.png gespeichert (das erste kann noch vor dem Kompilieren des Shaders liegen).
Argumente nach "--" gehen an die Demo. Fehlerzeilen aus dem Godot-Protokoll werden ausgegeben.
"""
import argparse, pathlib, re, shutil, subprocess, sys, tempfile

DEMO = pathlib.Path(__file__).resolve().parent.parent / "demo"


def snap(out, tt, renderer="", user=(), resolution="1280x720", frames=2, keep_all=False):
    with tempfile.TemporaryDirectory() as td:
        cmd = ["godot", "--path", str(DEMO), "--position", "20000,20000", "--resolution", resolution,
               "--write-movie", str(pathlib.Path(td) / "f.png"), "--fixed-fps", "30", "--quit-after", str(frames)]
        if renderer:
            cmd += ["--rendering-method", renderer]
        start = tt - frames / 30.0
        cmd += ["--", "--start", f"{start:.4f}", *user]
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
        log = r.stdout + r.stderr
        errs = [l for l in log.splitlines() if re.search(r"ERROR|SCRIPT|WARNING", l)]
        pngs = sorted(pathlib.Path(td).glob("f*.png"))
        if not pngs:
            print(log[-3000:])
            return None, errs, log
        if keep_all:
            outs = []
            for i, p in enumerate(pngs):
                o = out / f"t{tt:05.2f}_{i:03d}.png"
                shutil.copy(p, o)
                outs.append(o)
            return outs, errs, log
        o = out / f"t{tt:05.2f}.png"
        shutil.copy(pngs[-1], o)
        return o, errs, log


def main():
    argv = sys.argv[1:]
    user = []
    if "--" in argv:
        i = argv.index("--")
        argv, user = argv[:i], argv[i + 1:]
    ap = argparse.ArgumentParser()
    ap.add_argument("out")
    ap.add_argument("--times", default="0.5,2.5,4.8")
    ap.add_argument("--renderer", default="")
    ap.add_argument("--resolution", default="1280x720")
    a = ap.parse_args(argv)
    out = pathlib.Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    for tt in [float(x) for x in a.times.split(",")]:
        o, errs, _ = snap(out, tt, a.renderer, user, a.resolution)
        for e in errs[:10]:
            print("  ", e)
        print(o)


if __name__ == "__main__":
    main()
