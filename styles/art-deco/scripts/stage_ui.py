#!/usr/bin/env python3
"""Schreibt demo/art/ui_text.json aus data/motif.json (ui_text), damit die Demo den Text nicht doppelt führt.

    .venv/bin/python styles/art-deco/scripts/stage_ui.py
"""
import json, pathlib

ROOT = pathlib.Path(__file__).resolve().parents[1]
motif = json.loads((ROOT.parents[1] / "data/motif.json").read_text())
(ROOT / "demo/art/ui_text.json").write_text(json.dumps(motif["ui_text"], indent=1, ensure_ascii=False))
print("ok", motif["ui_text"]["location"])
