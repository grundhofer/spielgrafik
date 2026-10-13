"""Messung des Dachses in der echten Godot-Ausgabe (Basisauflösung 160x144).

Nimmt die Demo mit --sprites-only auf (nur Sprites des Dachses auf hellem Grund) und misst je Bild:
Bodenkontakte (Pixelläufe in der Fußzeile), Kopf (Schwerpunkt der Mützenzeilen) und Fußzeile.
Prüft: Beim Laufen bleibt zwischen zwei aufeinanderfolgenden Laufbildern mindestens ein Fuß auf ±1 px stehen;
im Stehen (Profil nach dem Halt, dann Vorderansicht mit Blinzeln und Atmen) sind Fußzeilen und Bodenkontakte je
Ansicht in allen Bildern gleich. Zusätzlich: Anzahl Farben je Bild
der normalen Aufnahme (muss 4 sein).

  .venv/bin/python styles/gameboy/scripts/probe.py [--keep DIR]   (DIR: eigener Temp-Ordner, sonst System-Temp)
"""
import argparse
import json
import pathlib
import re
import subprocess
import tempfile

import numpy as np
from PIL import Image

ROOT = pathlib.Path(__file__).resolve().parent.parent
GB = {(0x9b, 0xbc, 0x0f): 0, (0x8b, 0xac, 0x0f): 1, (0x30, 0x62, 0x30): 2, (0x0f, 0x38, 0x0f): 3}


def record(out, args=()):
    cmd = ["godot", "--path", str(ROOT / "demo"), "--position", "20000,20000", "--write-movie", str(out / "f.png"),
           "--fixed-fps", "30", "--quit-after", "180", "--", *args]
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
    return r.stdout + r.stderr


def runs(row):
    xs = np.flatnonzero(row)
    out = []
    for x in xs:
        if out and x == out[-1][1] + 1:
            out[-1][1] = x
        else:
            out.append([x, x])
    return [tuple(r) for r in out]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--keep")
    a = ap.parse_args()
    rom = json.loads((ROOT / "demo" / "rom" / "rom.json").read_text())
    feet_y = rom["scene"]["feet_y"]
    with tempfile.TemporaryDirectory() as td:
        d = pathlib.Path(a.keep or td)
        d.mkdir(parents=True, exist_ok=True)
        (d / "sp").mkdir(exist_ok=True)
        (d / "full").mkdir(exist_ok=True)
        log = record(d / "sp", ["--sprites-only"]) + record(d / "full")
        sp = sorted((d / "sp").glob("f*.png"))
        full = sorted((d / "full").glob("f*.png"))
        rows = []
        prev = None
        for i, p in enumerate(sp):
            im = np.asarray(Image.open(p).convert("RGB"))
            fig = (im != np.array([0x9b, 0xbc, 0x0f])).any(-1)
            if not fig.any():
                rows.append(None)
                continue
            ys = np.flatnonzero(fig.any(1))
            top, bottom = ys[0], ys[-1]
            head = fig[top:top + 4]
            hx = float(np.mean(np.nonzero(head)[1]))
            ground = runs(fig[feet_y])
            rows.append({"i": i, "top": int(top), "bottom": int(bottom), "head_x": round(hx, 2),
                         "ground": [list(map(int, g)) for g in ground]})
        colors = []
        for p in full[::10]:
            im = np.asarray(Image.open(p).convert("RGB")).reshape(-1, 3)
            u = {tuple(c) for c in np.unique(im, axis=0)}
            colors.append(len(u))
            assert u <= set(GB), f"fremde Farben in {p.name}: {u - set(GB)}"
    # Auswertung: Zeitplan aus main.gd (WALK_FRAMES bei 15 Laufbildern/s, TURN_T)
    gd = (ROOT / "demo" / "scripts" / "main.gd").read_text()
    walk_frames = int(re.search(r"const WALK_FRAMES := (\d+)", gd).group(1))
    turn_t = float(re.search(r"const TURN_T := ([\d.]+)", gd).group(1))
    walk_end = int(round(walk_frames / 15 * 30))
    turn = int(round(turn_t * 30))
    problems = []
    changes = 0
    last = None
    for r in rows:
        if r is None:
            continue
        key = (tuple(map(tuple, r["ground"])), r["top"], r["head_x"])
        if last is not None and key != last[0]:
            changes += 1
            g0, g1 = last[1]["ground"], r["ground"]
            if r["i"] < walk_end + 2:
                ok = any(abs(a0 - b0) <= 1 and abs(a1 - b1) <= 1 for a0, a1 in g0 for b0, b1 in g1)
                if not ok and g0 and g1:
                    problems.append(f"Bild {r['i']}: kein Fuß bleibt stehen {g0} -> {g1}")
        last = (key, r)
    phases = {"profil": [r for r in rows if r and walk_end + 2 <= r["i"] < turn],
              "front": [r for r in rows if r and r["i"] >= turn]}
    stand = {}
    for name, ph in phases.items():
        sg = {tuple(map(tuple, r["ground"])) for r in ph}
        sb = {r["bottom"] for r in ph}
        stand[name] = {"frames": len(ph), "ground": [list(g) for g in sg], "bottom": sorted(sb)}
        if len(sg) > 1 or len(sb) > 1:
            problems.append(f"Stehen ({name}): Bodenkontakte {sg}, Fußzeilen {sb}")
    print(json.dumps({"frames": len(rows), "walk_end": walk_end, "turn": turn, "changes": changes,
                      "stand": stand, "colors_per_frame": sorted(set(colors)), "problems": problems}, indent=1))
    for r in rows[::3][:40]:
        print(r)
    hw = [l for l in log.splitlines() if l.startswith("HWSTAT")]
    print("\n".join(hw))


if __name__ == "__main__":
    main()
