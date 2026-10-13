#!/usr/bin/env python3
"""Baut alle Assets des Eintrags aus den Rohbildern neu und prüft die Demo.

    .venv/bin/python styles/fotoreal-standbild/tools/process.py [--debug <Ordner>]

1. prep_scene.py: KI-Foto + KI-Farbcode-Maske -> photo, plate, mask_a/b/c, photo_blur, noise, scene.json
2. prep_actor.py: freigestellter KI-Dachs (+ Fassung mit gedrehtem Kopf) -> actor, actor_look, actor_aux, actor_aux2,
   actor_shadow, actor_raw, actor.json
3. godot --import und ein Probelauf (bricht bei ERROR ab)
Korrekturen von Hand stehen nur in tools/scene.json und tools/actor.json.
"""
import argparse, pathlib, re, subprocess, sys

HERE = pathlib.Path(__file__).resolve().parent
DEMO = HERE.parent / "demo"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--debug")
    a = ap.parse_args()
    for name in ("prep_scene.py", "prep_actor.py"):
        cmd = [sys.executable, str(HERE / name)]
        if a.debug:
            cmd += ["--debug", str(pathlib.Path(a.debug) / name.replace(".py", ""))]
        subprocess.run(cmd, check=True)
    for cmd in (["godot", "--headless", "--path", str(DEMO), "--import"],
                ["godot", "--headless", "--path", str(DEMO), "--quit-after", "5"]):
        r = subprocess.run(cmd, capture_output=True, text=True)
        errs = [l for l in (r.stdout + r.stderr).splitlines() if re.search(r"\bERROR\b|SCRIPT ERROR", l)]
        if errs:
            sys.exit("Godot-Fehler:\n" + "\n".join(errs))
    print("ok")


if __name__ == "__main__":
    main()
