#!/usr/bin/env python3
"""Fertigstellen nach den Bildaufträgen: verarbeitet jedes vorhandene KI-Bild aus assets/raw/ und baut die Demo neu.
Ruft kein Bildmodell auf.

    .venv/bin/python styles/aquarell/tools/build_ai.py [--raw DIR] [--override FILE] [--no-measure]

  raw/bg.png    -> prep_bg_ai.py     (Hintergrund, Masken, Lichtpunkte, scene_ai.json)
  raw/walk.png  -> prep_badger_ai.py (mit raw/front.png, falls vorhanden)
  dann stage.py (nimmt KI-Teile, wo vorhanden, sonst die gerechnete 3D-Fassung), Godot-Import, Probelauf und
  measure_badger.py. Danach: Prüfbilder in assets/check/ ansehen, ggf. assets/bg_ai_override.json anlegen und
  erneut ausführen, dann tools/capture.py.
"""
import argparse, pathlib, re, subprocess, sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
PY = sys.executable


def run(cmd, **kw):
    print("$", " ".join(str(c) for c in cmd), flush=True)
    return subprocess.run([str(c) for c in cmd], **kw)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--raw", default=str(ROOT / "assets/raw"))
    ap.add_argument("--override", default=str(ROOT / "assets/bg_ai_override.json"))
    ap.add_argument("--no-measure", action="store_true")
    a = ap.parse_args()
    raw = pathlib.Path(a.raw)
    T = ROOT / "tools"
    if (raw / "bg.png").exists():
        run([PY, T / "prep_bg_ai.py", "--raw", raw / "bg.png", "--override", a.override], check=True)
    else:
        print("kein raw/bg.png: Hintergrund bleibt die gerechnete 3D-Fassung")
    if (raw / "walk.png").exists():
        run([PY, T / "prep_badger_ai.py", "--walk", raw / "walk.png", "--front", raw / "front.png"], check=True)
    else:
        print("kein raw/walk.png: Figur bleibt die gerechnete 3D-Fassung")
    run([PY, T / "stage.py"], check=True)
    demo = ROOT / "demo"
    errs = []
    for cmd in (["godot", "--headless", "--path", demo, "--import"],
                ["godot", "--headless", "--path", demo, "--quit-after", "30"]):
        r = run(cmd, capture_output=True, text=True, timeout=600)
        errs += [l for l in (r.stdout + r.stderr).splitlines() if re.search(r"\bERROR\b|SCRIPT ERROR", l)]
    if errs:
        print("GODOT-FEHLER:\n" + "\n".join(errs[:20]))
        sys.exit(1)
    print("Godot: keine Fehler")
    if not a.no_measure:
        run([PY, T / "measure_badger.py"], check=True)
    print("\nAnsehen: assets/check/bg_ai_check.png, bg_ai_grid.png, badger_ai_frames.png, badger_ai_feet.png")
    print("Aufnahme: .venv/bin/python tools/capture.py styles/aquarell --poster-at 0.72")


if __name__ == "__main__":
    main()
