#!/usr/bin/env python3
"""Prüft, ob der Zeichenbefehl-Interpreter der Godot-Demo dasselbe Bild erzeugt wie agipic.py.

    .venv/bin/python styles/ega-adventure/scripts/check_pic.py [bild.pic.json]
Ohne Angabe das Handbild demo/art/harbor.pic.json. Godot spielt die Datei immer über --pic ab, unabhängig davon,
welches Bild demo/art/scene.json für die Demo wählt.
"""
import json, pathlib, subprocess, sys, tempfile

import numpy as np

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from agipic import replay, W, H  # noqa: E402

SD = HERE.parent
pic = pathlib.Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else SD / "demo/art/harbor.pic.json"
cmds = json.loads(pic.read_text())["commands"]
vis, pri = replay(cmds)
with tempfile.TemporaryDirectory() as td:
    dump = pathlib.Path(td) / "pic.bin"
    r = subprocess.run(["godot", "--headless", "--path", str(SD / "demo"), "--quit-after", "90", "--",
                        f"--dump-pic={dump}", f"--pic={pic}"],
                       capture_output=True, text=True, timeout=300)
    print("\n".join(l for l in r.stdout.splitlines() if "Bild fertig" in l))
    raw = np.frombuffer(dump.read_bytes(), np.uint8)
gv, gp = raw[:W * H].reshape(H, W), raw[W * H:].reshape(H, W)
dv, dp = int((gv != vis).sum()), int((gp != pri).sum())
print(f"sichtbare Ebene: {dv} abweichende Pixel, Prioritätsebene: {dp}")
sys.exit(1 if dv or dp else 0)
