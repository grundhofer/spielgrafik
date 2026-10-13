#!/usr/bin/env python3
"""Misst den Dachs in der gerenderten Demo: Fußzeile, Fußspalten, Kopfoberkante, Nasenlage je Bild.

Rendert zweimal (mit und ohne Dachs, beide ohne Schatten, Korn und Oberfläche); der Unterschied ist die Figur.
    .venv/bin/python styles/fotoreal-standbild/tools/measure_actor.py <Arbeitsordner> [--t0 0]
Erwartung: Füße in allen Bildern auf derselben Zeile und Spalte (±0 px); Kopf hebt und senkt sich mit dem Atem um
höchstens 1 px je Bild; die Kopfdrehung zeigt sich als Sprung der Kopfmitte nur in den Überblendbildern.
"""
import argparse, json, pathlib, sys

import numpy as np
from PIL import Image

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from render import render  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("work")
    ap.add_argument("--t0", type=float, default=0.0)
    a = ap.parse_args()
    work = pathlib.Path(a.work)
    common = [f"--t0={a.t0}", "--no-ui", "--no-grain", "--no-shadow"]
    w = render(work / "with", 180, None, common, quiet=True)
    wo = render(work / "without", 180, None, common + ["--no-actor"], quiet=True)
    rows = []
    for i, (p, q) in enumerate(zip(w, wo)):
        A = np.asarray(Image.open(p).convert("RGB"), np.int16)
        B = np.asarray(Image.open(q).convert("RGB"), np.int16)
        m = np.abs(A - B).max(-1) > 18
        ys, xs = np.where(m)
        feet = int(ys.max())
        low = m[feet - 6:feet + 1]
        fx = np.where(low.any(0))[0]
        top = int(ys.min())
        head = m[top:top + 40]
        hx = np.where(head.any(0))[0]
        rows.append({"frame": i, "feet_y": feet, "feet_x0": int(fx.min()), "feet_x1": int(fx.max()), "top_y": top,
                     "head_x0": int(hx.min()), "head_x1": int(hx.max())})
    def span(k):
        v = [r[k] for r in rows]
        return [min(v), max(v)]
    top_jump = max(abs(rows[i + 1]["top_y"] - rows[i]["top_y"]) for i in range(len(rows) - 1))
    feet_jump = max(abs(rows[i + 1]["feet_y"] - rows[i]["feet_y"]) for i in range(len(rows) - 1))
    summary = {k: span(k) for k in ("feet_y", "feet_x0", "feet_x1", "top_y", "head_x0", "head_x1")}
    summary["max_top_jump_per_frame"] = top_jump
    summary["max_feet_jump_per_frame"] = feet_jump
    print(json.dumps(summary))
    (work / "actor_measure.json").write_text(json.dumps({"summary": summary, "frames": rows}, indent=1))


if __name__ == "__main__":
    main()
