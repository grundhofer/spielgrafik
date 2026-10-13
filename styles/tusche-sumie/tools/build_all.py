#!/usr/bin/env python3
"""Baut den Eintrag tusche-sumie aus den vorhandenen Rohbildern neu auf (ruft kein Bildmodell auf).

    .venv/bin/python styles/tusche-sumie/tools/build_all.py [--measure <Arbeitsordner>]

Reihenfolge: Papier und Stempel, Code-Effekte, Pinselstriche zuschneiden, Hintergrund, Figur, Zusammenstellen,
Godot-Import; mit --measure zusätzlich die Fuß- und Kopfmessung (measure_badger.py) und die Lücke zwischen
Schornstein und Rauch (measure_smoke.py). make_clean_refs.py gehört nicht dazu: Es erzeugt nur die Vorlagen für
die Bildaufträge walk_v3/front_v3.
"""
import argparse, pathlib, subprocess, sys

HERE = pathlib.Path(__file__).resolve().parent
PY = sys.executable


def run(*args):
    print("+", " ".join(str(a) for a in args), flush=True)
    subprocess.run(list(args), check=True, cwd=HERE)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--measure")
    a = ap.parse_args()
    for s in ("make_paper.py", "make_fx.py"):
        run(PY, s)
    run(PY, "prep_strokes.py", "--pick")
    for s in ("prep_bg.py", "prep_badger.py", "stage.py"):
        run(PY, s)
    run("godot", "--headless", "--path", str(HERE.parent / "demo"), "--import")
    if a.measure:
        run(PY, "measure_badger.py", "--tmp", a.measure)
        run(PY, "measure_smoke.py", "--tmp", a.measure)


if __name__ == "__main__":
    main()
