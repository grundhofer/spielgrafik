#!/usr/bin/env python3
"""Einzelbild(er) der Demo zu bestimmten Zeitpunkten rendern (Prüfhilfe).

    .venv/bin/python styles/diorama-tiltshift/scripts/still.py OUT_DIR 0.0 2.5 5.0 [-- --no-dof ...]

Für jeden Zeitpunkt startet Godot mit --t0=<Zeit> und schreibt zwei Bilder (--write-movie); das zweite
wird als OUT_DIR/still_<zeit>.png behalten.
"""
import pathlib, shutil, subprocess, sys, tempfile

DEMO = pathlib.Path(__file__).resolve().parent.parent / "demo"
argv = sys.argv[1:]
extra = []
if "--" in argv:
    i = argv.index("--")
    argv, extra = argv[:i], argv[i + 1:]
out = pathlib.Path(argv[0])
out.mkdir(parents=True, exist_ok=True)
subprocess.run(["godot", "--headless", "--path", str(DEMO), "--import"], capture_output=True)
for ts in argv[1:]:
    with tempfile.TemporaryDirectory() as td:
        r = subprocess.run(["godot", "--path", str(DEMO), "--position", "20000,20000", "--resolution", "1280x720",
                            "--write-movie", f"{td}/f.png", "--fixed-fps", "30", "--quit-after", "2", "--",
                            f"--t0={ts}", *extra], capture_output=True, text=True)
        errs = [l for l in (r.stdout + r.stderr).splitlines() if "ERROR" in l or "WARNING" in l]
        for e in errs[:12]:
            print("  ", e)
        frames = sorted(pathlib.Path(td).glob("f*.png"))
        if not frames:
            print("keine Bilder", r.stderr[-2000:])
            continue
        tag = "_".join(a.strip("-").replace("=", "").replace(",", "_") for a in extra)
        dst = out / f"still_{float(ts):05.2f}{'_' + tag if tag else ''}.png"
        shutil.copy(frames[-1], dst)
        print(dst)
